from flask import render_template

from ...forms import ReservationLookupForm
from ...services.reservation import lookup_month_password, lookup_my_reservations
from . import main_bp


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
