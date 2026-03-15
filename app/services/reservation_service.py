"""Backward-compatible reservation service facade."""

from .reservation.content_service import get_active_ticker_messages, get_notice_text
from .reservation.inquiry_service import (
    _build_request_key,
    _format_thread,
    add_inquiry_reply,
    create_inquiry,
    inquiry_status_label,
    list_inquiries,
)
from .reservation.month_service import get_months_with_slots
from .reservation.notification_service import (
    _send_telegram_message,
    send_telegram_inquiry_alert as _send_telegram_inquiry_alert,
    send_telegram_reservation_alert as _send_telegram_reservation_alert,
)
from .reservation.reservation_record_service import create_reservation, lookup_month_password, lookup_my_reservations
from .shared import (
    KST,
    format_date_display as _format_date_display,
    format_kst_datetime as _format_kst_datetime,
    is_month_open,
    month_status_label,
    parse_iso_date as _parse_iso_date,
    parse_iso_datetime as _parse_iso_datetime,
    split_apt_unit,
    status_label,
)

# Backward-compatible aliases
_send_telegram_deposit_request_alert = _send_telegram_inquiry_alert
add_payment_request_reply = add_inquiry_reply
create_payment_request = create_inquiry
list_payment_requests = list_inquiries
payment_request_status_label = inquiry_status_label