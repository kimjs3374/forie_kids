from flask import Blueprint


admin_bp = Blueprint("admin", __name__)


from . import auth, bank, dashboard, help_routes, inquiries, months, passwords, reservations, ticker  # noqa: E402,F401
