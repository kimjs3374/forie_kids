from flask import render_template

from . import admin_bp
from .decorators import login_required


@admin_bp.route("/help", methods=["GET"])
@login_required
def help_page():
    return render_template("admin/help.html")