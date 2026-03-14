from flask import Blueprint


admin_bp = Blueprint("admin", __name__)


from . import auth, bank, dashboard, help_routes, months, passwords, payment_requests, reservations, ticker  # noqa: E402,F401
