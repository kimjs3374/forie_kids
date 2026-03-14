import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change_me")
    PERSONAL_DATA_RETENTION_MONTHS = int(os.getenv("PERSONAL_DATA_RETENTION_MONTHS", "12"))
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    MASTER_SECRET_KEY = os.getenv("MASTER_SECRET_KEY", "")
    BANK_API_KEY = os.getenv("BANK_API_KEY", "")
    BANK_API_SECRET_KEY = os.getenv("BANK_API_SECRET_KEY", "")
    BANK_API_BASE_URL = os.getenv("BANK_API_BASE_URL", "https://api.bankapi.co.kr")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")