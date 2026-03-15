from datetime import datetime, timezone

from flask import current_app

from ..bank.settings_service import (
    DEFAULT_PAYMENT_AMOUNT,
    get_bank_code_label,
    get_bank_setting,
    get_bank_setting_defaults_from_env,
)
from ..shared import build_apt_unit, format_kst_datetime, split_apt_unit, status_label
from ..supabase_service import SupabaseRequestError, call_rpc, fetch_rows, patch_rows
from .notification_service import send_telegram_auto_payment_confirmed_alert, send_telegram_reservation_alert


def _extract_reservation_error_message(exc):
    payload = getattr(exc, "response_data", {}) or {}
    for key in ("details", "message", "hint"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return "이용 신청 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."


def _build_reservation_submit_info(form, month):
    bank_setting = None
    try:
        bank_setting = get_bank_setting(include_decrypted=True)
    except Exception:
        current_app.logger.exception("예약 완료 안내용 은행 설정 조회에 실패했습니다. .env 기본값으로 대체합니다.")

    if bank_setting:
        account_number = str((bank_setting or {}).get("account_number") or "").strip()
        account_holder_name = str((bank_setting or {}).get("account_holder_name") or "").strip()
        bank_label = get_bank_code_label((bank_setting or {}).get("bank_code"))
    else:
        env_defaults = get_bank_setting_defaults_from_env()
        account_number = str(env_defaults.get("account_number") or "").strip()
        account_holder_name = str(env_defaults.get("account_holder_name") or "").strip()
        bank_label = str(env_defaults.get("bank_name") or "").strip()

    month_payment_amount = (month or {}).get("payment_amount")

    return {
        "target_month": month.get("target_month") or "",
        "apt_dong": form.apt_dong.data.strip(),
        "apt_ho": form.apt_ho.data.strip(),
        "name": form.name.data.strip(),
        "children_count": int(form.children_count.data),
        "payment_amount": int(month_payment_amount if month_payment_amount not in (None, "") else DEFAULT_PAYMENT_AMOUNT),
        "bank_name": bank_label,
        "account_number": account_number,
        "account_holder_name": account_holder_name,
        "has_bank_account": bool(account_number),
    }


def _auto_confirm_zero_amount_reservation(form, month, apt_unit):
    month_payment_amount = (month or {}).get("payment_amount")
    expected_amount = int(month_payment_amount if month_payment_amount not in (None, "") else DEFAULT_PAYMENT_AMOUNT)
    if expected_amount != 0:
        return

    reservations = fetch_rows(
        "reservations",
        params={
            "select": "id,status,month_id,apt_unit,name,created_at",
            "month_id": f"eq.{month['id']}",
            "apt_unit": f"eq.{apt_unit}",
            "name": f"eq.{form.name.data.strip()}",
            "order": "created_at.desc,id.desc",
            "limit": "1",
        },
    )
    if not reservations:
        return

    reservation = reservations[0]
    if reservation.get("status") == "PAYMENT_CONFIRMED":
        return

    now = datetime.now(timezone.utc).isoformat()
    patch_rows(
        "reservations",
        {
            "status": "PAYMENT_CONFIRMED",
            "payment_confirmed_at": now,
            "updated_at": now,
        },
        params={"id": f"eq.{reservation['id']}"},
    )

    try:
        send_telegram_auto_payment_confirmed_alert(
            month.get("target_month"),
            form.apt_dong.data.strip(),
            form.apt_ho.data.strip(),
            form.name.data.strip(),
        )
    except Exception:
        current_app.logger.exception("0원 예약 자동확정 텔레그램 알림 전송에 실패했습니다.")


def create_reservation(form):
    month_id = int(form.month_id.data)
    now = datetime.now(timezone.utc).isoformat()
    month_rows = fetch_rows(
        "reservation_months",
        params={"select": "id,target_month,payment_amount", "id": f"eq.{month_id}", "limit": "1"},
    )
    month = month_rows[0] if month_rows else None

    if not month:
        return False, "현재 신청 가능한 월이 아닙니다.", None

    phone = form.phone.data.strip()
    apt_unit = build_apt_unit(form.apt_dong.data, form.apt_ho.data)
    try:
        month_payment_amount = (month or {}).get("payment_amount")
        call_rpc(
            "create_reservation_atomic",
            {
                "p_month_id": month_id,
                "p_name": form.name.data.strip(),
                "p_apt_unit": apt_unit,
                "p_phone": phone,
                "p_children_count": int(form.children_count.data),
                "p_expected_amount": int(month_payment_amount if month_payment_amount not in (None, "") else DEFAULT_PAYMENT_AMOUNT),
                "p_consent_agreed": bool(form.consent_agreed.data),
                "p_consent_agreed_at": now if form.consent_agreed.data else None,
            },
        )
    except SupabaseRequestError as exc:
        current_app.logger.warning("예약 생성 RPC 실패: %s", exc)
        return False, _extract_reservation_error_message(exc), None

    try:
        send_telegram_reservation_alert(
            month.get("target_month"),
            form.apt_dong.data.strip(),
            form.apt_ho.data.strip(),
            form.name.data.strip(),
        )
    except Exception:
        current_app.logger.exception("텔레그램 예약 알림 전송에 실패했습니다.")

    _auto_confirm_zero_amount_reservation(form, month, apt_unit)

    return (
        True,
        "해당 월 이용 신청이 완료되었습니다. 입금 확인 후 해당 월에는 제한 없이 이용 가능합니다.",
        _build_reservation_submit_info(form, month),
    )


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
        reservation["expected_amount_display"] = f"{int(reservation.get('expected_amount') or 0):,}원"
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
