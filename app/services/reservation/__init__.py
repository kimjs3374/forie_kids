from ..shared import is_month_open, month_status_label, split_apt_unit, status_label
from .content_service import get_active_ticker_messages, get_notice_text
from .inquiry_service import (
    add_inquiry_reply,
    create_inquiry,
    delete_inquiry_message,
    inquiry_status_label,
    list_inquiries,
    update_inquiry_message,
)
from .month_service import get_months_with_slots
from .reservation_record_service import create_reservation, lookup_month_password, lookup_my_reservations

# Backward-compatible aliases
add_payment_request_reply = add_inquiry_reply
create_payment_request = create_inquiry
delete_payment_request_message = delete_inquiry_message
list_payment_requests = list_inquiries
payment_request_status_label = inquiry_status_label
update_payment_request_message = update_inquiry_message
