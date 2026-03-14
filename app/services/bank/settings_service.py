from datetime import datetime, timezone

from ..shared.crypto_service import decrypt_sensitive_value, encrypt_sensitive_value
from ..supabase_service import fetch_rows, insert_row, patch_rows


BANK_CODE_LABELS = {
    "NH": "농협은행",
    "KB": "KB국민은행",
    "WR": "우리은행",
    "SH": "신한은행",
    "HN": "하나은행",
    "IBK": "IBK기업은행",
}

DEFAULT_PAYMENT_AMOUNT = 5000


def _normalize_digits(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _mask_account_number(value):
    digits = _normalize_digits(value)
    if not digits:
        return ""
    if len(digits) <= 4:
        return "*" * len(digits)
    return f"{digits[:3]}-***-***-{digits[-3:]}"


def _mask_identity_number(value):
    digits = _normalize_digits(value)
    if not digits:
        return ""
    if len(digits) <= 2:
        return "*" * len(digits)
    return f"{digits[:2]}{'*' * max(len(digits) - 2, 0)}"


def _coerce_payment_amount(value):
    try:
        amount = int(value)
    except (TypeError, ValueError):
        amount = DEFAULT_PAYMENT_AMOUNT
    return max(amount, 0)


def get_bank_code_label(bank_code):
    return BANK_CODE_LABELS.get(str(bank_code or "").upper(), str(bank_code or ""))


def _fetch_bank_settings():
    return fetch_rows("bank_settings", params={"select": "*", "order": "id.asc"})


def _format_bank_setting(setting, include_decrypted=False):
    if not setting:
        return None

    formatted = dict(setting)
    bank_code = formatted.get("bank_code", "")
    account_number = decrypt_sensitive_value(formatted.get("account_number_encrypted"))
    resident_number = decrypt_sensitive_value(formatted.get("resident_number_encrypted"))

    formatted["bank_name"] = get_bank_code_label(bank_code)
    formatted["masked_account_number"] = _mask_account_number(account_number)
    formatted["masked_resident_number"] = _mask_identity_number(resident_number)
    formatted["payment_amount"] = _coerce_payment_amount(formatted.get("payment_amount"))
    formatted["has_credentials"] = bool(formatted.get("account_number_encrypted"))
    if include_decrypted:
        formatted["account_number"] = account_number
        formatted["account_password"] = decrypt_sensitive_value(formatted.get("account_password_encrypted"))
        formatted["resident_number"] = resident_number
    return formatted


def get_bank_setting(include_decrypted=False):
    rows = _fetch_bank_settings()
    return _format_bank_setting(rows[0], include_decrypted=include_decrypted) if rows else None


def get_active_bank_setting(include_decrypted=False):
    setting = get_bank_setting(include_decrypted=include_decrypted)
    if not setting or not setting.get("is_active"):
        return None
    return setting


def get_configured_payment_amount():
    setting = get_bank_setting(include_decrypted=False)
    if not setting:
        return DEFAULT_PAYMENT_AMOUNT
    return _coerce_payment_amount(setting.get("payment_amount"))


def save_bank_setting(
    bank_code,
    account_holder_name,
    account_number,
    account_password,
    resident_number,
    payment_amount=DEFAULT_PAYMENT_AMOUNT,
    is_active=True,
):
    now = datetime.now(timezone.utc).isoformat()
    existing = get_bank_setting(include_decrypted=False)
    previous_payment_amount = _coerce_payment_amount(existing.get("payment_amount")) if existing else DEFAULT_PAYMENT_AMOUNT

    normalized_account_number = _normalize_digits(account_number)
    normalized_resident_number = _normalize_digits(resident_number)
    final_payment_amount = _coerce_payment_amount(payment_amount if payment_amount not in (None, "") else previous_payment_amount)

    if not existing and (not normalized_account_number or not str(account_password or "").strip() or not normalized_resident_number):
        raise ValueError("은행 연동에 필요한 계좌번호, 비밀번호, 생년월일/사업자번호를 모두 입력해주세요.")

    payload = {
        "bank_code": str(bank_code or "").upper().strip(),
        "account_holder_name": str(account_holder_name or "").strip() or None,
        "account_number_encrypted": encrypt_sensitive_value(normalized_account_number)
        if normalized_account_number
        else existing.get("account_number_encrypted"),
        "account_password_encrypted": encrypt_sensitive_value(str(account_password or "").strip())
        if str(account_password or "").strip()
        else existing.get("account_password_encrypted"),
        "resident_number_encrypted": encrypt_sensitive_value(normalized_resident_number)
        if normalized_resident_number
        else existing.get("resident_number_encrypted"),
        "payment_amount": final_payment_amount,
        "is_active": bool(is_active),
        "updated_at": now,
    }

    if existing:
        patch_rows("bank_settings", payload, params={"id": f"eq.{existing['id']}"})
    else:
        payload["created_at"] = now
        insert_row("bank_settings", payload)

    if final_payment_amount != previous_payment_amount:
        patch_rows(
            "reservations",
            {"expected_amount": final_payment_amount, "updated_at": now},
            params={"status": "eq.PENDING_PAYMENT"},
        )

    return get_bank_setting(include_decrypted=True)


def update_bank_setting(setting_id, payload):
    update_payload = dict(payload)
    update_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    patch_rows("bank_settings", update_payload, params={"id": f"eq.{setting_id}"})
    return get_bank_setting(include_decrypted=True)