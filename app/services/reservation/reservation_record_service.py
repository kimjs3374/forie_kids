from datetime import datetime, timezone

from flask import current_app

from ..shared import build_apt_unit, format_kst_datetime, is_month_open, split_apt_unit, status_label
from ..supabase_service import fetch_rows, insert_row
from .month_service import get_months_with_slots
from .notification_service import send_telegram_reservation_alert


def create_reservation(form):
    month_id = int(form.month_id.data)
    now = datetime.now(timezone.utc).isoformat()
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
    apt_unit = build_apt_unit(form.apt_dong.data, form.apt_ho.data)
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
            "consent_agreed_at": now if form.consent_agreed.data else None,
            "status": "PENDING_PAYMENT",
        },
    )
    try:
        send_telegram_reservation_alert(
            month.get("target_month"),
            form.apt_dong.data.strip(),
            form.apt_ho.data.strip(),
            form.name.data.strip(),
        )
    except Exception:
        current_app.logger.exception("텔레그램 예약 알림 전송에 실패했습니다.")
    return True, "해당 월 이용 신청이 완료되었습니다. 입금 확인 후 해당 월에는 제한 없이 이용 가능합니다."


def lookup_my_reservations(name, phone, apt_dong, apt_ho):
    apt_unit = build_apt_unit(apt_dong, apt_ho)
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
    result = []
    for reservation in reservations:
        dong, ho = split_apt_unit(reservation.get("apt_unit"))
        reservation["month"] = months.get(reservation["month_id"], {})
        reservation["apt_dong"] = dong
        reservation["apt_ho"] = ho
        reservation["status_label"] = status_label(reservation.get("status"))
        reservation["payment_checked"] = reservation.get("status") == "PAYMENT_CONFIRMED"
        reservation["payment_confirmed_at_display"] = format_kst_datetime(reservation.get("payment_confirmed_at"))
        reservation["created_at_display"] = format_kst_datetime(reservation.get("created_at"))
        result.append(reservation)
    return result


def lookup_month_password(name, phone, apt_dong, apt_ho):
    reservations = lookup_my_reservations(name, phone, apt_dong, apt_ho)
    month_passwords = {
        item["target_month"]: item.get("access_password", "")
        for item in fetch_rows("month_passwords", params={"select": "target_month,access_password"})
    }
    matched = []
    for reservation in reservations:
        target_month = reservation.get("month", {}).get("target_month")
        if (
            reservation.get("status") == "PAYMENT_CONFIRMED"
            and target_month
            and month_passwords.get(target_month)
        ):
            reservation["access_password"] = month_passwords.get(target_month)
            matched.append(reservation)
    return matched
