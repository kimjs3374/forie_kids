from datetime import datetime, timezone

from flask import current_app

from ..shared import format_kst_datetime, parse_iso_datetime
from ..supabase_service import fetch_rows, insert_row, patch_rows
from .notification_service import send_telegram_deposit_request_alert


def _build_request_key(name, phone, apt_dong, apt_ho):
    return f"{name.strip()}|{phone.strip()}|{apt_dong.strip()}|{apt_ho.strip()}"


def _format_thread(thread):
    formatted = dict(thread)
    messages = sorted(thread.get("messages", []), key=lambda item: item.get("created_at", ""), reverse=True)
    formatted_messages = []
    for message in messages:
        item = dict(message)
        item["created_at_display"] = format_kst_datetime(message.get("created_at"))
        formatted_messages.append(item)
    formatted["messages"] = formatted_messages
    formatted["latest_message_at_display"] = format_kst_datetime(thread.get("latest_message_at"))
    return formatted


def create_payment_request(name, phone, apt_dong, apt_ho, content, consent_agreed=True):
    now = datetime.now(timezone.utc).isoformat()
    request_key = _build_request_key(name, phone, apt_dong, apt_ho)
    consent_granted = bool(consent_agreed)
    thread = fetch_rows(
        "deposit_requests",
        params={"select": "id,consent_agreed,consent_agreed_at", "request_key": f"eq.{request_key}"},
    )

    if thread:
        request_id = thread[0]["id"]
        payload = {"status": "PENDING", "latest_message_at": now, "updated_at": now}
        if consent_granted and not thread[0].get("consent_agreed_at"):
            payload["consent_agreed"] = True
            payload["consent_agreed_at"] = now
        patch_rows("deposit_requests", payload, params={"id": f"eq.{request_id}"})
    else:
        created = insert_row(
            "deposit_requests",
            {
                "request_key": request_key,
                "name": name.strip(),
                "phone": phone.strip(),
                "apt_dong": apt_dong.strip(),
                "apt_ho": apt_ho.strip(),
                "consent_agreed": consent_granted,
                "consent_agreed_at": now if consent_granted else None,
                "status": "PENDING",
                "latest_message_at": now,
            },
        )
        request_id = created[0]["id"]

    insert_row(
        "deposit_request_messages",
        {
            "request_id": request_id,
            "author_type": "USER",
            "content": content.strip(),
            "created_at": now,
        },
    )
    try:
        send_telegram_deposit_request_alert(apt_dong.strip(), apt_ho.strip(), name.strip(), content.strip())
    except Exception:
        current_app.logger.exception("텔레그램 입금확인요청 알림 전송에 실패했습니다.")


def list_payment_requests(name=None, phone=None, apt_dong=None, apt_ho=None):
    params = {"select": "*"}
    if name and phone and apt_dong and apt_ho:
        request_key = _build_request_key(name, phone, apt_dong, apt_ho)
        params["request_key"] = f"eq.{request_key}"
    threads = fetch_rows("deposit_requests", params=params)
    if not threads:
        return []

    request_ids = ",".join(str(thread["id"]) for thread in threads)
    messages = fetch_rows(
        "deposit_request_messages",
        params={"select": "*", "request_id": f"in.({request_ids})", "order": "created_at.desc"},
    )
    message_map = {}
    for message in messages:
        message_map.setdefault(message["request_id"], []).append(message)

    for thread in threads:
        thread_messages = message_map.get(thread["id"], [])
        thread["messages"] = thread_messages

        latest_candidates = [candidate for candidate in [parse_iso_datetime(thread.get("latest_message_at"))] if candidate]
        latest_candidates.extend(
            parsed for parsed in (parse_iso_datetime(message.get("created_at")) for message in thread_messages) if parsed
        )
        latest_message_at = max(latest_candidates) if latest_candidates else None
        if latest_message_at:
            thread["latest_message_at"] = latest_message_at.isoformat()

    threads.sort(
        key=lambda thread: parse_iso_datetime(thread.get("latest_message_at")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return [_format_thread(item) for item in threads]


def add_payment_request_reply(thread_id, content):
    thread = fetch_rows("deposit_requests", params={"select": "id", "id": f"eq.{thread_id}"})
    if not thread:
        raise ValueError("입금확인요청 글을 찾을 수 없습니다.")

    now = datetime.now(timezone.utc).isoformat()
    insert_row(
        "deposit_request_messages",
        {
            "request_id": thread[0]["id"],
            "author_type": "ADMIN",
            "content": content.strip(),
            "created_at": now,
        },
    )
    patch_rows(
        "deposit_requests",
        {"status": "ANSWERED", "latest_message_at": now, "updated_at": now},
        params={"id": f"eq.{thread[0]['id']}"},
    )


def payment_request_status_label(status):
    return {
        "PENDING": "확인대기",
        "ANSWERED": "답변완료",
    }.get(status, status)
