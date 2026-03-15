from datetime import datetime, timezone

from flask import current_app

from ..shared import format_kst_datetime, parse_iso_datetime
from ..supabase_service import delete_rows, fetch_rows, insert_row, patch_rows
from .notification_service import send_telegram_inquiry_alert


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


def create_inquiry(name, phone, apt_dong, apt_ho, content, consent_agreed=True):
    now = datetime.now(timezone.utc).isoformat()
    request_key = _build_request_key(name, phone, apt_dong, apt_ho)
    consent_granted = bool(consent_agreed)
    thread = fetch_rows(
        "inquiries",
        params={"select": "id,consent_agreed,consent_agreed_at", "request_key": f"eq.{request_key}"},
    )

    if thread:
        inquiry_id = thread[0]["id"]
        payload = {"status": "PENDING", "latest_message_at": now, "updated_at": now}
        if consent_granted and not thread[0].get("consent_agreed_at"):
            payload["consent_agreed"] = True
            payload["consent_agreed_at"] = now
        patch_rows("inquiries", payload, params={"id": f"eq.{inquiry_id}"})
    else:
        created = insert_row(
            "inquiries",
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
        inquiry_id = created[0]["id"]

    insert_row(
        "inquiry_messages",
        {
            "inquiry_id": inquiry_id,
            "author_type": "USER",
            "content": content.strip(),
            "created_at": now,
        },
    )
    try:
        send_telegram_inquiry_alert(apt_dong.strip(), apt_ho.strip(), name.strip(), content.strip())
    except Exception:
        current_app.logger.exception("텔레그램 문의사항 알림 전송에 실패했습니다.")


def list_inquiries(name=None, phone=None, apt_dong=None, apt_ho=None):
    params = {"select": "*"}
    if name and phone and apt_dong and apt_ho:
        request_key = _build_request_key(name, phone, apt_dong, apt_ho)
        params["request_key"] = f"eq.{request_key}"
    threads = fetch_rows("inquiries", params=params)
    if not threads:
        return []

    inquiry_ids = ",".join(str(thread["id"]) for thread in threads)
    messages = fetch_rows(
        "inquiry_messages",
        params={"select": "*", "inquiry_id": f"in.({inquiry_ids})", "order": "created_at.desc"},
    )
    message_map = {}
    for message in messages:
        message_map.setdefault(message["inquiry_id"], []).append(message)

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


def add_inquiry_reply(thread_id, content):
    thread = fetch_rows("inquiries", params={"select": "id", "id": f"eq.{thread_id}"})
    if not thread:
        raise ValueError("문의글을 찾을 수 없습니다.")

    now = datetime.now(timezone.utc).isoformat()
    insert_row(
        "inquiry_messages",
        {
            "inquiry_id": thread[0]["id"],
            "author_type": "ADMIN",
            "content": content.strip(),
            "created_at": now,
        },
    )
    patch_rows(
        "inquiries",
        {"status": "ANSWERED", "latest_message_at": now, "updated_at": now},
        params={"id": f"eq.{thread[0]['id']}"},
    )


def update_inquiry_message(message_id, thread_id, content):
    thread = fetch_rows("inquiries", params={"select": "id", "id": f"eq.{thread_id}"})
    if not thread:
        raise ValueError("문의글을 찾을 수 없습니다.")

    message = fetch_rows(
        "inquiry_messages",
        params={"select": "id,inquiry_id", "id": f"eq.{message_id}", "inquiry_id": f"eq.{thread_id}"},
    )
    if not message:
        raise ValueError("수정할 문의/답변 내용을 찾을 수 없습니다.")

    now = datetime.now(timezone.utc).isoformat()
    patch_rows("inquiry_messages", {"content": content.strip()}, params={"id": f"eq.{message_id}"})
    patch_rows("inquiries", {"latest_message_at": now, "updated_at": now}, params={"id": f"eq.{thread_id}"})


def delete_inquiry_message(message_id, thread_id):
    thread = fetch_rows("inquiries", params={"select": "id,status", "id": f"eq.{thread_id}"})
    if not thread:
        raise ValueError("문의글을 찾을 수 없습니다.")

    message = fetch_rows(
        "inquiry_messages",
        params={"select": "id,inquiry_id", "id": f"eq.{message_id}", "inquiry_id": f"eq.{thread_id}"},
    )
    if not message:
        raise ValueError("삭제할 문의/답변 내용을 찾을 수 없습니다.")

    delete_rows("inquiry_messages", params={"id": f"eq.{message_id}"})
    remaining_messages = fetch_rows(
        "inquiry_messages",
        params={"select": "id,author_type,created_at", "inquiry_id": f"eq.{thread_id}", "order": "created_at.desc,id.desc"},
    )
    if not remaining_messages:
        delete_rows("inquiries", params={"id": f"eq.{thread_id}"})
        return

    latest_message_at = remaining_messages[0].get("created_at")
    has_admin_reply = any(message.get("author_type") == "ADMIN" for message in remaining_messages)
    now = datetime.now(timezone.utc).isoformat()
    patch_rows(
        "inquiries",
        {
            "status": "ANSWERED" if has_admin_reply else "PENDING",
            "latest_message_at": latest_message_at or now,
            "updated_at": now,
        },
        params={"id": f"eq.{thread_id}"},
    )


def inquiry_status_label(status):
    return {"PENDING": "확인대기", "ANSWERED": "답변완료"}.get(status, status)