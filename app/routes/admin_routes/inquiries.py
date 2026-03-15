from flask import current_app, flash, redirect, render_template, request, url_for

from ...forms import PaymentRequestMessageEditForm, PaymentRequestReplyForm
from ...services.reservation import (
    add_inquiry_reply,
    delete_inquiry_message,
    inquiry_status_label,
    list_inquiries,
    update_inquiry_message,
)
from . import admin_bp
from .decorators import login_required


@admin_bp.route("/inquiries", methods=["GET"])
@login_required
def inquiries():
    threads = list_inquiries()
    threads.sort(key=lambda thread: thread.get("latest_message_at") or "", reverse=True)

    for thread in threads:
        thread["status_label"] = inquiry_status_label(thread.get("status"))
    reply_form = PaymentRequestReplyForm()
    edit_form = PaymentRequestMessageEditForm()
    return render_template(
        "admin/inquiries.html",
        threads=threads,
        reply_form=reply_form,
        edit_form=edit_form,
        open_thread_id=request.args.get("open_thread", "").strip(),
    )


@admin_bp.route("/inquiries/reply", methods=["POST"])
@login_required
def reply_inquiry():
    form = PaymentRequestReplyForm()
    thread_id = request.form.get("thread_id", "").strip()
    content = request.form.get("content", "").strip()
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if not form.csrf_token.data:
        flash("보안 검증에 실패했습니다. 다시 시도해주세요.", "danger")
    elif not thread_id or not content:
        flash("답변 내용을 확인해주세요.", "danger")
    else:
        try:
            add_inquiry_reply(thread_id, content)
            flash("답변이 등록되었습니다.", "success")
        except Exception as exc:
            current_app.logger.exception("문의사항 답변 등록 실패 | thread_id=%s", thread_id)
            flash(f"답변 등록 실패: {exc}", "danger")

    if is_ajax:
        threads = list_inquiries()
        for thread in threads:
            thread["status_label"] = inquiry_status_label(thread.get("status"))
        reply_form = PaymentRequestReplyForm()
        edit_form = PaymentRequestMessageEditForm()
        return render_template(
            "admin/inquiries.html",
            threads=threads,
            reply_form=reply_form,
            edit_form=edit_form,
            open_thread_id=thread_id,
        )

    return redirect(url_for("admin.inquiries", open_thread=thread_id or None))


@admin_bp.route("/inquiries/message/edit", methods=["POST"])
@login_required
def edit_inquiry_message():
    form = PaymentRequestMessageEditForm()
    thread_id = request.form.get("thread_id", "").strip()
    message_id = request.form.get("message_id", "").strip()
    content = request.form.get("content", "").strip()

    if not form.csrf_token.data:
        flash("보안 검증에 실패했습니다. 다시 시도해주세요.", "danger")
    elif not thread_id or not message_id or not content:
        flash("수정 내용을 확인해주세요.", "danger")
    else:
        try:
            update_inquiry_message(message_id, thread_id, content)
            flash("문의/답변 내용이 수정되었습니다.", "success")
        except Exception as exc:
            current_app.logger.exception(
                "문의/답변 수정 실패 | thread_id=%s message_id=%s",
                thread_id,
                message_id,
            )
            flash(f"수정 실패: {exc}", "danger")

    return redirect(url_for("admin.inquiries", open_thread=thread_id or None))


@admin_bp.route("/inquiries/message/delete", methods=["POST"])
@login_required
def delete_inquiry_message_route():
    thread_id = request.form.get("thread_id", "").strip()
    message_id = request.form.get("message_id", "").strip()

    if not thread_id or not message_id:
        flash("삭제할 문의/답변 정보를 확인해주세요.", "danger")
    else:
        try:
            delete_inquiry_message(message_id, thread_id)
            flash("문의/답변 내용이 삭제되었습니다.", "success")
        except Exception as exc:
            current_app.logger.exception(
                "문의/답변 삭제 실패 | thread_id=%s message_id=%s",
                thread_id,
                message_id,
            )
            flash(f"삭제 실패: {exc}", "danger")

    return redirect(url_for("admin.inquiries", open_thread=thread_id or None))