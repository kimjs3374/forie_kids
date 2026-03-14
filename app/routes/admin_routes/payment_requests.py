from flask import flash, redirect, render_template, request, url_for

from ...forms import PaymentRequestReplyForm
from ...services.reservation import add_payment_request_reply, list_payment_requests, payment_request_status_label
from . import admin_bp
from .decorators import login_required


@admin_bp.route("/payment-requests", methods=["GET"])
@login_required
def payment_requests():
    threads = list_payment_requests()
    threads.sort(key=lambda thread: thread.get("latest_message_at") or "", reverse=True)

    for thread in threads:
        thread["status_label"] = payment_request_status_label(thread.get("status"))
    reply_form = PaymentRequestReplyForm()
    return render_template(
        "admin/payment_requests.html",
        threads=threads,
        reply_form=reply_form,
        open_thread_id=request.args.get("open_thread", "").strip(),
    )


@admin_bp.route("/payment-requests/reply", methods=["POST"])
@login_required
def reply_payment_request():
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
            add_payment_request_reply(thread_id, content)
            flash("답변이 등록되었습니다.", "success")
        except Exception as exc:
            flash(f"답변 등록 실패: {exc}", "danger")

    if is_ajax:
        threads = list_payment_requests()
        for thread in threads:
            thread["status_label"] = payment_request_status_label(thread.get("status"))
        reply_form = PaymentRequestReplyForm()
        return render_template(
            "admin/payment_requests.html",
            threads=threads,
            reply_form=reply_form,
            open_thread_id=thread_id,
        )

    return redirect(url_for("admin.payment_requests", open_thread=thread_id or None))
