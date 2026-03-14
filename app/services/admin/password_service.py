import random
from datetime import datetime, timezone

from ..supabase_service import delete_rows, fetch_rows, insert_row, patch_rows


DEFAULT_MONTH_CAPACITY = 100
VALID_MONTH_PASSWORD_COUNT = 9630


def _generate_random_password():
    return f"{random.randint(0, 9999):04d}"


def _is_valid_month_password(password):
    normalized = str(password or "").strip().zfill(4)
    if len(normalized) != 4 or not normalized.isdigit():
        return False
    counts = {}
    for digit in normalized:
        counts[digit] = counts.get(digit, 0) + 1
        if counts[digit] >= 3:
            return False
    return True


def _get_used_passwords():
    passwords = fetch_rows("used_passwords", params={"select": "password"})
    return {str(item.get("password", "")).zfill(4) for item in passwords if str(item.get("password", "")).strip()}


def _reserve_password(password):
    normalized = str(password or "").strip().zfill(4)
    if not normalized:
        return False
    if not _is_valid_month_password(normalized):
        return False
    existing = fetch_rows("used_passwords", params={"select": "password", "password": f"eq.{normalized}"})
    if existing:
        return False
    try:
        insert_row("used_passwords", {"password": normalized})
        return True
    except Exception:
        return False


def _register_used_password(password):
    normalized = str(password or "").strip()
    if not normalized:
        return
    _reserve_password(normalized)


def generate_unique_month_password():
    used_passwords = _get_used_passwords()
    if len(used_passwords) >= VALID_MONTH_PASSWORD_COUNT:
        raise ValueError("사용 가능한 4자리 비밀번호가 모두 소진되었습니다.")

    password = _generate_random_password()
    while password in used_passwords or not _is_valid_month_password(password):
        password = _generate_random_password()
    return password


def _allocate_unique_month_password():
    for _ in range(VALID_MONTH_PASSWORD_COUNT):
        candidate = _generate_random_password()
        if _reserve_password(candidate):
            return candidate
    raise ValueError("사용 가능한 4자리 비밀번호가 모두 소진되었습니다.")


def _get_month_password(target_month):
    rows = fetch_rows("month_passwords", params={"select": "target_month,access_password", "target_month": f"eq.{target_month}"})
    return rows[0] if rows else None


def _get_month_password_map():
    rows = fetch_rows("month_passwords", params={"select": "target_month,access_password"})
    return {item["target_month"]: item.get("access_password", "") for item in rows}


def _set_month_password(target_month, password):
    existing = _get_month_password(target_month)
    normalized = str(password or "").strip().zfill(4)
    if existing:
        patch_rows(
            "month_passwords",
            {"access_password": normalized, "updated_at": datetime.now(timezone.utc).isoformat()},
            params={"target_month": f"eq.{target_month}"},
        )
    else:
        insert_row("month_passwords", {"target_month": target_month, "access_password": normalized})


def _remove_month_password(target_month):
    delete_rows("month_passwords", params={"target_month": f"eq.{target_month}"})


def update_month_password(month_id, password):
    month = fetch_rows("reservation_months", params={"select": "target_month", "id": f"eq.{month_id}"})
    if not month:
        return

    target_month = month[0]["target_month"]
    normalized = str(password or "").strip().zfill(4)
    if not normalized:
        return
    if not _is_valid_month_password(normalized):
        raise ValueError("비밀번호는 같은 숫자가 3개 이상 반복될 수 없습니다.")

    current_entry = _get_month_password(target_month)
    current_password = current_entry.get("access_password", "") if current_entry else ""
    if current_password == normalized:
        return

    if not _reserve_password(normalized):
        raise ValueError("이미 사용했던 비밀번호입니다. 랜덤생성으로 다시 시도해주세요.")

    _set_month_password(target_month, normalized)
