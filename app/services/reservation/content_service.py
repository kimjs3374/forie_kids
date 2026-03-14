from flask import current_app

from ..supabase_service import fetch_rows


def get_notice_text():
    settings = fetch_rows("settings", params={"select": "*", "id": "eq.1"})
    if settings:
        return settings[0].get("notice_text") or "현재 공지사항이 없습니다."
    return "현재 공지사항이 없습니다."


def get_active_ticker_messages():
    messages = fetch_rows(
        "ticker_messages",
        params={"select": "*", "is_active": "eq.true", "order": "sort_order.asc,id.asc"},
    )
    active_messages = [item for item in messages if (item.get("content") or "").strip()]
    try:
        from ..bank import get_billboard_ticker_messages

        active_messages.extend(get_billboard_ticker_messages())
    except Exception:
        current_app.logger.exception("전광판 메시지 병합 중 오류가 발생했습니다.")
    return active_messages
