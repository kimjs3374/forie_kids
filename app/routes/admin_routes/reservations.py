from math import ceil

from flask import current_app, flash, redirect, render_template, request, send_file, url_for

from ...forms import ReservationStatusForm
from ...services.admin import (
    get_reservation_counts,
    list_reservations,
    update_reservation_status as update_reservation_status_data,
)
from ...services.export import build_reservations_workbook
from . import admin_bp
from .decorators import login_required


@admin_bp.route("/reservations", methods=["GET", "POST"])
@login_required
def reservations():
    active_filter = request.args.get("filter", "all").strip().lower()
    search_query = request.args.get("q", "").strip()
    page = max(request.args.get("page", default=1, type=int), 1)
    page_size = 50
    filter_map = {
        "all": None,
        "confirmed": "PAYMENT_CONFIRMED",
        "pending": "PENDING_PAYMENT",
    }
    if active_filter not in filter_map:
        active_filter = "all"

    target_status = filter_map[active_filter]
    reservation_counts = get_reservation_counts(search_text=search_query)
    filtered_total = reservation_counts[active_filter]
    total_pages = max(ceil(filtered_total / page_size), 1) if filtered_total else 1
    page = min(page, total_pages)
    reservations_list = list_reservations(
        status=target_status,
        limit=page_size,
        offset=(page - 1) * page_size,
        search_text=search_query,
    )

    status_form = ReservationStatusForm()
    return render_template(
        "admin/reservations.html",
        reservations=reservations_list,
        status_form=status_form,
        active_filter=active_filter,
        search_query=search_query,
        page=page,
        total_pages=total_pages,
        filtered_total=filtered_total,
        reservation_counts=reservation_counts,
    )


@admin_bp.route("/reservations/<int:reservation_id>/status", methods=["POST"])
@login_required
def change_reservation_status(reservation_id):
    form = ReservationStatusForm()
    if form.validate_on_submit():
        try:
            update_reservation_status_data(reservation_id, form.status.data)
            flash("예약 상태가 변경되었습니다.", "success")
        except Exception as exc:
            current_app.logger.exception("예약 상태 변경 실패 | reservation_id=%s", reservation_id)
            flash(f"예약 상태 변경에 실패했습니다: {exc}", "danger")
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
        current_app.logger.exception("예약 입금 상태 저장 실패 | reservation_id=%s", reservation_id)
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
