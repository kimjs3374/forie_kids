from datetime import datetime, timedelta, timezone

from ..shared import KST, parse_iso_datetime
from ..supabase_service import fetch_rows, insert_row, patch_rows
from .api_client import AccountNotRegisteredError, fetch_transactions, register_account
from .matching_service import auto_match_pending_transactions, build_transaction_datetime, build_transaction_uid, extract_deposit_name
from .settings_service import get_active_bank_setting, update_bank_setting


SYNC_PAUSE_START_HOUR = 2
SYNC_PAUSE_END_HOUR = 7


def is_bank_sync_window_open(now=None):
    now_kst = now.astimezone(KST) if now else datetime.now(KST)
    return not (SYNC_PAUSE_START_HOUR <= now_kst.hour < SYNC_PAUSE_END_HOUR)


def _build_sync_dates(setting, lookback_days):
    now_kst = datetime.now(KST)
    sync_cursor = parse_iso_datetime(setting.get("sync_cursor_at"))
    end_date = now_kst.date()
    if sync_cursor:
        start_date = sync_cursor.astimezone(KST).date()
    else:
        start_date = end_date - timedelta(days=max(int(lookback_days) - 1, 0))
    return start_date, end_date


def _create_sync_run(setting_id, start_date, end_date):
    rows = insert_row(
        "bank_sync_runs",
        {
            "bank_setting_id": setting_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "RUNNING",
            "requested_from": start_date.isoformat(),
            "requested_to": end_date.isoformat(),
        },
    )
    return rows[0] if rows else None


def _finish_sync_run(run_id, **payload):
    update_payload = dict(payload)
    update_payload["finished_at"] = datetime.now(timezone.utc).isoformat()
    patch_rows("bank_sync_runs", update_payload, params={"id": f"eq.{run_id}"})


def _transaction_exists(transaction_uid):
    return bool(fetch_rows("bank_transactions", params={"select": "id", "transaction_uid": f"eq.{transaction_uid}"}))


def _ingest_transactions(setting, raw_transactions):
    inserted_ids = []
    latest_seen_at = parse_iso_datetime(setting.get("sync_cursor_at"))
    sync_cursor = parse_iso_datetime(setting.get("sync_cursor_at"))

    for item in raw_transactions:
        transaction_date = build_transaction_datetime(item)
        parsed_transaction_date = parse_iso_datetime(transaction_date)
        if parsed_transaction_date and (latest_seen_at is None or parsed_transaction_date > latest_seen_at):
            latest_seen_at = parsed_transaction_date

        if sync_cursor and parsed_transaction_date and parsed_transaction_date <= sync_cursor:
            continue

        transaction_uid = build_transaction_uid(item)
        if _transaction_exists(transaction_uid):
            continue

        transaction_type = str(item.get("type") or "").lower()
        deposit_name = extract_deposit_name(item)
        rows = insert_row(
            "bank_transactions",
            {
                "bank_setting_id": setting["id"],
                "bank_code": setting.get("bank_code"),
                "transaction_uid": transaction_uid,
                "deposit_name": deposit_name or "",
                "amount": int(item.get("amount") or 0),
                "transaction_date": transaction_date,
                "description": item.get("description") or None,
                "display_name": item.get("displayName") or None,
                "counterparty": item.get("counterparty") or None,
                "balance": int(item.get("balance") or 0),
                "transaction_type": transaction_type,
                "status": "PENDING" if transaction_type == "deposit" else "IGNORED",
                "raw_json": item,
            },
        )
        if rows:
            inserted_ids.append(rows[0]["id"])

    return inserted_ids, latest_seen_at


def list_recent_sync_runs(limit=10):
    return fetch_rows(
        "bank_sync_runs",
        params={"select": "*", "order": "started_at.desc,id.desc", "limit": str(limit)},
    )


def sync_bank_transactions(force=False, lookback_days=30):
    setting = get_active_bank_setting(include_decrypted=True)
    if not setting:
        return {
            "status": "SKIPPED",
            "reason": "활성화된 은행 계좌 설정이 없습니다.",
            "fetched_count": 0,
            "inserted_count": 0,
            "matched_count": 0,
            "unmatched_count": 0,
        }

    if not force and not is_bank_sync_window_open():
        return {
            "status": "SKIPPED",
            "reason": "02:00~07:00 KST 자동 호출 중지 시간입니다.",
            "fetched_count": 0,
            "inserted_count": 0,
            "matched_count": 0,
            "unmatched_count": 0,
        }

    start_date, end_date = _build_sync_dates(setting, lookback_days)
    sync_run = _create_sync_run(setting["id"], start_date, end_date)

    try:
        try:
            response_payload = fetch_transactions(setting, start_date, end_date)
        except AccountNotRegisteredError:
            register_account(setting)
            update_bank_setting(setting["id"], {"account_registered_at": datetime.now(timezone.utc).isoformat()})
            response_payload = fetch_transactions(setting, start_date, end_date)

        raw_transactions = response_payload.get("transactions") or []
        inserted_ids, latest_seen_at = _ingest_transactions(setting, raw_transactions)
        matching_summary = auto_match_pending_transactions(inserted_ids)

        update_bank_setting(
            setting["id"],
            {
                "sync_cursor_at": latest_seen_at.isoformat() if latest_seen_at else setting.get("sync_cursor_at"),
                "last_synced_at": datetime.now(timezone.utc).isoformat(),
                "last_error_message": None,
            },
        )

        if sync_run:
            _finish_sync_run(
                sync_run["id"],
                status="SUCCESS",
                fetched_count=len(raw_transactions),
                inserted_count=len(inserted_ids),
                matched_count=matching_summary["matched_count"],
                unmatched_count=matching_summary["unmatched_count"],
                error_message=None,
            )

        return {
            "status": "SUCCESS",
            "reason": "정상 동기화 완료",
            "fetched_count": len(raw_transactions),
            "inserted_count": len(inserted_ids),
            "matched_count": matching_summary["matched_count"],
            "unmatched_count": matching_summary["unmatched_count"],
        }
    except Exception as exc:
        if sync_run:
            _finish_sync_run(sync_run["id"], status="FAILED", error_message=str(exc)[:500])
        update_bank_setting(setting["id"], {"last_error_message": str(exc)[:500]})
        raise