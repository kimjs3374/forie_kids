from flask import flash, render_template

from ...forms import ReservationLookupForm
from ...services.reservation import lookup_month_password, lookup_my_reservations
from . import main_bp
from .helpers import _get_missing_required_fields_message


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
    elif form.is_submitted():
        missing_fields_message = _get_missing_required_fields_message(
            form, ["name", "phone", "apt_dong", "apt_ho"]
        )
        if missing_fields_message:
            flash(missing_fields_message, "danger")
        else:
            first_error = form.name.errors or form.phone.errors or form.apt_dong.errors or form.apt_ho.errors
            if first_error:
                flash(first_error[0], "danger")
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
    elif form.is_submitted():
        missing_fields_message = _get_missing_required_fields_message(
            form, ["name", "phone", "apt_dong", "apt_ho"]
        )
        if missing_fields_message:
            flash(missing_fields_message, "danger")
        else:
            first_error = form.name.errors or form.phone.errors or form.apt_dong.errors or form.apt_ho.errors
            if first_error:
                flash(first_error[0], "danger")
    return render_template("password.html", form=form, reservations=reservations, searched=searched)
