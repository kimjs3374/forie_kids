from datetime import datetime, time, timedelta, timezone

from .supabase_service import delete_rows, fetch_rows, insert_row, patch_rows
from .reservation_service import month_status_label, split_apt_unit, status_label


KST = timezone(timedelta(hours=9))


def _format_kst_datetime(value):
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)[:16].replace("T", " ")


def _get_settings_row():
    settings = fetch_rows("settings", params={"select": "*", "id": "eq.1"})
    return settings[0] if settings else {"id": 1, "notice_text": "현재 공지사항이 없습니다.", "policy_json": {}}


def _get_policy_json():
    settings = _get_settings_row()
    return settings.get("policy_json") or {}


def _save_policy_json(policy_json):
    patch_rows("settings", {"policy_json": policy_json}, params={"id": "eq.1"})


def _set_month_password(target_month, password):
    policy_json = _get_policy_json()
    month_passwords = policy_json.get("month_passwords") or {}
    if password:
        month_passwords[target_month] = password
    else:
        month_passwords.pop(target_month, None)
    policy_json["month_passwords"] = month_passwords
    _save_policy_json(policy_json)


def _remove_month_password(target_month):
    policy_json = _get_policy_json()
    month_passwords = policy_json.get("month_passwords") or {}
    month_passwords.pop(target_month, None)
    policy_json["month_passwords"] = month_passwords
    _save_policy_json(policy_json)


def _set_payment_confirmed_at(reservation_id, confirmed_at):
    policy_json = _get_policy_json()
    confirmed_map = policy_json.get("reservation_payment_confirmed_at") or {}
    if confirmed_at:
        confirmed_map[str(reservation_id)] = confirmed_at
    else:
        confirmed_map.pop(str(reservation_id), None)
    policy_json["reservation_payment_confirmed_at"] = confirmed_map
    _save_policy_json(policy_json)


def _get_payment_confirmed_map():
    policy_json = _get_policy_json()
    return policy_json.get("reservation_payment_confirmed_at") or {}


def update_month_password(month_id, password):
    month = fetch_rows("reservation_months", params={"select": "target_month", "id": f"eq.{month_id}"})
    if not month:
        return
    _set_month_password(month[0]["target_month"], (password or "").strip())


def save_notice(notice_text):
    existing = fetch_rows("settings", params={"select": "id", "id": "eq.1"})
    payload = {"id": 1, "notice_text": notice_text.strip(), "updated_at": datetime.now(timezone.utc).isoformat()}
    if existing:
        patch_rows("settings", payload, params={"id": "eq.1"})
    else:
        insert_row("settings", payload)


def create_month(form):
    target_month = f"{form.target_year.data}-{form.target_month_num.data:02d}"
    open_at = datetime.combine(form.open_date.data, time(0, 0), tzinfo=timezone.utc)
    close_at = datetime.combine(form.close_date.data, time(23, 59), tzinfo=timezone.utc)
    created_month = insert_row(
        "reservation_months",
        {
            "target_month": target_month,
            "title": form.title.data.strip() if form.title.data else None,
            "open_at": open_at.isoformat(),
            "close_at": close_at.isoformat(),
            "max_reservations_per_household": 1,
        },
    )

    if created_month:
        month_id = created_month[0]["id"]
        insert_row(
            "reservation_slots",
            {
                "month_id": month_id,
                "play_date": form.open_date.data.isoformat(),
                "start_time": "00:00:00",
                "end_time": "23:59:00",
                "capacity": form.capacity.data,
                "status": "ACTIVE",
            },
        )
        _set_month_password(target_month, (form.access_password.data or "").strip())


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
    month_passwords = (_get_policy_json().get("month_passwords") or {})
    slot_map = {}
    for slot in slots:
        slot_map.setdefault(slot["month_id"], []).append(slot)
    for month in months:
        month["status_label"] = month_status_label(month)
        month_slots = slot_map.get(month["id"], [])
        month["capacity"] = month_slots[0]["capacity"] if month_slots else 0
        month["access_password"] = month_passwords.get(month["target_month"], "")
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
        _remove_month_password(previous_target_month)
    _set_month_password(target_month, (form.access_password.data or "").strip())


def delete_month(month_id):
    existing_month = fetch_rows("reservation_months", params={"select": "target_month", "id": f"eq.{month_id}"})
    delete_rows("reservation_months", params={"id": f"eq.{month_id}"})
    if existing_month:
        _remove_month_password(existing_month[0]["target_month"])


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
    confirmed_map = _get_payment_confirmed_map()
    for reservation in reservations:
        reservation["month"] = months.get(reservation["month_id"], {})
        reservation["slot"] = slots.get(reservation["slot_id"], {})
        reservation["status_label"] = status_label(reservation.get("status"))
        dong, ho = split_apt_unit(reservation.get("apt_unit"))
        reservation["apt_dong"] = dong
        reservation["apt_ho"] = ho
        reservation["payment_checked"] = reservation.get("status") == "PAYMENT_CONFIRMED"
        confirmed_at = reservation.get("payment_confirmed_at") or confirmed_map.get(str(reservation.get("id")), "")
        reservation["payment_confirmed_at_display"] = _format_kst_datetime(confirmed_at)
        reservation["created_at_display"] = _format_kst_datetime(reservation.get("created_at"))
    return reservations


def update_reservation_status(reservation_id, status):
    payload = {"status": status}
    if status == "PAYMENT_CONFIRMED":
        confirmed_at = datetime.now(timezone.utc).isoformat()
        _set_payment_confirmed_at(reservation_id, confirmed_at)
        try:
            patch_rows(
                "reservations",
                {"payment_confirmed_at": confirmed_at},
                params={"id": f"eq.{reservation_id}"},
            )
        except Exception:
            pass
    elif status == "CANCELLED" or status == "PENDING_PAYMENT":
        _set_payment_confirmed_at(reservation_id, None)
    patch_rows("reservations", payload, params={"id": f"eq.{reservation_id}"})