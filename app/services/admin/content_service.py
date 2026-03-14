from datetime import datetime, timezone

from ..supabase_service import delete_rows, fetch_rows, insert_row, patch_rows


def save_notice(notice_text):
    existing = fetch_rows("settings", params={"select": "id", "id": "eq.1"})
    payload = {"id": 1, "notice_text": notice_text.strip(), "updated_at": datetime.now(timezone.utc).isoformat()}
    if existing:
        patch_rows("settings", payload, params={"id": "eq.1"})
    else:
        insert_row("settings", payload)


def list_ticker_messages():
    return fetch_rows("ticker_messages", params={"select": "*", "order": "sort_order.asc,id.asc"})


def create_ticker_message(form):
    insert_row(
        "ticker_messages",
        {
            "content": form.content.data.strip(),
            "display_seconds": form.display_seconds.data,
            "sort_order": form.sort_order.data,
            "is_active": True,
        },
    )


def update_ticker_message(message_id, form):
    patch_rows(
        "ticker_messages",
        {
            "content": form.content.data.strip(),
            "display_seconds": form.display_seconds.data,
            "sort_order": form.sort_order.data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        params={"id": f"eq.{message_id}"},
    )


def delete_ticker_message(message_id):
    delete_rows("ticker_messages", params={"id": f"eq.{message_id}"})
