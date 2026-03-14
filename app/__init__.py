from datetime import datetime, timedelta

import click
from flask import Flask
from werkzeug.security import generate_password_hash

from config import Config, validate_security_settings
from .services.admin import ensure_next_month_reservation
from .services.bank import sync_bank_transactions
from .services.cleanup import delete_expired_personal_data


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="static")
    app.config.from_object(Config)
    app.permanent_session_lifetime = timedelta(minutes=app.config["ADMIN_SESSION_TIMEOUT_MINUTES"])

    app.config["TEMPLATES_AUTO_RELOAD"] = True

    for warning_message in validate_security_settings(app.config):
        app.logger.warning("보안 설정 경고: %s", warning_message)

    @app.context_processor
    def inject_layout_context():
        company_name = app.config.get("FOOTER_COMPANY_NAME") or "포리에 실내놀이터 예약시스템"
        return {
            "current_year": datetime.now().year,
            "footer_company_name": company_name,
            "footer_address": app.config.get("FOOTER_ADDRESS") or "주소 정보 준비중",
            "footer_contact": app.config.get("FOOTER_CONTACT") or "연락처 정보 준비중",
            "footer_copyright": app.config.get("FOOTER_COPYRIGHT")
            or f"© {datetime.now().year} {company_name}. All rights reserved.",
        }

    if app.config.get("AUTO_ENSURE_NEXT_MONTH_ON_REQUESTS"):
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
            f"deposit_request_messages_deleted={summary['deposit_request_messages_deleted']} "
            f"bank_transactions_deleted={summary.get('bank_transactions_deleted', 0)} "
            f"bank_sync_runs_deleted={summary.get('bank_sync_runs_deleted', 0)}"
        )
        if summary["errors"]:
            raise click.ClickException("; ".join(summary["errors"]))

    @app.cli.command("sync-bank-transactions")
    @click.option("--lookback-days", default=30, show_default=True, type=int)
    @click.option("--force", is_flag=True, help="호출 중지 시간대에도 강제로 동기화합니다.")
    def sync_bank_transactions_command(lookback_days, force):
        """Sync bank transactions from BankAPI and auto-match reservations."""
        summary = sync_bank_transactions(force=force, lookback_days=lookback_days)
        click.echo(
            "bank sync completed | "
            f"status={summary['status']} "
            f"reason={summary['reason']} "
            f"fetched={summary['fetched_count']} "
            f"inserted={summary['inserted_count']} "
            f"matched={summary['matched_count']} "
            f"unmatched={summary['unmatched_count']}"
        )

    @app.cli.command("ensure-next-month-reservation")
    def ensure_next_month_reservation_command():
        """Create next month's reservation record when the scheduling condition is met."""
        created = ensure_next_month_reservation()
        if created:
            click.echo("next month reservation created")
        else:
            click.echo("next month reservation skipped")

    @app.cli.command("generate-admin-password-hash")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def generate_admin_password_hash_command(password):
        """Generate a password hash for ADMIN_PASSWORD_HASH."""
        click.echo(generate_password_hash(password))

    return app