from flask import current_app, flash

from ...forms import TickerMessageForm
from ...services.admin import create_ticker_message, delete_ticker_message, update_ticker_message
from . import admin_bp
from .decorators import login_required
from .helpers import _redirect_back


@admin_bp.route("/ticker", methods=["POST"])
@login_required
def create_ticker():
    form = TickerMessageForm()
    if form.validate_on_submit():
        try:
            create_ticker_message(form)
            flash("전광판 문구가 추가되었습니다.", "success")
        except Exception as exc:
            current_app.logger.exception("전광판 문구 추가 실패")
            flash(f"전광판 문구 추가 실패: {exc}", "danger")
    else:
        flash("전광판 입력값을 확인해주세요.", "danger")
    return _redirect_back()


@admin_bp.route("/ticker/<int:message_id>/edit", methods=["POST"])
@login_required
def edit_ticker(message_id):
    form = TickerMessageForm()
    if form.validate_on_submit():
        try:
            update_ticker_message(message_id, form)
            flash("전광판 문구가 수정되었습니다.", "success")
        except Exception as exc:
            current_app.logger.exception("전광판 문구 수정 실패 | message_id=%s", message_id)
            flash(f"전광판 문구 수정 실패: {exc}", "danger")
    else:
        flash("전광판 수정 입력값을 확인해주세요.", "danger")
    return _redirect_back()


@admin_bp.route("/ticker/<int:message_id>/delete", methods=["POST"])
@login_required
def remove_ticker(message_id):
    try:
        delete_ticker_message(message_id)
        flash("전광판 문구가 삭제되었습니다.", "success")
    except Exception as exc:
        current_app.logger.exception("전광판 문구 삭제 실패 | message_id=%s", message_id)
        flash(f"전광판 문구 삭제 실패: {exc}", "danger")
    return _redirect_back()
