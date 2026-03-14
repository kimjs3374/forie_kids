from flask import flash, render_template, request

from ...forms import PaymentRequestForm, ReservationLookupForm
from ...services.reservation import create_payment_request, list_payment_requests
from . import main_bp
from .helpers import _get_apartment_validation_error


@main_bp.route("/payment-request", methods=["GET", "POST"])
def payment_request():
    form = PaymentRequestForm()
    lookup_form = ReservationLookupForm(formdata=request.form if request.method == "POST" else None)
    threads = []
    searched = False
    apt_validation_error = ""

    action = request.form.get("action", "submit")

    if request.method == "POST":
        if action == "lookup":
            if lookup_form.validate():
                threads = list_payment_requests(
                    lookup_form.name.data,
                    lookup_form.phone.data,
                    lookup_form.apt_dong.data,
                    lookup_form.apt_ho.data,
                )
                searched = True
            else:
                apt_validation_error = _get_apartment_validation_error(lookup_form)
                if not apt_validation_error:
                    first_error = (
                        lookup_form.name.errors
                        or lookup_form.phone.errors
                        or lookup_form.apt_dong.errors
                        or lookup_form.apt_ho.errors
                    )
                    if first_error:
                        flash(first_error[0], "danger")
        elif form.validate_on_submit():
            if not (form.content.data or "").strip():
                flash("문의사항 내용을 입력해주세요.", "danger")
            else:
                create_payment_request(
                    form.name.data,
                    form.phone.data,
                    form.apt_dong.data,
                    form.apt_ho.data,
                    form.content.data,
                    bool(form.consent_agreed.data),
                )
                flash("문의사항이 접수되었습니다. 관리자가 확인 후 답변을 남깁니다.", "success")
                threads = list_payment_requests(
                    form.name.data,
                    form.phone.data,
                    form.apt_dong.data,
                    form.apt_ho.data,
                )
                searched = True
        else:
            apt_validation_error = _get_apartment_validation_error(form)

    return render_template(
        "payment_request.html",
        form=form,
        threads=threads,
        searched=searched,
        apt_validation_error=apt_validation_error,
    )
