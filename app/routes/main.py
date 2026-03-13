from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..forms import ReservationForm, ReservationLookupForm
from ..services.reservation_service import (
    create_reservation,
    get_months_with_slots,
    get_notice_text,
    lookup_month_password,
    lookup_my_reservations,
)


main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET", "POST"])
def index():
    months = get_months_with_slots()
    selected_month_id = request.args.get("month_id", type=int)
    selected_month = next((month for month in months if month["id"] == selected_month_id), None)
    if not selected_month and months:
        selected_month = months[0]

    form = ReservationForm()
    if selected_month:
        active_slots = [slot for slot in selected_month.get("slots", []) if slot.get("status") == "ACTIVE"]
        form.month_id.data = str(selected_month["id"])
        if active_slots:
            form.slot_id.data = str(active_slots[0]["id"])

    if form.validate_on_submit():
        success, message = create_reservation(form)
        flash(message, "success" if success else "danger")
        return redirect(url_for("main.index", month_id=form.month_id.data, submitted=1 if success else 0))
    elif request.method == "POST":
        flash("입력값을 다시 확인해주세요. 모든 필수 항목을 입력해야 합니다.", "danger")

    lookup_form = ReservationLookupForm()

    return render_template(
        "index.html",
        months=months,
        selected_month=selected_month,
        notice_text=get_notice_text(),
        form=form,
        lookup_form=lookup_form,
        submitted=request.args.get("submitted") == "1",
    )


@main_bp.route("/lookup", methods=["GET", "POST"])
def lookup():
    form = ReservationLookupForm()
    reservations = []
    searched = False
    if form.validate_on_submit():
        reservations = lookup_my_reservations(
            form.name.data,
            form.phone.data,
            form.apt_dong.data,
            form.apt_ho.data,
        )
        searched = True
    return render_template("lookup.html", form=form, reservations=reservations, searched=searched)


@main_bp.route("/password", methods=["GET", "POST"])
def password_lookup():
    form = ReservationLookupForm()
    reservations = []
    searched = False
    if form.validate_on_submit():
        reservations = lookup_month_password(
            form.name.data,
            form.phone.data,
            form.apt_dong.data,
            form.apt_ho.data,
        )
        searched = True
    return render_template("password.html", form=form, reservations=reservations, searched=searched)