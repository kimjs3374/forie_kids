from datetime import datetime

from flask import current_app, flash, redirect, render_template, session, url_for

from ...forms import LoginForm
from . import admin_bp
from .decorators import login_required


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


@admin_bp.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("admin.login"))
