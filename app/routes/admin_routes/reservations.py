from flask import flash, redirect, render_template, request, send_file, url_for

from ...forms import ReservationStatusForm
from ...services.admin import list_reservations, update_reservation_status as update_reservation_status_data
from ...services.export import build_reservations_workbook
from . import admin_bp
from .decorators import login_required


@admin_bp.route("/reservations", methods=["GET", "POST"])
@login_required
def reservations():
    reservations_list = list_reservations()
    active_filter = request.args.get("filter", "all").strip().lower()
    filter_map = {
        "all": None,
        "confirmed": "PAYMENT_CONFIRMED",
        "pending": "PENDING_PAYMENT",
    }
    if active_filter not in filter_map:
        active_filter = "all"

    target_status = filter_map[active_filter]
    if target_status:
        reservations_list = [item for item in reservations_list if item.get("status") == target_status]

    all_reservations = list_reservations()
    reservation_counts = {
        "all": len(all_reservations),
        "confirmed": sum(1 for item in all_reservations if item.get("status") == "PAYMENT_CONFIRMED"),
        "pending": sum(1 for item in all_reservations if item.get("status") == "PENDING_PAYMENT"),
    }
    status_form = ReservationStatusForm()
    return render_template(
        "admin/reservations.html",
        reservations=reservations_list,
        status_form=status_form,
        active_filter=active_filter,
        reservation_counts=reservation_counts,
    )


@admin_bp.route("/reservations/<int:reservation_id>/status", methods=["POST"])
@login_required
def change_reservation_status(reservation_id):
    form = ReservationStatusForm()
    if form.validate_on_submit():
        update_reservation_status_data(reservation_id, form.status.data)
        flash("예약 상태가 변경되었습니다.", "success")
    else:
        flash("예약 상태 변경에 실패했습니다.", "danger")
    return redirect(url_for("admin.reservations"))


@admin_bp.route("/reservations/<int:reservation_id>/toggle-payment", methods=["POST"])
@login_required
def toggle_reservation_payment(reservation_id):
    current_status = request.form.get("current_status", "PENDING_PAYMENT")
    next_status = "PAYMENT_CONFIRMED" if current_status != "PAYMENT_CONFIRMED" else "PENDING_PAYMENT"
    try:
        update_reservation_status_data(reservation_id, next_status)
        flash("입금 상태가 저장되었습니다.", "success")
    except Exception as exc:
        flash(f"입금 상태 저장 실패: {exc}", "danger")
    return redirect(url_for("admin.reservations"))


@admin_bp.route("/reservations/export")
@login_required
def export_reservations():
    reservations = list_reservations()
    output = build_reservations_workbook(reservations)
    return send_file(
        output,
        as_attachment=True,
        download_name="reservations.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
