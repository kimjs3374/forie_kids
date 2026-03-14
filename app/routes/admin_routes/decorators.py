from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import current_app, flash, redirect, session, url_for

from ...services.shared import parse_iso_datetime


def is_admin_session_authenticated(refresh=False, flash_on_expire=False):
    if not session.get("admin_logged_in"):
        return False

    timeout_minutes = int(current_app.config.get("ADMIN_SESSION_TIMEOUT_MINUTES", 30))
    last_activity = parse_iso_datetime(session.get("admin_last_login_at"))
    now = datetime.now(timezone.utc)
    if not last_activity or last_activity + timedelta(minutes=timeout_minutes) <= now:
        session.clear()
        if flash_on_expire:
            flash("관리자 세션이 만료되었습니다. 다시 로그인해주세요.", "warning")
        return False

    if refresh:
        session["admin_last_login_at"] = now.isoformat()
        session.modified = True
    return True


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not is_admin_session_authenticated(refresh=True, flash_on_expire=True):
            return redirect(url_for("admin.login"))
        return view_func(*args, **kwargs)

    return wrapper
