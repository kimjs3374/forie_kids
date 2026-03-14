"""Backward-compatible admin service facade.

기존 import 경로를 유지하면서 내부 구현은 도메인 패키지로 분리한다.
"""

from .admin.content_service import (
    create_ticker_message,
    delete_ticker_message,
    list_ticker_messages,
    save_notice,
    update_ticker_message,
)
from .admin.month_service import (
    _build_month_title,
    _create_month_record,
    create_month,
    create_slot,
    delete_month,
    ensure_next_month_reservation,
    list_months,
    update_month,
)
from .admin.password_service import (
    DEFAULT_MONTH_CAPACITY,
    VALID_MONTH_PASSWORD_COUNT,
    _allocate_unique_month_password,
    _generate_random_password,
    _get_month_password,
    _get_month_password_map,
    _get_used_passwords,
    _is_valid_month_password,
    _register_used_password,
    _remove_month_password,
    _reserve_password,
    _set_month_password,
    generate_unique_month_password,
    update_month_password,
)
from .admin.reservation_admin_service import list_reservations, update_reservation_status
from .shared import format_kst_datetime as _format_kst_datetime