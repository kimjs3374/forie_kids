from datetime import datetime, timezone


def _to_utc_datetime(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00").replace("/", "-"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def status_label(status):
    return {
        "ACTIVE": "사용가능",
        "INACTIVE": "비활성",
        "PENDING": "미처리",
        "MATCHED": "자동매칭",
        "UNMATCHED": "미매칭",
        "IGNORED": "무시됨",
        "PENDING_PAYMENT": "예약대기",
        "PAYMENT_CONFIRMED": "예약완료",
        "CANCELLED": "취소",
    }.get(status, status)


def month_status_label(month):
    now = datetime.now(timezone.utc)
    open_at = _to_utc_datetime(month["open_at"])
    close_at = _to_utc_datetime(month["close_at"])
    if now < open_at:
        return "예약대기"
    if open_at <= now <= close_at:
        return "예약중"
    return "예약완료"


def is_month_open(month):
    now = datetime.now(timezone.utc)
    open_at = _to_utc_datetime(month["open_at"])
    close_at = _to_utc_datetime(month["close_at"])
    return open_at <= now <= close_at
