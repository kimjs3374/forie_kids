from flask import Flask

from config import Config


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="static")
    app.config.from_object(Config)

    from .routes.main import main_bp
    from .routes.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix="/forie_admin")

    return app