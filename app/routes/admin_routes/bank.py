from flask import flash, redirect, render_template, request, url_for

from ...forms import BankSettingsForm, BankSyncForm
from ...services.admin import (
    get_bank_dashboard_summary,
    get_bank_setting_view,
    ignore_bank_transaction,
    list_bank_sync_histories,
    list_bank_transactions,
    match_bank_transaction,
    run_bank_sync,
    save_bank_settings,
    set_bank_transaction_billboard_approval,
)
from . import admin_bp
from .decorators import login_required


def _redirect_to_bank():
    return redirect(request.form.get("next") or request.args.get("next") or url_for("admin.bank_management"))


@admin_bp.route("/bank", methods=["GET"])
@login_required
def bank_management():
    setting = get_bank_setting_view()
    settings_form = BankSettingsForm()
    sync_form = BankSyncForm()
    sync_form.lookback_days.data = 30

    if setting:
        settings_form.bank_code.data = setting.get("bank_code") or settings_form.bank_code.data
        settings_form.account_holder_name.data = setting.get("account_holder_name") or ""
        settings_form.payment_amount.data = int(setting.get("payment_amount") or 5000)
        settings_form.is_active.data = bool(setting.get("is_active"))

    status_filter = request.args.get("status", "all").strip().lower()
    if status_filter not in {"all", "pending", "matched", "unmatched", "ignored"}:
        status_filter = "all"

    return render_template(
        "admin/bank.html",
        settings_form=settings_form,
        sync_form=sync_form,
        bank_setting=setting,
        bank_summary=get_bank_dashboard_summary(),
        sync_runs=list_bank_sync_histories(limit=10),
        transactions=list_bank_transactions(status_filter=status_filter, limit=100),
        active_filter=status_filter,
    )


@admin_bp.route("/bank/settings", methods=["POST"])
@login_required
def save_bank_settings_route():
    form = BankSettingsForm()
    if form.validate_on_submit():
        try:
            save_bank_settings(form)
            flash("은행 연동 설정이 암호화 저장되었습니다.", "success")
        except Exception as exc:
            flash(f"은행 연동 저장 실패: {exc}", "danger")
    else:
        flash("은행 연동 입력값을 다시 확인해주세요.", "danger")
    return redirect(url_for("admin.bank_management"))


@admin_bp.route("/bank/sync", methods=["POST"])
@login_required
def sync_bank_transactions_now():
    form = BankSyncForm()
    if form.validate_on_submit():
        try:
            summary = run_bank_sync(lookback_days=form.lookback_days.data, force=True)
            flash(
                "동기화 완료: "
                f"조회 {summary['fetched_count']}건 / 적재 {summary['inserted_count']}건 / "
                f"자동매칭 {summary['matched_count']}건 / 미매칭 {summary['unmatched_count']}건",
                "success",
            )
        except Exception as exc:
            flash(f"동기화 실패: {exc}", "danger")
    else:
        flash("동기화 요청값을 확인해주세요.", "danger")
    return redirect(url_for("admin.bank_management"))


@admin_bp.route("/bank/transactions/<int:transaction_id>/approve", methods=["POST"])
@login_required
def approve_bank_transaction(transaction_id):
    approved = request.form.get("approved", "true").lower() == "true"
    try:
        set_bank_transaction_billboard_approval(transaction_id, approved)
        flash("전광판 승인 상태가 변경되었습니다.", "success")
    except Exception as exc:
        flash(f"전광판 승인 변경 실패: {exc}", "danger")
    return _redirect_to_bank()


@admin_bp.route("/bank/transactions/<int:transaction_id>/ignore", methods=["POST"])
@login_required
def ignore_bank_transaction_route(transaction_id):
    try:
        ignore_bank_transaction(transaction_id)
        flash("거래를 무시 처리했습니다.", "success")
    except Exception as exc:
        flash(f"무시 처리 실패: {exc}", "danger")
    return _redirect_to_bank()


@admin_bp.route("/bank/transactions/<int:transaction_id>/match", methods=["POST"])
@login_required
def match_bank_transaction_route(transaction_id):
    reservation_id = str(request.form.get("reservation_id", "")).strip()
    if not reservation_id.isdigit():
        flash("연결할 예약 ID를 숫자로 입력해주세요.", "danger")
        return _redirect_to_bank()

    try:
        match_bank_transaction(transaction_id, int(reservation_id))
        flash("입금 거래가 예약과 연결되었습니다.", "success")
    except Exception as exc:
        flash(f"수동 매칭 실패: {exc}", "danger")
    return _redirect_to_bank()