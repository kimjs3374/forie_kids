"""Backward-compatible reservation service facade."""

from .reservation.content_service import get_active_ticker_messages, get_notice_text
from .reservation.month_service import get_months_with_slots
from .reservation.notification_service import (
    _send_telegram_message,
    send_telegram_deposit_request_alert as _send_telegram_deposit_request_alert,
    send_telegram_reservation_alert as _send_telegram_reservation_alert,
)
from .reservation.payment_request_service import (
    _build_request_key,
    _format_thread,
    add_payment_request_reply,
    create_payment_request,
    list_payment_requests,
    payment_request_status_label,
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