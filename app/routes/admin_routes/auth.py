from datetime import datetime, timedelta, timezone

from flask import current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from ...forms import LoginForm
from . import admin_bp
from .decorators import is_admin_session_authenticated, login_required


_LOGIN_ATTEMPTS = {}


def _now_utc():
    return datetime.now(timezone.utc)


def _client_ip():
    forwarded_for = str(request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return forwarded_for or request.remote_addr or "unknown"


def _prune_login_attempts(now):
    expired_keys = []
    for key, record in _LOGIN_ATTEMPTS.items():
        blocked_until = record.get("blocked_until")
        last_failed_at = record.get("last_failed_at")
        if blocked_until and blocked_until <= now:
            expired_keys.append(key)
            continue
        if last_failed_at and (now - last_failed_at) > timedelta(hours=12):
            expired_keys.append(key)
    for key in expired_keys:
        _LOGIN_ATTEMPTS.pop(key, None)


def _get_login_attempt_state():
    now = _now_utc()
    _prune_login_attempts(now)
    return now, _LOGIN_ATTEMPTS.get(_client_ip(), {})


def _is_login_blocked(state, now):
    blocked_until = state.get("blocked_until")
    return bool(blocked_until and blocked_until > now)


def _register_failed_login(now):
    key = _client_ip()
    state = _LOGIN_ATTEMPTS.get(key, {"count": 0})
    state["count"] = int(state.get("count") or 0) + 1
    state["last_failed_at"] = now

    max_attempts = int(current_app.config.get("ADMIN_MAX_LOGIN_ATTEMPTS", 5))
    if state["count"] >= max_attempts:
        block_minutes = int(current_app.config.get("ADMIN_LOGIN_BLOCK_MINUTES", 15))
        state["blocked_until"] = now + timedelta(minutes=block_minutes)

    _LOGIN_ATTEMPTS[key] = state
    return state


def _clear_failed_login_state():
    _LOGIN_ATTEMPTS.pop(_client_ip(), None)


def _is_valid_admin_password(password):
    configured_hash = str(current_app.config.get("ADMIN_PASSWORD_HASH") or "").strip()
    if configured_hash:
        try:
            return check_password_hash(configured_hash, password)
        except ValueError:
            current_app.logger.exception("ADMIN_PASSWORD_HASH 형식이 올바르지 않습니다.")
            return False
    return password == current_app.config["ADMIN_PASSWORD"]


@admin_bp.route("/", methods=["GET", "POST"])
def login():
    if is_admin_session_authenticated():
        return redirect(url_for("admin.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        now, state = _get_login_attempt_state()
        if _is_login_blocked(state, now):
            blocked_until = state.get("blocked_until")
            remaining_seconds = max(int((blocked_until - now).total_seconds()), 1)
            remaining_minutes = max((remaining_seconds + 59) // 60, 1)
            flash(f"로그인 시도가 너무 많습니다. {remaining_minutes}분 후 다시 시도해주세요.", "danger")
        else:
            username = form.username.data.strip()
            if username == current_app.config["ADMIN_USERNAME"] and _is_valid_admin_password(form.password.data):
                session.clear()
                session.permanent = True
                session["admin_logged_in"] = True
                session["admin_last_login_at"] = now.isoformat()
                _clear_failed_login_state()
                return redirect(url_for("admin.dashboard"))

            state = _register_failed_login(now)
            blocked_until = state.get("blocked_until")
            if blocked_until and blocked_until > now:
                remaining_seconds = max(int((blocked_until - now).total_seconds()), 1)
                remaining_minutes = max((remaining_seconds + 59) // 60, 1)
                flash(f"로그인 시도가 너무 많습니다. {remaining_minutes}분 후 다시 시도해주세요.", "danger")
            else:
                remaining_attempts = max(
                    int(current_app.config.get("ADMIN_MAX_LOGIN_ATTEMPTS", 5)) - int(state.get("count") or 0),
                    0,
                )
                flash(f"로그인 정보가 올바르지 않습니다. 남은 시도 횟수: {remaining_attempts}회", "danger")

    return render_template("admin/login.html", form=form)


@admin_bp.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("admin.login"))
