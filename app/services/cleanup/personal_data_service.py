import logging
from calendar import monthrange
from datetime import date, datetime, time, timezone

from flask import current_app, has_app_context

from ..supabase_service import delete_rows, fetch_rows


DEFAULT_RETENTION_MONTHS = 12
DELETE_BATCH_SIZE = 200


def _logger():
    if has_app_context():
        return current_app.logger
    return logging.getLogger(__name__)


def _parse_timestamp(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def _subtract_months(value, months):
    year = value.year
    month = value.month - months
    while month <= 0:
        month += 12
        year -= 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _chunked(items, size=DELETE_BATCH_SIZE):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _delete_rows_by_ids(table_name, row_ids, id_column="id"):
    total_deleted = 0
    normalized_ids = [str(row_id) for row_id in dict.fromkeys(row_ids) if str(row_id).strip()]
    for chunk in _chunked(normalized_ids):
        deleted_rows = delete_rows(table_name, params={id_column: f"in.({','.join(chunk)})"})
        total_deleted += len(deleted_rows or [])
    return total_deleted


def _retention_cutoff(retention_months):
    now = datetime.now(timezone.utc)
    return _subtract_months(now, retention_months)


def _collect_expired_reservation_ids(cutoff_dt):
    reservations = fetch_rows("reservations", params={"select": "id,created_at,consent_agreed_at,slot_id"})
    slots = fetch_rows("reservation_slots", params={"select": "id,play_date"})
    slot_date_map = {slot["id"]: _parse_date(slot.get("play_date")) for slot in slots}

    expired_ids = []
    for reservation in reservations:
        created_at = _parse_timestamp(reservation.get("created_at"))
        consent_agreed_at = _parse_timestamp(reservation.get("consent_agreed_at"))
        play_date = slot_date_map.get(reservation.get("slot_id"))
        retention_base = consent_agreed_at or created_at
        if play_date:
            play_date_dt = datetime.combine(play_date, time.max, tzinfo=timezone.utc)
            if retention_base is None or play_date_dt > retention_base:
                retention_base = play_date_dt
        if retention_base and retention_base < cutoff_dt:
            expired_ids.append(reservation["id"])
    return expired_ids


def _collect_expired_deposit_request_ids(cutoff_dt):
    rows = fetch_rows("deposit_requests", params={"select": "id,created_at,consent_agreed_at"})
    expired_ids = []
    for row in rows:
        retention_base = _parse_timestamp(row.get("consent_agreed_at")) or _parse_timestamp(row.get("created_at"))
        if retention_base and retention_base < cutoff_dt:
            expired_ids.append(row["id"])
    return expired_ids


def _collect_expired_deposit_message_ids(cutoff_dt, expired_request_ids):
    message_ids = {
        row["id"]
        for row in fetch_rows(
            "deposit_request_messages",
            params={"select": "id", "created_at": f"lt.{cutoff_dt.isoformat()}"},
        )
    }

    for chunk in _chunked([str(request_id) for request_id in expired_request_ids]):
        rows = fetch_rows(
            "deposit_request_messages",
            params={"select": "id", "request_id": f"in.({','.join(chunk)})"},
        )
        message_ids.update(row["id"] for row in rows)

    return list(message_ids)


def delete_expired_personal_data(retention_months=None):
    logger = _logger()
    retention_months = int(
        retention_months or current_app.config.get("PERSONAL_DATA_RETENTION_MONTHS", DEFAULT_RETENTION_MONTHS)
    )
    if retention_months <= 0:
        raise ValueError("PERSONAL_DATA_RETENTION_MONTHS 는 1 이상의 정수여야 합니다.")

    cutoff_dt = _retention_cutoff(retention_months)
    summary = {
        "retention_months": retention_months,
        "cutoff": cutoff_dt.isoformat(),
        "reservations_deleted": 0,
        "deposit_requests_deleted": 0,
        "deposit_request_messages_deleted": 0,
        "errors": [],
    }

    try:
        expired_reservation_ids = _collect_expired_reservation_ids(cutoff_dt)
        summary["reservations_deleted"] = _delete_rows_by_ids("reservations", expired_reservation_ids)
        logger.info(
            "개인정보 정리 - reservations 삭제 완료 | cutoff=%s deleted=%s",
            summary["cutoff"],
            summary["reservations_deleted"],
        )
    except Exception as exc:
        logger.exception("개인정보 정리 - reservations 삭제 중 오류가 발생했습니다.")
        summary["errors"].append(f"reservations cleanup failed: {exc}")

    try:
        expired_request_ids = _collect_expired_deposit_request_ids(cutoff_dt)
        expired_message_ids = _collect_expired_deposit_message_ids(cutoff_dt, expired_request_ids)
        summary["deposit_request_messages_deleted"] = _delete_rows_by_ids(
            "deposit_request_messages",
            expired_message_ids,
        )
        summary["deposit_requests_deleted"] = _delete_rows_by_ids("deposit_requests", expired_request_ids)
        logger.info(
            "개인정보 정리 - deposit requests 삭제 완료 | cutoff=%s requests_deleted=%s messages_deleted=%s",
            summary["cutoff"],
            summary["deposit_requests_deleted"],
            summary["deposit_request_messages_deleted"],
        )
    except Exception as exc:
        logger.exception("개인정보 정리 - deposit requests 삭제 중 오류가 발생했습니다.")
        summary["errors"].append(f"deposit requests cleanup failed: {exc}")

    if summary["errors"]:
        logger.error("개인정보 정리 작업이 일부 실패했습니다. errors=%s", summary["errors"])
    else:
        logger.info(
            "개인정보 정리 작업 완료 | reservations_deleted=%s deposit_requests_deleted=%s deposit_request_messages_deleted=%s",
            summary["reservations_deleted"],
            summary["deposit_requests_deleted"],
            summary["deposit_request_messages_deleted"],
        )

    return summary
