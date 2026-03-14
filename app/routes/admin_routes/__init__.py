from flask import Blueprint


admin_bp = Blueprint("admin", __name__)


from . import auth, dashboard, months, passwords, payment_requests, reservations, ticker  # noqa: E402,F401
