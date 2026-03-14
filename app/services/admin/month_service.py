from datetime import date, datetime, time, timezone

from ..shared import month_status_label
from ..supabase_service import delete_rows, fetch_rows, insert_row, patch_rows
from .password_service import (
    DEFAULT_MONTH_CAPACITY,
    _allocate_unique_month_password,
    _get_month_password,
    _get_month_password_map,
    _is_valid_month_password,
    _remove_month_password,
    _reserve_password,
    _set_month_password,
)


def _build_month_title(target_year, target_month_num):
    return f"{target_year}년 {target_month_num}월 예약"


def _create_month_record(target_year, target_month_num, open_date, close_date, capacity, access_password=None, title=None):
    target_month = f"{target_year}-{target_month_num:02d}"
    existing_month = fetch_rows("reservation_months", params={"select": "id,target_month", "target_month": f"eq.{target_month}"})
    if existing_month:
        return existing_month[0], False

    open_at = datetime.combine(open_date, time(0, 0), tzinfo=timezone.utc)
    close_at = datetime.combine(close_date, time(23, 59), tzinfo=timezone.utc)
    if (access_password or "").strip():
        final_password = str(access_password).strip().zfill(4)
        if not _is_valid_month_password(final_password):
            raise ValueError("비밀번호는 같은 숫자가 3개 이상 반복될 수 없습니다.")
        if not _reserve_password(final_password):
            raise ValueError("이미 사용했던 비밀번호입니다. 랜덤생성으로 다시 시도해주세요.")
    else:
        final_password = _allocate_unique_month_password()

    final_title = (title or "").strip() or _build_month_title(target_year, target_month_num)
    created_month = insert_row(
        "reservation_months",
        {
            "target_month": target_month,
            "title": final_title,
            "open_at": open_at.isoformat(),
            "close_at": close_at.isoformat(),
            "max_reservations_per_household": 1,
        },
    )
    if not created_month:
        return None, False

    month_id = created_month[0]["id"]
    insert_row(
        "reservation_slots",
        {
            "month_id": month_id,
            "play_date": date(target_year, target_month_num, 1).isoformat(),
            "start_time": "00:00:00",
            "end_time": "23:59:00",
            "capacity": capacity,
            "status": "ACTIVE",
        },
    )
    _set_month_password(target_month, final_password)
    created_month[0]["access_password"] = final_password
    return created_month[0], True


def ensure_next_month_reservation(today=None):
    from ..shared import KST

    now_kst = today.astimezone(KST) if today else datetime.now(KST)
    if now_kst.day != 1:
        return None

    target_year = now_kst.year + (1 if now_kst.month == 12 else 0)
    target_month_num = 1 if now_kst.month == 12 else now_kst.month + 1
    _, created = _create_month_record(
        target_year=target_year,
        target_month_num=target_month_num,
        open_date=date(now_kst.year, now_kst.month, 20),
        close_date=date(target_year, target_month_num, 15),
        capacity=DEFAULT_MONTH_CAPACITY,
    )
    return created


def create_month(form):
    _create_month_record(
        target_year=form.target_year.data,
        target_month_num=form.target_month_num.data,
        open_date=form.open_date.data,
        close_date=form.close_date.data,
        capacity=form.capacity.data,
        title=form.title.data,
    )


def create_slot(form):
    insert_row(
        "reservation_slots",
        {
            "month_id": form.month_id.data,
            "play_date": form.play_date.data.isoformat(),
            "start_time": form.start_time.data.strftime("%H:%M:%S"),
            "end_time": form.end_time.data.strftime("%H:%M:%S"),
            "capacity": form.capacity.data,
            "status": "ACTIVE",
        },
    )


def list_months():
    months = fetch_rows("reservation_months", params={"select": "*", "order": "target_month.desc"})
    slots = fetch_rows("reservation_slots", params={"select": "id,month_id,capacity,status"})
    reservations = fetch_rows("reservations", params={"select": "month_id,status"})
    month_passwords = _get_month_password_map()
    slot_map = {}
    reservation_summary = {}

    for slot in slots:
        slot_map.setdefault(slot["month_id"], []).append(slot)

    for reservation in reservations:
        month_id = reservation.get("month_id")
        if not month_id:
            continue
        summary = reservation_summary.setdefault(month_id, {"applied": 0, "confirmed": 0})
        if reservation.get("status") != "CANCELLED":
            summary["applied"] += 1
            if reservation.get("status") == "PAYMENT_CONFIRMED":
                summary["confirmed"] += 1

    for month in months:
        month["status_label"] = month_status_label(month)
        month_slots = slot_map.get(month["id"], [])
        month["capacity"] = month_slots[0]["capacity"] if month_slots else 0
        month["access_password"] = month_passwords.get(month["target_month"], "")
        summary = reservation_summary.get(month["id"], {})
        month["applied_count"] = summary.get("applied", 0)
        month["confirmed_count"] = summary.get("confirmed", 0)
    return months


def update_month(month_id, form):
    target_month = f"{form.target_year.data}-{form.target_month_num.data:02d}"
    existing_month = fetch_rows("reservation_months", params={"select": "target_month", "id": f"eq.{month_id}"})
    previous_target_month = existing_month[0]["target_month"] if existing_month else target_month
    open_at = datetime.combine(form.open_date.data, time(0, 0), tzinfo=timezone.utc)
    close_at = datetime.combine(form.close_date.data, time(23, 59), tzinfo=timezone.utc)

    patch_rows(
        "reservation_months",
        {
            "target_month": target_month,
            "title": form.title.data.strip() if form.title.data else None,
            "open_at": open_at.isoformat(),
            "close_at": close_at.isoformat(),
        },
        params={"id": f"eq.{month_id}"},
    )

    slots = fetch_rows("reservation_slots", params={"select": "id", "month_id": f"eq.{month_id}", "order": "id.asc"})
    if slots:
        patch_rows("reservation_slots", {"capacity": form.capacity.data}, params={"id": f"eq.{slots[0]['id']}"})

    if previous_target_month != target_month:
        current_entry = _get_month_password(previous_target_month)
        current_password = current_entry.get("access_password", "") if current_entry else ""
        _remove_month_password(previous_target_month)
        if current_password:
            _set_month_password(target_month, current_password)


def delete_month(month_id):
    existing_month = fetch_rows("reservation_months", params={"select": "target_month", "id": f"eq.{month_id}"})
    delete_rows("reservation_months", params={"id": f"eq.{month_id}"})
    if existing_month:
        _remove_month_password(existing_month[0]["target_month"])
