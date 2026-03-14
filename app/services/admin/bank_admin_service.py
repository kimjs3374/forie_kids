from datetime import datetime, timezone

from ..bank import find_candidate_reservations, get_bank_setting, manual_match_transaction, save_bank_setting, sync_bank_transactions
from ..bank.billboard_service import build_billboard_message
from ..bank.matching_service import normalize_name
from ..bank.settings_service import get_bank_code_label, update_bank_setting
from ..bank.sync_service import list_recent_sync_runs
from ..shared import format_kst_datetime, parse_iso_datetime, split_apt_unit, status_label
from ..supabase_service import fetch_rows, patch_rows


def _safe_fetch_rows(table_name, params=None):
    try:
        return fetch_rows(table_name, params=params)
    except Exception:
        return []


def _format_sync_run(sync_run):
    item = dict(sync_run)
    item["started_at_display"] = format_kst_datetime(sync_run.get("started_at"))
    item["finished_at_display"] = format_kst_datetime(sync_run.get("finished_at"))
    return item


def get_bank_setting_view():
    try:
        return get_bank_setting(include_decrypted=False)
    except Exception:
        return None


def save_bank_settings(form):
    return save_bank_setting(
        bank_code=form.bank_code.data,
        account_holder_name=form.account_holder_name.data,
        account_number=form.account_number.data,
        account_password=form.account_password.data,
        resident_number=form.resident_number.data,
        payment_amount=form.payment_amount.data,
        is_active=bool(form.is_active.data),
    )


def run_bank_sync(lookback_days=30, force=True):
    return sync_bank_transactions(force=force, lookback_days=lookback_days)


def list_bank_sync_histories(limit=10):
    try:
        return [_format_sync_run(item) for item in list_recent_sync_runs(limit=limit)]
    except Exception:
        return []


def _reservation_map():
    reservations = _safe_fetch_rows(
        "reservations",
        params={"select": "id,name,apt_unit,month_id,expected_amount,created_at,status,payment_confirmed_at"},
    )
    months = {
        item["id"]: item
        for item in _safe_fetch_rows("reservation_months", params={"select": "id,target_month,title,payment_amount"})
    }
    return reservations, months


def _build_manual_match_options(transaction, reservations, month_map, limit=30):
    transaction_amount = int(transaction.get("amount") or 0)
    transaction_name = normalize_name(transaction.get("deposit_name"))
    transaction_dt = parse_iso_datetime(transaction.get("transaction_date"))
    options = []

    for reservation in reservations:
        if reservation.get("status") != "PENDING_PAYMENT":
            continue

        month = month_map.get(reservation.get("month_id"), {})
        created_at = parse_iso_datetime(reservation.get("created_at"))
        amount_match = int(reservation.get("expected_amount") or 0) == transaction_amount
        name_match = normalize_name(reservation.get("name")) == transaction_name if transaction_name else False
        time_valid = not (transaction_dt and created_at and transaction_dt < created_at)
        score = (100 if amount_match else 0) + (10 if name_match else 0) + (1 if time_valid else 0)

        dong, ho = split_apt_unit(reservation.get("apt_unit"))
        recommendation = []
        if amount_match:
            recommendation.append("금액일치")
        if name_match:
            recommendation.append("이름일치")
        if time_valid:
            recommendation.append("시간유효")
        if not recommendation:
            recommendation.append("수동검토")

        options.append(
            {
                "id": reservation["id"],
                "target_month": month.get("target_month") or "-",
                "name": reservation.get("name") or "",
                "apt_dong": dong,
                "apt_ho": ho,
                "phone": reservation.get("phone") or "",
                "expected_amount_display": f"{int(reservation.get('expected_amount') or 0):,}원",
                "created_at_display": format_kst_datetime(reservation.get("created_at")),
                "amount_match": amount_match,
                "name_match": name_match,
                "time_valid": time_valid,
                "recommendation_label": " · ".join(recommendation),
                "score": score,
            }
        )

    options.sort(key=lambda item: (-item["score"], item["target_month"], item["id"]))
    return options[:limit]


