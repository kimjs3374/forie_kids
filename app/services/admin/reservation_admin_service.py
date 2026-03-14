from datetime import datetime, timezone

from ..shared import format_kst_datetime, split_apt_unit, status_label
from ..supabase_service import fetch_rows, patch_rows


def list_reservations():
    months = {item["id"]: item for item in fetch_rows("reservation_months", params={"select": "id,target_month"})}
    slots = {
        item["id"]: item
        for item in fetch_rows(
            "reservation_slots",
            params={"select": "id,play_date,start_time,end_time,month_id", "order": "play_date.asc,start_time.asc"},
        )
    }
    reservations = fetch_rows("reservations", params={"select": "*", "order": "created_at.desc"})
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


def update_reservation_status(reservation_id, status):
    payload = {"status": status}
    if status == "PAYMENT_CONFIRMED":
        payload["payment_confirmed_at"] = datetime.now(timezone.utc).isoformat()
    elif status in {"CANCELLED", "PENDING_PAYMENT"}:
        payload["payment_confirmed_at"] = None
    patch_rows("reservations", payload, params={"id": f"eq.{reservation_id}"})
