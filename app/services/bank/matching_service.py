import hashlib
import json
from datetime import datetime, timezone

from ..shared import KST, format_kst_datetime, parse_iso_datetime, split_apt_unit
from ..supabase_service import fetch_rows, insert_row, patch_rows


def normalize_name(value):
    return "".join(str(value or "").split())


def build_transaction_uid(raw_transaction):
    stable_payload = {
        "date": raw_transaction.get("date"),
        "time": raw_transaction.get("time"),
        "type": raw_transaction.get("type"),
        "amount": raw_transaction.get("amount"),
        "balance": raw_transaction.get("balance"),
        "description": raw_transaction.get("description"),
        "displayName": raw_transaction.get("displayName"),
        "counterparty": raw_transaction.get("counterparty"),
        "branch": raw_transaction.get("branch"),
        "memo": raw_transaction.get("memo"),
    }
    encoded = json.dumps(stable_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_transaction_datetime(raw_transaction):
    date_text = str(raw_transaction.get("date") or "").strip().replace("/", "-")
    if not date_text:
        return None
    time_text = str(raw_transaction.get("time") or "00:00:00").strip() or "00:00:00"
    dt = datetime.fromisoformat(f"{date_text}T{time_text}")
    return dt.replace(tzinfo=KST).astimezone(timezone.utc).isoformat()


def extract_deposit_name(raw_transaction):
    for field_name in ("counterparty", "memo", "displayName"):
        value = str(raw_transaction.get(field_name) or "").strip()
        if value:
            return value
    return ""


def _fetch_pending_reservations():
    return fetch_rows(
        "reservations",
        params={
            "select": "id,month_id,name,apt_unit,phone,status,created_at,expected_amount,payment_confirmed_at",
            "status": "eq.PENDING_PAYMENT",
            "order": "created_at.asc,id.asc",
        },
    )


def _fetch_month_order_map():
    return {
        item["id"]: item.get("target_month") or "9999-99"
        for item in fetch_rows("reservation_months", params={"select": "id,target_month"})
    }


def _reservation_sort_key(reservation, month_order_map):
    created_at = parse_iso_datetime(reservation.get("created_at")) or datetime.max.replace(tzinfo=timezone.utc)
    return (month_order_map.get(reservation.get("month_id"), "9999-99"), created_at, int(reservation.get("id") or 0))


def find_best_match_reservations(transaction, reservations=None, month_order_map=None):
    transaction_amount = int(transaction.get("amount") or 0)
    transaction_dt = parse_iso_datetime(transaction.get("transaction_date"))
    normalized_deposit_name = normalize_name(transaction.get("deposit_name"))

    if transaction_amount <= 0 or not normalized_deposit_name:
        return None

    reservations = reservations if reservations is not None else _fetch_pending_reservations()
    month_order_map = month_order_map if month_order_map is not None else _fetch_month_order_map()

    grouped_candidates = {}
    for reservation in reservations:
        if normalize_name(reservation.get("name")) != normalized_deposit_name:
            continue

        created_at = parse_iso_datetime(reservation.get("created_at"))
        if transaction_dt and created_at and transaction_dt < created_at:
            continue

        group_key = (
            normalize_name(reservation.get("name")),
            str(reservation.get("phone") or "").strip(),
            str(reservation.get("apt_unit") or "").strip(),
        )
        grouped_candidates.setdefault(group_key, []).append(reservation)

    matched_groups = []
    for group_key, group_reservations in grouped_candidates.items():
        ordered = sorted(group_reservations, key=lambda item: _reservation_sort_key(item, month_order_map))
        selected = []
        running_amount = 0
        for reservation in ordered:
            running_amount += int(reservation.get("expected_amount") or 0)
            selected.append(reservation)
            if running_amount == transaction_amount:
                strategy = "BUNDLE" if len(selected) > 1 else ("PARTIAL" if len(ordered) > 1 else "SINGLE")
                matched_groups.append(
                    {
                        "group_key": group_key,
                        "reservations": list(selected),
                        "strategy": strategy,
                    }
                )
                break
            if running_amount > transaction_amount:
                break

    if len(matched_groups) != 1:
        return None
    return matched_groups[0]


def _fetch_reservation_candidates(amount):
    if amount in (None, ""):
        return []
    return fetch_rows(
        "reservations",
        params={
            "select": "id,month_id,name,apt_unit,phone,status,created_at,expected_amount,payment_confirmed_at",
            "status": "eq.PENDING_PAYMENT",
            "expected_amount": f"eq.{int(amount)}",
            "order": "created_at.asc",
        },
    )


def find_candidate_reservations(transaction, require_name_match=False):
    transaction_dt = parse_iso_datetime(transaction.get("transaction_date"))
    normalized_deposit_name = normalize_name(transaction.get("deposit_name"))
    candidates = []

    for reservation in _fetch_reservation_candidates(transaction.get("amount")):
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
        candidates.append(item)

    candidates.sort(key=lambda item: (not item.get("name_matches"), item.get("created_at") or ""))
    return candidates


def _log_match(transaction_id, reservation_id, match_type, result, reason, created_by_admin_id=None):
    insert_row(
        "bank_match_logs",
        {
            "transaction_id": transaction_id,
            "reservation_id": reservation_id,
            "match_type": match_type,
            "result": result,
            "reason": reason,
            "created_by_admin_id": created_by_admin_id,
        },
    )


def _apply_match(transaction, reservations, match_type, reason, created_by_admin_id=None):
    reservation_list = reservations if isinstance(reservations, list) else [reservations]
    if not reservation_list:
        raise ValueError("매칭할 예약 정보가 없습니다.")

    now = datetime.now(timezone.utc).isoformat()
    payment_confirmed_at = transaction.get("transaction_date") or now

    for reservation in reservation_list:
        patch_rows(
            "reservations",
            {
                "status": "PAYMENT_CONFIRMED",
                "payment_confirmed_at": payment_confirmed_at,
                "updated_at": now,
            },
            params={"id": f"eq.{reservation['id']}"},
        )

    patch_rows(
        "bank_transactions",
        {
            "status": "MATCHED",
            "matched_reservation_id": reservation_list[0]["id"],
            "matched_at": now,
            "is_billboard_approved": False,
            "updated_at": now,
        },
        params={"id": f"eq.{transaction['id']}"},
    )
    for reservation in reservation_list:
        _log_match(
            transaction["id"],
            reservation["id"],
            match_type,
            "MATCHED",
            reason,
            created_by_admin_id=created_by_admin_id,
        )


def manual_match_transaction(transaction_id, reservation_id, created_by_admin_id=None):
    transactions = fetch_rows("bank_transactions", params={"select": "*", "id": f"eq.{transaction_id}"})
    if not transactions:
        raise ValueError("입금 거래를 찾을 수 없습니다.")

    reservations = fetch_rows(
        "reservations",
        params={"select": "id,status,expected_amount", "id": f"eq.{reservation_id}"},
    )
    if not reservations:
        raise ValueError("연결할 예약을 찾을 수 없습니다.")

    transaction = transactions[0]
    reservation = reservations[0]
    if reservation.get("status") == "CANCELLED":
        raise ValueError("취소된 예약에는 매칭할 수 없습니다.")
    if reservation.get("status") == "PAYMENT_CONFIRMED":
        raise ValueError("이미 입금 확인된 예약에는 다시 매칭할 수 없습니다.")
    if str(transaction.get("transaction_type") or "").lower() != "deposit":
        raise ValueError("입금 거래만 수동 매칭할 수 있습니다.")

    mismatch_note = ""
    if int(transaction.get("amount") or 0) != int(reservation.get("expected_amount") or 0):
        mismatch_note = " (금액 상이 건 수동 승인)"

    _apply_match(
        transaction,
        reservation,
        match_type="MANUAL",
        reason=f"관리자 수동 매칭{mismatch_note}",
        created_by_admin_id=created_by_admin_id,
    )
    return True


def auto_match_pending_transactions(transaction_ids=None):
    params = {"select": "*", "status": "eq.PENDING", "order": "transaction_date.asc,id.asc"}
    if transaction_ids:
        normalized_ids = [str(transaction_id) for transaction_id in transaction_ids]
        params["id"] = f"in.({','.join(normalized_ids)})"

    transactions = fetch_rows("bank_transactions", params=params)
    pending_reservations = _fetch_pending_reservations()
    month_order_map = _fetch_month_order_map()
    matched_count = 0
    unmatched_count = 0

    for transaction in transactions:
        if str(transaction.get("transaction_type") or "").lower() != "deposit":
            patch_rows(
                "bank_transactions",
                {"status": "IGNORED", "updated_at": datetime.now(timezone.utc).isoformat()},
                params={"id": f"eq.{transaction['id']}"},
            )
            continue

        best_match = find_best_match_reservations(
            transaction,
            reservations=pending_reservations,
            month_order_map=month_order_map,
        )
        if best_match:
            strategy = best_match["strategy"]
            reason = {
                "SINGLE": "자동 매칭 성공",
                "PARTIAL": "자동 부분 입금 매칭 (빠른 이용월 우선)",
                "BUNDLE": "자동 묶음 입금 매칭",
            }.get(strategy, "자동 매칭 성공")
            _apply_match(transaction, best_match["reservations"], match_type="AUTO", reason=reason)
            matched_ids = {reservation["id"] for reservation in best_match["reservations"]}
            pending_reservations = [item for item in pending_reservations if item.get("id") not in matched_ids]
            matched_count += len(best_match["reservations"])
            continue

        patch_rows(
            "bank_transactions",
            {"status": "UNMATCHED", "updated_at": datetime.now(timezone.utc).isoformat()},
            params={"id": f"eq.{transaction['id']}"},
        )
        unmatched_count += 1

    return {
        "processed_count": len(transactions),
        "matched_count": matched_count,
        "unmatched_count": unmatched_count,
    }