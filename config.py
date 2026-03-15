import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _get_bool_env(name, default=False):
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}


def validate_security_settings(config):
    warnings = []
    secret_key = str(config.get("SECRET_KEY") or "").strip()
    admin_username = str(config.get("ADMIN_USERNAME") or "").strip()
    admin_password = str(config.get("ADMIN_PASSWORD") or "").strip()
    admin_password_hash = str(config.get("ADMIN_PASSWORD_HASH") or "").strip()

    if not secret_key or secret_key == "dev-secret-key":
        warnings.append("FLASK_SECRET_KEY 가 기본값(dev-secret-key)이거나 비어 있습니다.")

    if not admin_password_hash:
        warnings.append("ADMIN_PASSWORD_HASH 가 없어 평문 ADMIN_PASSWORD fallback 을 사용 중입니다.")

    if admin_username == "admin":
        warnings.append("ADMIN_USERNAME 이 기본값(admin)입니다.")

    if not admin_password_hash and admin_password == "change_me":
        warnings.append("ADMIN_PASSWORD 가 기본값(change_me)입니다.")

    if config.get("ENFORCE_SECURE_CONFIG") and warnings:
        raise RuntimeError("운영 보안 설정이 미흡합니다: " + " | ".join(warnings))

    return warnings


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change_me")
    ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
    ADMIN_SESSION_TIMEOUT_MINUTES = int(os.getenv("ADMIN_SESSION_TIMEOUT_MINUTES", "30"))
    ADMIN_MAX_LOGIN_ATTEMPTS = int(os.getenv("ADMIN_MAX_LOGIN_ATTEMPTS", "5"))
    ADMIN_LOGIN_BLOCK_MINUTES = int(os.getenv("ADMIN_LOGIN_BLOCK_MINUTES", "15"))
    ENFORCE_SECURE_CONFIG = _get_bool_env("ENFORCE_SECURE_CONFIG", False)
    AUTO_ENSURE_NEXT_MONTH_ON_REQUESTS = _get_bool_env("AUTO_ENSURE_NEXT_MONTH_ON_REQUESTS", False)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = _get_bool_env("SESSION_COOKIE_SECURE", False)
    FOOTER_COMPANY_NAME = os.getenv("FOOTER_COMPANY_NAME", "포리에 실내놀이터 예약시스템")
    FOOTER_ADDRESS = os.getenv("FOOTER_ADDRESS", "주소 정보 준비중")
    FOOTER_CONTACT = os.getenv("FOOTER_CONTACT", "연락처 정보 준비중")
    FOOTER_COPYRIGHT = os.getenv("FOOTER_COPYRIGHT", "")
    PERSONAL_DATA_RETENTION_MONTHS = int(os.getenv("PERSONAL_DATA_RETENTION_MONTHS", "12"))
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    MASTER_SECRET_KEY = os.getenv("MASTER_SECRET_KEY", "")
    BANK_API_KEY = os.getenv("BANK_API_KEY", "")
    BANK_API_SECRET_KEY = os.getenv("BANK_API_SECRET_KEY", "")
    BANK_API_BASE_URL = os.getenv("BANK_API_BASE_URL", "https://api.bankapi.co.kr")
    BANK_DEFAULT_CODE = os.getenv("BANK_DEFAULT_CODE", "NH")
    BANK_DEFAULT_ACCOUNT_HOLDER_NAME = os.getenv("BANK_DEFAULT_ACCOUNT_HOLDER_NAME", "")
    BANK_DEFAULT_ACCOUNT_NUMBER = os.getenv("BANK_DEFAULT_ACCOUNT_NUMBER", "")
    BANK_DEFAULT_PAYMENT_AMOUNT = int(os.getenv("BANK_DEFAULT_PAYMENT_AMOUNT", "5000"))
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")