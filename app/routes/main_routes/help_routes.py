from flask import render_template

from . import main_bp


@main_bp.route("/help", methods=["GET"])
def help_page():
    return render_template("help.html")