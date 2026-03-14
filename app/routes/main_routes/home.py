from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for

from ...forms import ReservationForm, ReservationLookupForm, TickerMessageForm
from ...services.admin import list_ticker_messages
from ...services.reservation import (
    create_reservation,
    get_active_ticker_messages,
    get_months_with_slots,
    get_notice_text,
)
from ..admin_routes.decorators import is_admin_session_authenticated
from . import main_bp
from .helpers import _build_month_payload, _get_apartment_validation_error


@main_bp.route("/", methods=["GET", "POST"])
def index():
    months = get_months_with_slots()
    selected_month_id = request.args.get("month_id", type=int)
    selected_month = next((month for month in months if month["id"] == selected_month_id), None)
    if not selected_month and months:
        selected_month = months[0]

    form = ReservationForm()
    apt_validation_error = ""
    if selected_month:
        active_slots = [slot for slot in selected_month.get("slots", []) if slot.get("status") == "ACTIVE"]
        form.month_id.data = str(selected_month["id"])
        if active_slots:
            form.slot_id.data = str(active_slots[0]["id"])

    if form.validate_on_submit():
        success, message = create_reservation(form)
        flash(message, "success" if success else "danger")
        return redirect(url_for("main.index", month_id=form.month_id.data, submitted=1 if success else 0))
    if request.method == "POST":
        apt_validation_error = _get_apartment_validation_error(form)
        if not apt_validation_error:
            flash("입력값을 다시 확인해주세요. 모든 필수 항목을 입력해야 합니다.", "danger")

    lookup_form = ReservationLookupForm()
    ticker_messages = get_active_ticker_messages()
    is_admin_authenticated = is_admin_session_authenticated()
    ticker_form = TickerMessageForm() if is_admin_authenticated else None
    ticker_manage_messages = list_ticker_messages() if is_admin_authenticated else []
    reservation_closed = bool((selected_month or {}).get("reservation_closed"))
    reservation_disabled = bool((selected_month or {}).get("reservation_disabled"))

    return render_template(
        "index.html",
        months=months,
        selected_month=selected_month,
        notice_text=get_notice_text(),
        ticker_messages=ticker_messages,
        ticker_manage_messages=ticker_manage_messages,
        ticker_form=ticker_form,
        reservation_closed=reservation_closed,
        reservation_disabled=reservation_disabled,
        form=form,
        lookup_form=lookup_form,
        submitted=request.args.get("submitted") == "1",
        apt_validation_error=apt_validation_error,
    )


@main_bp.route("/api/month/<int:month_id>", methods=["GET"])
def month_detail(month_id):
    months = get_months_with_slots()
    month = next((m for m in months if m["id"] == month_id), None)
    if not month:
        abort(404)
    return jsonify(_build_month_payload(month))
