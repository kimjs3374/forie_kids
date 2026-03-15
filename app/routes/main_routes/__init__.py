from flask import Blueprint


main_bp = Blueprint("main", __name__)


from . import help_routes, home, inquiry, lookup  # noqa: E402,F401
