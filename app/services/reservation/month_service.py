from datetime import datetime

from ..shared import KST, format_date_display, is_month_open, month_status_label, parse_iso_date
from ..supabase_service import fetch_rows


def get_months_with_slots():
    months = fetch_rows("reservation_months", params={"select": "*", "order": "target_month.asc"})
    slots = fetch_rows("reservation_slots", params={"select": "*", "order": "play_date.asc,start_time.asc"})
    reservations = fetch_rows(
        "reservations",
        params={"select": "id,slot_id,status,phone,apt_unit,month_id"},
    )

    reserved_by_slot = {}
    confirmed_by_slot = {}
    for reservation in reservations:
        status = reservation.get("status")
        if status != "CANCELLED":
            slot_id = reservation["slot_id"]
            reserved_by_slot[slot_id] = reserved_by_slot.get(slot_id, 0) + 1
            if status == "PAYMENT_CONFIRMED":
                confirmed_by_slot[slot_id] = confirmed_by_slot.get(slot_id, 0) + 1

    slot_map = {}
    for slot in slots:
        reserved_count = reserved_by_slot.get(slot["id"], 0)
        confirmed_count = confirmed_by_slot.get(slot["id"], 0)
        capacity = slot.get("capacity") or 0
        slot["reserved_count"] = reserved_count
        slot["confirmed_count"] = confirmed_count
        slot["remaining_capacity"] = max(capacity - reserved_count, 0)
        slot_map.setdefault(slot["month_id"], []).append(slot)

    today_kst = datetime.now(KST).date()
    for month in months:
        month["slots"] = slot_map.get(month["id"], [])
        month["payment_amount"] = int(month.get("payment_amount") if month.get("payment_amount") not in (None, "") else 5000)
        month["status_label"] = month_status_label(month)
        month["is_open"] = is_month_open(month)
        month["status_variant"] = {
            "예약대기": "draft",
            "예약중": "open",
            "예약완료": "closed",
        }.get(month["status_label"], "inactive")

        active_slots = [slot for slot in month["slots"] if slot.get("status") == "ACTIVE"]
        active_slot = active_slots[0] if active_slots else None
        slot_capacity = active_slot.get("capacity", 0) if active_slot else 0
        slot_reserved = active_slot.get("reserved_count", 0) if active_slot else 0
        slot_confirmed = active_slot.get("confirmed_count", 0) if active_slot else 0
        slot_remaining = active_slot.get("remaining_capacity", 0) if active_slot else 0
        reservation_closed = bool(active_slot and slot_remaining <= 0)
        capacity_ratio = (slot_reserved / slot_capacity) if slot_capacity else 0

        open_date = parse_iso_date(month.get("open_at"))
        close_date = parse_iso_date(month.get("close_at"))
        days_until_close = (close_date - today_kst).days if close_date else None
        is_capacity_imminent = bool(slot_capacity and capacity_ratio >= 0.8 and not reservation_closed)
        is_deadline_imminent = bool(
            month["is_open"] and days_until_close is not None and 0 <= days_until_close <= 3 and not reservation_closed
        )

        urgency_labels = []
        if reservation_closed:
            urgency_labels.append("정원마감")
        elif is_capacity_imminent:
            urgency_labels.append("정원임박")
        if is_deadline_imminent:
            urgency_labels.append("마감임박")

        month["slot_id"] = active_slot.get("id") if active_slot else None
        month["slot_capacity"] = slot_capacity
        month["slot_reserved"] = slot_reserved
        month["slot_confirmed"] = slot_confirmed
        month["slot_remaining"] = slot_remaining
        month["reservation_closed"] = reservation_closed
        month["reservation_disabled"] = bool(not month["is_open"] or reservation_closed or not active_slot)
        month["open_date_display"] = format_date_display(open_date)
        month["close_date_display"] = format_date_display(close_date)
        month["reservation_period_display"] = " ~ ".join(
            value for value in [month["open_date_display"], month["close_date_display"]] if value
        )
        month["is_capacity_imminent"] = is_capacity_imminent
        month["is_deadline_imminent"] = is_deadline_imminent
        month["urgency_labels"] = urgency_labels

    return months
