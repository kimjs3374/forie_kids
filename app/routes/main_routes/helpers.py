def _get_apartment_validation_error(form):
    apt_dong_errors = getattr(form, "apt_dong", None).errors if getattr(form, "apt_dong", None) else []
    apt_ho_errors = getattr(form, "apt_ho", None).errors if getattr(form, "apt_ho", None) else []
    return (apt_dong_errors + apt_ho_errors)[0] if (apt_dong_errors or apt_ho_errors) else ""


def _build_month_payload(month):
    return {
        "id": month["id"],
        "target_month": month.get("target_month"),
        "title": month.get("title"),
        "status": month.get("status_variant") or month.get("status"),
        "status_variant": month.get("status_variant") or month.get("status"),
        "status_label": month.get("status_label"),
        "is_open": month.get("is_open"),
        "reservation_closed": bool(month.get("reservation_closed")),
        "reservation_disabled": bool(month.get("reservation_disabled")),
        "slot_id": month.get("slot_id"),
        "slot_capacity": month.get("slot_capacity", 0),
        "slot_remaining": month.get("slot_remaining", 0),
        "slot_reserved": month.get("slot_reserved", 0),
        "slot_confirmed": month.get("slot_confirmed", 0),
        "open_date_display": month.get("open_date_display", ""),
        "close_date_display": month.get("close_date_display", ""),
        "reservation_period_display": month.get("reservation_period_display", ""),
        "urgency_labels": month.get("urgency_labels", []),
        "is_capacity_imminent": bool(month.get("is_capacity_imminent")),
        "is_deadline_imminent": bool(month.get("is_deadline_imminent")),
    }
