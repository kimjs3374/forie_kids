from datetime import datetime, timezone

from ..shared import format_kst_datetime, split_apt_unit, status_label
from ..supabase_service import count_rows, fetch_rows, patch_rows


RESERVATION_SELECT_COLUMNS = (
    "id,month_id,slot_id,name,apt_unit,phone,children_count,expected_amount,"
    "status,payment_confirmed_at,created_at"
)


def _build_in_filter(values):
    normalized = [str(int(value)) for value in values if str(value).strip()]
    if not normalized:
        return None
    return f"in.({','.join(normalized)})"


def _normalize_search_text(search_text):
    return (
        str(search_text or "")
        .strip()
        .replace(",", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace("*", " ")
    )


def _build_reservation_params(status=None, search_text=None):
    params = {}
    if status:
        params["status"] = f"eq.{status}"

    normalized_search = _normalize_search_text(search_text)
    if normalized_search:
        wildcard = f"*{normalized_search}*"
        params["or"] = f"(name.ilike.{wildcard},phone.ilike.{wildcard},apt_unit.ilike.{wildcard})"
    return params


def _format_reservations(reservations):
    month_ids = sorted({item.get("month_id") for item in reservations if item.get("month_id")})
    slot_ids = sorted({item.get("slot_id") for item in reservations if item.get("slot_id")})

    months = {}
    if month_ids:
        months = {
            item["id"]: item
            for item in fetch_rows(
                "reservation_months",
                params={"select": "id,target_month", "id": _build_in_filter(month_ids)},
            )
        }

    slots = {}
    if slot_ids:
        slots = {
            item["id"]: item
            for item in fetch_rows(
                "reservation_slots",
                params={
                    "select": "id,play_date,start_time,end_time,month_id",
                    "id": _build_in_filter(slot_ids),
                    "order": "play_date.asc,start_time.asc",
                },
            )
        }

    for reservation in reservations:
        reservation["month"] = months.get(reservation["month_id"], {})
        reservation["slot"] = slots.get(reservation["slot_id"], {})
        reservation["status_label"] = status_label(reservation.get("status"))
        dong, ho = split_apt_unit(reservation.get("apt_unit"))
        reservation["apt_dong"] = dong
        reservation["apt_ho"] = ho
        reservation["payment_checked"] = reservation.get("status") == "PAYMENT_CONFIRMED"
        reservation["expected_amount_display"] = f"{int(reservation.get('expected_amount') or 0):,}원"
        reservation["payment_confirmed_at_display"] = format_kst_datetime(reservation.get("payment_confirmed_at"))
        reservation["created_at_display"] = format_kst_datetime(reservation.get("created_at"))
    return reservations


def list_reservations(status=None, limit=None, offset=0, search_text=None):
    params = {
        "select": RESERVATION_SELECT_COLUMNS,
        "order": "created_at.desc",
        **_build_reservation_params(status=status, search_text=search_text),
    }
    if limit is not None:
        params["limit"] = str(limit)
    if offset:
        params["offset"] = str(offset)

    reservations = fetch_rows("reservations", params=params)
    return _format_reservations(reservations)


def get_reservation_counts(search_text=None):
    return {
        "all": count_rows("reservations", params={**_build_reservation_params(search_text=search_text)}),
        "confirmed": count_rows(
            "reservations",
            params={**_build_reservation_params(status="PAYMENT_CONFIRMED", search_text=search_text)},
        ),
        "pending": count_rows(
            "reservations",
            params={**_build_reservation_params(status="PENDING_PAYMENT", search_text=search_text)},
        ),
    }


def list_recent_reservations(limit=10):
    return list_reservations(limit=limit)


def update_reservation_status(reservation_id, status):
    payload = {"status": status}
    if status == "PAYMENT_CONFIRMED":
        payload["payment_confirmed_at"] = datetime.now(timezone.utc).isoformat()
    elif status in {"CANCELLED", "PENDING_PAYMENT"}:
        payload["payment_confirmed_at"] = None
    patch_rows("reservations", payload, params={"id": f"eq.{reservation_id}"})
