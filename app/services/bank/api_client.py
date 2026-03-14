from datetime import date
from urllib.parse import urljoin

import requests
from flask import current_app
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class BankApiError(RuntimeError):
    pass


class AccountNotRegisteredError(BankApiError):
    pass


_BANK_API_SESSION = None


def _get_session():
    global _BANK_API_SESSION
    if _BANK_API_SESSION is None:
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.5,
            status_forcelist=(408, 429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
        )
        adapter = HTTPAdapter(max_retries=retry)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        _BANK_API_SESSION = session
    return _BANK_API_SESSION


def _base_url():
    return (current_app.config.get("BANK_API_BASE_URL") or "https://api.bankapi.co.kr").rstrip("/") + "/"


def _headers():
    api_key = (current_app.config.get("BANK_API_KEY") or "").strip()
    secret_key = (current_app.config.get("BANK_API_SECRET_KEY") or "").strip()
    if not api_key or not secret_key:
        raise BankApiError("BANK_API_KEY 와 BANK_API_SECRET_KEY 가 설정되지 않았습니다.")
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}:{secret_key}",
    }


def _endpoint(path):
    return urljoin(_base_url(), path.lstrip("/"))


def _parse_response(response):
    try:
        payload = response.json()
    except Exception:
        payload = {}

    if response.status_code >= 400 or payload.get("success") is False:
        error_code = payload.get("error") or f"HTTP_{response.status_code}"
        message = payload.get("message") or payload.get("error") or response.text[:200]
        if error_code == "ACCOUNT_NOT_REGISTERED":
            raise AccountNotRegisteredError(message)
        raise BankApiError(f"BankAPI 호출 실패: {error_code} ({message})")
    return payload


def _format_date(value):
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    return str(value or "").replace("-", "")


def register_account(setting):
    response = _get_session().post(
        _endpoint("/v1/accounts"),
        headers=_headers(),
        json={
            "bankCode": setting["bank_code"],
            "accountNumber": setting["account_number"],
        },
        timeout=20,
    )
    return _parse_response(response)


def fetch_transactions(setting, start_date, end_date):
    response = _get_session().post(
        _endpoint("/v1/transactions"),
        headers=_headers(),
        json={
            "bankCode": setting["bank_code"],
            "accountNumber": setting["account_number"],
            "accountPassword": setting["account_password"],
            "residentNumber": setting["resident_number"],
            "startDate": _format_date(start_date),
            "endDate": _format_date(end_date),
        },
        timeout=30,
    )
    return _parse_response(response)