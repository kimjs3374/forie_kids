from flask import flash, jsonify, redirect, render_template, request, url_for

from ...services.admin import generate_unique_month_password, list_months, update_month_password
from . import admin_bp
from .decorators import login_required


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


@admin_bp.route("/passwords/generate", methods=["GET"])
@login_required
def generate_password():
    try:
        return jsonify({"password": generate_unique_month_password()})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
