import click
from flask import Flask

from config import Config
from .services.admin import ensure_next_month_reservation
from .services.cleanup import delete_expired_personal_data


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="static")
    app.config.from_object(Config)

    app.config['TEMPLATES_AUTO_RELOAD'] = True

    @app.before_request
    def sync_next_month_reservation():
        try:
            ensure_next_month_reservation()
        except Exception:
            app.logger.exception("다음달 예약 자동 생성 중 오류가 발생했습니다.")

    from .routes.main import main_bp
    from .routes.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix="/forie_admin")

    @app.cli.command("cleanup-expired-data")
    def cleanup_expired_data_command():
        """Delete personal data older than the configured retention period."""
        summary = delete_expired_personal_data()
        click.echo(
            "cleanup completed | "
            f"cutoff={summary['cutoff']} "
            f"reservations_deleted={summary['reservations_deleted']} "
            f"deposit_requests_deleted={summary['deposit_requests_deleted']} "
            f"deposit_request_messages_deleted={summary['deposit_request_messages_deleted']}"
        )
        if summary["errors"]:
            raise click.ClickException("; ".join(summary["errors"]))

    return app