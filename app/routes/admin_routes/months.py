from datetime import datetime

from flask import current_app, flash, redirect, render_template, request, url_for

from ...forms import MonthForm
from ...services.admin import create_month, delete_month, list_months, update_month
from . import admin_bp
from .decorators import login_required
from .helpers import _build_month_year_choices


@admin_bp.route("/months", methods=["GET", "POST"])
@login_required
def months():
    month_list = list_months()
    form = MonthForm()
    form.target_year.choices, form.target_month_num.choices = _build_month_year_choices(month_list)
    if request.method == "GET":
        form.target_year.data = datetime.now().year
        form.payment_amount.data = 5000
    if form.validate_on_submit():
        try:
            create_month(form)
            flash("예약 월이 생성되었습니다.", "success")
            return redirect(url_for("admin.months"))
        except Exception as exc:
            current_app.logger.exception("예약 월 생성 실패")
            flash(f"예약 월 생성 실패: {exc}", "danger")

    return render_template("admin/months.html", form=form, months=month_list)


@admin_bp.route("/months/<int:month_id>/edit", methods=["POST"])
@login_required
def edit_month(month_id):
    month_list = list_months()
    form = MonthForm()
    form.target_year.choices, form.target_month_num.choices = _build_month_year_choices(month_list)
    if form.validate_on_submit():
        try:
            update_month(month_id, form)
            flash("예약 월 정보가 수정되었습니다.", "success")
        except Exception as exc:
            current_app.logger.exception("예약 월 수정 실패 | month_id=%s", month_id)
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
        current_app.logger.exception("예약 월 삭제 실패 | month_id=%s", month_id)
        flash(f"예약 월 삭제 실패: {exc}", "danger")
    return redirect(url_for("admin.months"))
