from datetime import datetime
from functools import wraps

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, session, url_for

from ..forms import (
    LoginForm,
    MonthForm,
    NoticeForm,
    ReservationStatusForm,
)
from ..services.admin_service import (
    create_month,
    delete_month,
    list_months,
    list_reservations,
    save_notice,
    update_month_password,
    update_month,
    update_reservation_status as update_reservation_status_data,
)
from ..services.export_service import build_reservations_workbook
from ..services.reservation_service import get_notice_text


admin_bp = Blueprint("admin", __name__)


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.login"))
        return view_func(*args, **kwargs)

    return wrapper


@admin_bp.route("/", methods=["GET", "POST"])
def login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        if (
            form.username.data.strip() == current_app.config["ADMIN_USERNAME"]
            and form.password.data == current_app.config["ADMIN_PASSWORD"]
        ):
            session["admin_logged_in"] = True
            session["admin_last_login_at"] = datetime.utcnow().isoformat()
            return redirect(url_for("admin.dashboard"))
        flash("로그인 정보가 올바르지 않습니다.", "danger")

    return render_template("admin/login.html", form=form)


@admin_bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    notice_form = NoticeForm()
    if not notice_form.notice_text.data:
        notice_form.notice_text.data = get_notice_text()

    if notice_form.validate_on_submit():
        save_notice(notice_form.notice_text.data)
        flash("공지사항이 저장되었습니다.", "success")
        return redirect(url_for("admin.dashboard"))

    months = list_months()
    reservations = list_reservations()[:10]
    return render_template(
        "admin/dashboard.html",
        notice_form=notice_form,
        months=months,
        reservations=reservations,
    )


@admin_bp.route("/months", methods=["GET", "POST"])
@login_required
def months():
    form = MonthForm()
    current_year = datetime.now().year
    form.target_year.choices = [(year, f"{year}년") for year in range(current_year, current_year + 3)]
    form.target_month_num.choices = [(month, f"{month}월") for month in range(1, 13)]
    if form.validate_on_submit():
        try:
            create_month(form)
            flash("예약 월이 생성되었습니다.", "success")
            return redirect(url_for("admin.months"))
        except Exception as exc:
            flash(f"예약 월 생성 실패: {exc}", "danger")

    month_list = list_months()
    return render_template("admin/months.html", form=form, months=month_list)


@admin_bp.route("/months/<int:month_id>/edit", methods=["POST"])
@login_required
def edit_month(month_id):
    form = MonthForm()
    current_year = datetime.now().year
    form.target_year.choices = [(year, f"{year}년") for year in range(current_year, current_year + 3)]
    form.target_month_num.choices = [(month, f"{month}월") for month in range(1, 13)]
    if form.validate_on_submit():
        try:
            update_month(month_id, form)
            flash("예약 월 정보가 수정되었습니다.", "success")
        except Exception as exc:
            flash(f"예약 월 수정 실패: {exc}", "danger")
    else:
        flash("예약 월 수정 입력값을 확인해주세요.", "danger")
    return redirect(url_for("admin.months"))


@admin_bp.route("/months/<int:month_id>/delete", methods=["POST"])
@login_required
def remove_month(month_id):
    try:
        delete_month(month_id)
        flash("예약 월이 삭제되었습니다.", "success")
    except Exception as exc:
        flash(f"예약 월 삭제 실패: {exc}", "danger")
    return redirect(url_for("admin.months"))


@admin_bp.route("/passwords", methods=["GET"])
@login_required
def passwords():
    months = list_months()
    return render_template("admin/passwords.html", months=months)


@admin_bp.route("/passwords/<int:month_id>", methods=["POST"])
@login_required
def update_password(month_id):
    password = request.form.get("access_password", "")
    try:
        update_month_password(month_id, password)
        flash("월별 입장 비밀번호가 저장되었습니다.", "success")
    except Exception as exc:
        flash(f"비밀번호 저장 실패: {exc}", "danger")
    return redirect(url_for("admin.passwords"))


@admin_bp.route("/reservations", methods=["GET", "POST"])
@login_required
def reservations():
    reservations_list = list_reservations()
    status_form = ReservationStatusForm()
    return render_template("admin/reservations.html", reservations=reservations_list, status_form=status_form)


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


@admin_bp.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("admin.login"))