def list_bank_transactions(status_filter="all", limit=100):
    params = {"select": "*", "order": "transaction_date.desc,id.desc", "limit": str(limit)}
    if status_filter and status_filter != "all":
        params["status"] = f"eq.{status_filter.upper()}"

    transactions = _safe_fetch_rows("bank_transactions", params=params)
    reservations, month_map = _reservation_map()
    reservation_by_id = {reservation["id"]: reservation for reservation in reservations}
    pending_reservations = [reservation for reservation in reservations if reservation.get("status") == "PENDING_PAYMENT"]
    match_logs = _safe_fetch_rows(
        "bank_match_logs",
        params={"select": "transaction_id,match_type,reason,created_at", "order": "created_at.desc,id.desc"},
    )
    match_log_map = {}
    for log in match_logs:
        match_log_map.setdefault(log.get("transaction_id"), log)

    formatted = []
    for transaction in transactions:
        item = dict(transaction)
        strict_candidates = []
        item["status_label"] = status_label(transaction.get("status"))
        item["transaction_date_display"] = format_kst_datetime(transaction.get("transaction_date"))
        item["amount_display"] = f"{int(transaction.get('amount') or 0):,}원"
        item["transaction_type_label"] = "입금" if str(transaction.get("transaction_type") or "").lower() == "deposit" else "출금"
        item["bank_name"] = get_bank_code_label(transaction.get("bank_code"))
        item["billboard_message"] = build_billboard_message(transaction) if transaction.get("status") == "UNMATCHED" else ""
        item["can_approve_billboard"] = transaction.get("status") == "UNMATCHED"
        item["can_ignore"] = transaction.get("status") in {"PENDING", "UNMATCHED"}
        item["can_manual_match"] = transaction.get("status") in {"PENDING", "UNMATCHED"}

        matched_reservation = reservation_by_id.get(transaction.get("matched_reservation_id"))
        match_log = match_log_map.get(transaction.get("id")) or {}
        if matched_reservation:
            month = month_map.get(matched_reservation.get("month_id"), {})
            item["matched_reservation"] = {
                "id": matched_reservation["id"],
                "name": matched_reservation.get("name"),
                "apt_unit": matched_reservation.get("apt_unit"),
                "target_month": month.get("target_month") or "-",
            }
        else:
            item["matched_reservation"] = None

        candidates = []
        if item["can_manual_match"]:
            strict_candidates = find_candidate_reservations(transaction, require_name_match=True)
            for candidate in find_candidate_reservations(transaction, require_name_match=False)[:5]:
                month = month_map.get(candidate.get("month_id"), {})
                candidate["target_month"] = month.get("target_month") or "-"
                candidates.append(candidate)
        item["manual_match_options"] = _build_manual_match_options(transaction, pending_reservations, month_map)
        item["candidate_reservations"] = candidates
        item["strict_candidate_count"] = len(strict_candidates)
        item["match_badge_label"] = ""
        item["match_badge_variant"] = ""

        reason_text = str(match_log.get("reason") or "")
        if item.get("status") == "MATCHED":
            if "묶음" in reason_text:
                item["match_badge_label"] = "묶음입금 처리"
                item["match_badge_variant"] = "bundle"
            elif "부분" in reason_text:
                item["match_badge_label"] = "부분입금 처리"
                item["match_badge_variant"] = "partial"
            else:
                item["match_badge_label"] = "매칭됨"
                item["match_badge_variant"] = "matched"

        if item.get("status") == "MATCHED":
            item["auto_match_note"] = "이미 연결이 끝난 입금입니다."
        elif item.get("transaction_type_label") != "입금":
            item["auto_match_note"] = "이 내역은 입금이 아니라 출금이라서 자동 확인 대상이 아닙니다."
        elif not (item.get("deposit_name") or "").strip():
            item["auto_match_note"] = "입금자명이 비어 있어서 누구의 입금인지 자동으로 판단할 수 없습니다."
        elif len(strict_candidates) == 1:
            item["auto_match_note"] = "조건에 맞는 예약이 1건이라 자동으로 연결할 수 있는 상태입니다."
        elif len(strict_candidates) > 1:
            item["auto_match_note"] = f"맞을 가능성이 있는 예약이 {len(strict_candidates)}건이라 실수 방지를 위해 자동으로 확정하지 않았습니다."
        elif candidates:
            item["auto_match_note"] = "금액은 비슷한 예약이 있지만 이름까지 정확히 같지 않아 자동으로 연결하지 않았습니다."
        else:
            item["auto_match_note"] = "지금 기준으로는 맞는 예약을 찾지 못했습니다. 수동매칭에서 직접 확인해주세요."
        formatted.append(item)

    return formatted


def get_bank_dashboard_summary():
    summary = {
        "is_enabled": False,
        "last_synced_at_display": "",
        "last_error_message": "",
        "total_transactions": 0,
        "pending_count": 0,
        "matched_count": 0,
        "unmatched_count": 0,
        "ignored_count": 0,
        "approved_billboard_count": 0,
    }

    setting = get_bank_setting_view()
    if setting:
        summary["is_enabled"] = bool(setting.get("is_active"))
        summary["last_synced_at_display"] = format_kst_datetime(setting.get("last_synced_at"))
        summary["last_error_message"] = setting.get("last_error_message") or ""
        summary["payment_amount_display"] = f"{int(setting.get('payment_amount') or 0):,}원"
    else:
        summary["payment_amount_display"] = "5,000원"

    transactions = _safe_fetch_rows("bank_transactions", params={"select": "id,status,is_billboard_approved"})
    summary["total_transactions"] = len(transactions)
    summary["pending_count"] = sum(1 for item in transactions if item.get("status") == "PENDING")
    summary["matched_count"] = sum(1 for item in transactions if item.get("status") == "MATCHED")
    summary["unmatched_count"] = sum(1 for item in transactions if item.get("status") == "UNMATCHED")
    summary["ignored_count"] = sum(1 for item in transactions if item.get("status") == "IGNORED")
    summary["approved_billboard_count"] = sum(
        1 for item in transactions if item.get("status") == "UNMATCHED" and item.get("is_billboard_approved")
    )
    return summary


def set_bank_transaction_billboard_approval(transaction_id, approved):
    patch_rows(
        "bank_transactions",
        {
            "is_billboard_approved": bool(approved),
            "billboard_posted_at": datetime.now(timezone.utc).isoformat() if approved else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        params={"id": f"eq.{transaction_id}"},
    )


def ignore_bank_transaction(transaction_id):
    patch_rows(
        "bank_transactions",
        {
            "status": "IGNORED",
            "is_billboard_approved": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        params={"id": f"eq.{transaction_id}"},
    )


def match_bank_transaction(transaction_id, reservation_id):
    return manual_match_transaction(transaction_id, reservation_id)