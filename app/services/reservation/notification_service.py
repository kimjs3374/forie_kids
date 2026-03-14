import requests
from flask import current_app


def _send_telegram_message(message):
    bot_token = (current_app.config.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (current_app.config.get("TELEGRAM_CHAT_ID") or "").strip()
    if not bot_token or not chat_id:
        return

    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": message},
        timeout=10,
    ).raise_for_status()


def send_telegram_reservation_alert(target_month, apt_dong, apt_ho, name):
    try:
        month_label = f"{int(str(target_month).split('-')[1])}월"
    except (TypeError, ValueError, IndexError):
        month_label = str(target_month)

    message = (
        "[포리에 실내놀이터]\n\n"
        "****예약알림****\n\n"
        f"{apt_dong}동 {apt_ho}호 {name}님이 {month_label} 예약신청 하셨습니다.\n"
        "입금 확인 후 안내바랍니다.\n\n"
        "https://kids.forie.kr/forie_admin/reservations"
    )
    _send_telegram_message(message)


def send_telegram_deposit_request_alert(apt_dong, apt_ho, name, content):
    message = (
        "[포리에 실내놀이터]\n\n"
        "****입금확인요청****\n\n"
        f"{apt_dong}동 {apt_ho}호 {name}님이 입금확인요청을 하셨습니다.\n"
        "관리자 페이지 내 입금확인요청 확인바랍니다.\n\n"
        f"요청내용 : {content.strip()}\n\n"
        "https://kids.forie.kr/forie_admin/payment-requests"
    )
    _send_telegram_message(message)
