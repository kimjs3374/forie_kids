from flask import flash, redirect, render_template, url_for

from ...forms import NoticeForm, TickerMessageForm
from ...services.admin import get_bank_dashboard_summary, list_months, list_reservations, list_ticker_messages, save_notice
from ...services.reservation import get_notice_text
from . import admin_bp
from .decorators import login_required


@admin_bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    notice_form = NoticeForm()
    ticker_form = TickerMessageForm()
    if not notice_form.notice_text.data:
        notice_form.notice_text.data = get_notice_text()

    if notice_form.validate_on_submit():
        save_notice(notice_form.notice_text.data)
        flash("공지사항이 저장되었습니다.", "success")
        return redirect(url_for("admin.dashboard"))

    months = list_months()
    reservations = list_reservations()[:10]
    ticker_messages = list_ticker_messages()
    return render_template(
        "admin/dashboard.html",
        bank_summary=get_bank_dashboard_summary(),
        notice_form=notice_form,
        ticker_form=ticker_form,
        ticker_messages=ticker_messages,
        months=months,
        reservations=reservations,
    )
