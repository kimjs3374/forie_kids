from datetime import datetime, timezone

from flask import current_app

from ..bank import get_bank_setting, manual_match_transaction, save_bank_setting, sync_bank_transactions
from ..bank.billboard_service import build_billboard_message
from ..bank.matching_service import normalize_name
from ..bank.settings_service import get_bank_code_label, update_bank_setting
from ..bank.sync_service import get_running_sync_run, list_recent_sync_runs
from ..shared import format_kst_datetime, parse_iso_datetime, split_apt_unit, status_label
from ..supabase_service import count_rows, fetch_rows, patch_rows


def _safe_fetch_rows(table_name, params=None):
    try:
        return fetch_rows(table_name, params=params)
    except Exception:
        current_app.logger.exception("은행 관리자 데이터 조회 실패 | table=%s params=%s", table_name, params)
        return []


def _safe_count_rows(table_name, params=None):
    try:
        return count_rows(table_name, params=params)
    except Exception:
        current_app.logger.exception("은행 관리자 데이터 카운트 실패 | table=%s params=%s", table_name, params)
        return 0


def _normalize_search_text(search_text):
    return (
        str(search_text or "")
        .strip()
        .replace(",", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace("*", " ")
    )


def _build_transaction_params(status_filter="all", search_text=None):
    params = {}
    if status_filter and status_filter != "all":
        params["status"] = f"eq.{status_filter.upper()}"

    normalized_search = _normalize_search_text(search_text)
    if normalized_search:
        wildcard = f"*{normalized_search}*"
        params["or"] = (
            f"(deposit_name.ilike.{wildcard},description.ilike.{wildcard},"
            f"display_name.ilike.{wildcard},counterparty.ilike.{wildcard})"
        )
    return params


def _format_sync_run(sync_run):
    item = dict(sync_run)
    item["started_at_display"] = format_kst_datetime(sync_run.get("started_at"))
    item["finished_at_display"] = format_kst_datetime(sync_run.get("finished_at"))
    return item


def get_bank_setting_view():
    try:
        return get_bank_setting(include_decrypted=False)
    except Exception:
        current_app.logger.exception("은행 설정 조회에 실패했습니다.")
        return None


def save_bank_settings(form):
    return save_bank_setting(
        bank_code=form.bank_code.data,
        account_holder_name=form.account_holder_name.data,
        account_number=form.account_number.data,
        account_password=form.account_password.data,
        resident_number=form.resident_number.data,
        is_active=bool(form.is_active.data),
    )


def run_bank_sync(lookback_days=30, force=True):
    return sync_bank_transactions(force=force, lookback_days=lookback_days)


def list_bank_sync_histories(limit=10):
    try:
        return [_format_sync_run(item) for item in list_recent_sync_runs(limit=limit)]
    except Exception:
        current_app.logger.exception("은행 동기화 이력 조회에 실패했습니다.")
        return []


def get_bank_transaction_counts(search_text=None):
    return {
        "all": _safe_count_rows("bank_transactions", params={**_build_transaction_params(search_text=search_text)}),
        "pending": _safe_count_rows(
            "bank_transactions",
            params={**_build_transaction_params(status_filter="pending", search_text=search_text)},
        ),
        "matched": _safe_count_rows(
            "bank_transactions",
            params={**_build_transaction_params(status_filter="matched", search_text=search_text)},
        ),
        "unmatched": _safe_count_rows(
            "bank_transactions",
            params={**_build_transaction_params(status_filter="unmatched", search_text=search_text)},
        ),
        "ignored": _safe_count_rows(
            "bank_transactions",
            params={**_build_transaction_params(status_filter="ignored", search_text=search_text)},
        ),
    }


def _reservation_map():
    reservations = _safe_fetch_rows(
        "reservations",
        params={"select": "id,name,apt_unit,phone,month_id,expected_amount,created_at,status,payment_confirmed_at"},
    )
    months = {
        item["id"]: item
        for item in _safe_fetch_rows("reservation_months", params={"select": "id,target_month,title,payment_amount"})
    }
    return reservations, months


def _build_candidate_reservations(transaction, reservations, month_map, require_name_match=False, limit=None):
    transaction_dt = parse_iso_datetime(transaction.get("transaction_date"))
    normalized_deposit_name = normalize_name(transaction.get("deposit_name"))
    transaction_amount = int(transaction.get("amount") or 0)
    candidates = []

    for reservation in reservations:
        if reservation.get("status") != "PENDING_PAYMENT":
            continue
        if int(reservation.get("expected_amount") or 0) != transaction_amount:
            continue

        created_at = parse_iso_datetime(reservation.get("created_at"))
        if transaction_dt and created_at and transaction_dt < created_at:
            continue

        reservation_name_matches = normalize_name(reservation.get("name")) == normalized_deposit_name if normalized_deposit_name else False
        if require_name_match and not reservation_name_matches:
            continue

        item = dict(reservation)
        item["name_matches"] = reservation_name_matches
        item["created_at_display"] = format_kst_datetime(reservation.get("created_at"))
        item["expected_amount_display"] = f"{int(reservation.get('expected_amount') or 0):,}원"
        dong, ho = split_apt_unit(reservation.get("apt_unit"))
        item["apt_dong"] = dong
        item["apt_ho"] = ho
        item["target_month"] = month_map.get(reservation.get("month_id"), {}).get("target_month") or "-"
        candidates.append(item)

    candidates.sort(key=lambda item: (not item.get("name_matches"), item.get("created_at") or "", item.get("id") or 0))
    return candidates[:limit] if limit is not None else candidates


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


def list_bank_transactions(status_filter="all", limit=100, offset=0, search_text=None):
    params = {
        "select": "*",
        "order": "transaction_date.desc,id.desc",
        "limit": str(limit),
        **_build_transaction_params(status_filter=status_filter, search_text=search_text),
    }
    if offset:
        params["offset"] = str(offset)

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
            strict_candidates = _build_candidate_reservations(
                transaction,
                pending_reservations,
                month_map,
                require_name_match=True,
            )
            candidates = _build_candidate_reservations(
                transaction,
                pending_reservations,
                month_map,
                require_name_match=False,
                limit=5,
            )
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
        "is_sync_running": False,
        "last_synced_at_display": "",
        "running_sync_started_at_display": "",
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
        running_run = get_running_sync_run(setting.get("id"))
        if running_run:
            summary["is_sync_running"] = True
            summary["running_sync_started_at_display"] = format_kst_datetime(running_run.get("started_at"))

    summary["total_transactions"] = _safe_count_rows("bank_transactions")
    summary["pending_count"] = _safe_count_rows("bank_transactions", params={"status": "eq.PENDING"})
    summary["matched_count"] = _safe_count_rows("bank_transactions", params={"status": "eq.MATCHED"})
    summary["unmatched_count"] = _safe_count_rows("bank_transactions", params={"status": "eq.UNMATCHED"})
    summary["ignored_count"] = _safe_count_rows("bank_transactions", params={"status": "eq.IGNORED"})
    summary["approved_billboard_count"] = _safe_count_rows(
        "bank_transactions",
        params={"status": "eq.UNMATCHED", "is_billboard_approved": "eq.true"},
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