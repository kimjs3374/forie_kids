from flask import Blueprint


main_bp = Blueprint("main", __name__)


from . import home, lookup, payment  # noqa: E402,F401
