from datetime import datetime, timedelta, timezone

from .supabase_service import fetch_rows, insert_row


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


def _get_policy_json():
    settings = fetch_rows("settings", params={"select": "policy_json", "id": "eq.1"})
    if settings:
        return settings[0].get("policy_json") or {}
    return {}


def _get_payment_confirmed_map():
    policy_json = _get_policy_json()
    return policy_json.get("reservation_payment_confirmed_at") or {}


def get_notice_text():
    settings = fetch_rows("settings", params={"select": "*", "id": "eq.1"})
    if settings:
        return settings[0].get("notice_text") or "현재 공지사항이 없습니다."
    return "현재 공지사항이 없습니다."


def status_label(status):
    return {
        "ACTIVE": "사용가능",
        "INACTIVE": "비활성",
        "PENDING_PAYMENT": "예약대기",
        "PAYMENT_CONFIRMED": "예약확정",
        "CANCELLED": "취소",
    }.get(status, status)


def month_status_label(month):
    now = datetime.now(timezone.utc)
    open_at = datetime.fromisoformat(month["open_at"].replace("Z", "+00:00"))
    close_at = datetime.fromisoformat(month["close_at"].replace("Z", "+00:00"))
    if now < open_at:
        return "예약대기"
    if open_at <= now <= close_at:
        return "예약중"
    return "예약완료"


def is_month_open(month):
    now = datetime.now(timezone.utc)
    open_at = datetime.fromisoformat(month["open_at"].replace("Z", "+00:00"))
    close_at = datetime.fromisoformat(month["close_at"].replace("Z", "+00:00"))
    return open_at <= now <= close_at


def get_months_with_slots():
    months = fetch_rows("reservation_months", params={"select": "*", "order": "target_month.asc"})
    slots = fetch_rows("reservation_slots", params={"select": "*", "order": "play_date.asc,start_time.asc"})
    reservations = fetch_rows(
        "reservations",
        params={"select": "id,slot_id,status,phone,apt_unit,month_id"},
    )

    reserved_by_slot = {}
    for reservation in reservations:
        if reservation.get("status") != "CANCELLED":
            reserved_by_slot[reservation["slot_id"]] = reserved_by_slot.get(reservation["slot_id"], 0) + 1

    slot_map = {}
    for slot in slots:
        slot["remaining_capacity"] = max((slot.get("capacity") or 0) - reserved_by_slot.get(slot["id"], 0), 0)
        slot_map.setdefault(slot["month_id"], []).append(slot)

    for month in months:
        month["slots"] = slot_map.get(month["id"], [])
        month["status_label"] = month_status_label(month)
        month["is_open"] = is_month_open(month)

    return months


def create_reservation(form):
    month_id = int(form.month_id.data)
    months = get_months_with_slots()
    month = next((month for month in months if month["id"] == month_id), None)
    slot = next((slot for slot in (month or {}).get("slots", []) if slot.get("status") == "ACTIVE"), None)

    if not month:
        return False, "현재 신청 가능한 월이 아닙니다."
    if not is_month_open(month):
        return False, "현재 신청 접수 기간이 아닙니다."
    if not slot and month:
        fallback_slot = insert_row(
            "reservation_slots",
            {
                "month_id": month_id,
                "play_date": month["open_at"][:10],
                "start_time": "00:00:00",
                "end_time": "23:59:00",
                "capacity": 9999,
                "status": "ACTIVE",
            },
        )
        if fallback_slot:
            slot = fallback_slot[0]

    if not slot:
        return False, "해당 월 이용 신청용 기본 이용 정보 생성에 실패했습니다. 관리자에게 문의해주세요."
    if slot.get("remaining_capacity", 0) <= 0:
        return False, "해당 월 신청 정원이 모두 마감되었습니다. 더 이상 신청할 수 없습니다."

    phone = form.phone.data.strip()
    apt_unit = f"{form.apt_dong.data.strip()}동 {form.apt_ho.data.strip()}호"
    monthly_reservations = fetch_rows(
        "reservations",
        params={"select": "id,phone,apt_unit,status", "month_id": f"eq.{month_id}", "status": "neq.CANCELLED"},
    )
    if any(item.get("phone") == phone or item.get("apt_unit") == apt_unit for item in monthly_reservations):
        return False, "해당 월 이용 신청은 세대당 1회만 가능합니다. 입금 확인 후 해당 월 자유롭게 이용할 수 있습니다."

    insert_row(
        "reservations",
        {
            "month_id": month_id,
            "slot_id": slot["id"],
            "name": form.name.data.strip(),
            "apt_unit": apt_unit,
            "phone": phone,
            "children_count": form.children_count.data,
            "consent_agreed": bool(form.consent_agreed.data),
            "status": "PENDING_PAYMENT",
        },
    )
    return True, "해당 월 이용 신청이 완료되었습니다. 입금 확인 후 해당 월에는 제한 없이 이용 가능합니다."


def split_apt_unit(apt_unit):
    value = apt_unit or ""
    if "동" in value and "호" in value:
        try:
            dong, rest = value.split("동", 1)
            ho = rest.replace("호", "").strip()
            return dong.strip(), ho
        except ValueError:
            return value, ""
    return value, ""


def lookup_my_reservations(name, phone, apt_dong, apt_ho):
    apt_unit = f"{apt_dong.strip()}동 {apt_ho.strip()}호"
    reservations = fetch_rows(
        "reservations",
        params={
            "select": "*",
            "name": f"eq.{name.strip()}",
            "phone": f"eq.{phone.strip()}",
            "apt_unit": f"eq.{apt_unit}",
            "order": "created_at.desc",
        },
    )
    months = {item["id"]: item for item in fetch_rows("reservation_months", params={"select": "id,target_month,title"})}
    confirmed_map = _get_payment_confirmed_map()
    result = []
    for reservation in reservations:
        dong, ho = split_apt_unit(reservation.get("apt_unit"))
        reservation["month"] = months.get(reservation["month_id"], {})
        reservation["apt_dong"] = dong
        reservation["apt_ho"] = ho
        reservation["status_label"] = status_label(reservation.get("status"))
        reservation["payment_checked"] = reservation.get("status") == "PAYMENT_CONFIRMED"
        confirmed_at = reservation.get("payment_confirmed_at") or confirmed_map.get(str(reservation.get("id")), "")
        reservation["payment_confirmed_at_display"] = _format_kst_datetime(confirmed_at)
        reservation["created_at_display"] = _format_kst_datetime(reservation.get("created_at"))
        result.append(reservation)
    return result


def lookup_month_password(name, phone, apt_dong, apt_ho):
    reservations = lookup_my_reservations(name, phone, apt_dong, apt_ho)
    current_month = datetime.now().strftime("%Y-%m")
    month_passwords = (_get_policy_json().get("month_passwords") or {})
    matched = []
    for reservation in reservations:
        target_month = reservation.get("month", {}).get("target_month")
        if (
            target_month == current_month
            and reservation.get("status") == "PAYMENT_CONFIRMED"
            and month_passwords.get(target_month)
        ):
            reservation["access_password"] = month_passwords.get(target_month)
            matched.append(reservation)
    return matched