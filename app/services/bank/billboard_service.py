from ..shared import KST, parse_iso_datetime
from ..supabase_service import fetch_rows


def mask_depositor_name(name):
    compact = "".join(str(name or "").split())
    if not compact:
        return "입금자미상"
    if len(compact) == 1:
        return compact + "*"
    if len(compact) == 2:
        return compact[0] + "*"
    return compact[0] + ("*" * (len(compact) - 2)) + compact[-1]


def _date_label(value):
    parsed = parse_iso_datetime(value)
    if not parsed:
        return "-/-"
    localized = parsed.astimezone(KST)
    return f"{localized.month}/{localized.day}"


def build_billboard_message(transaction):
    masked_name = mask_depositor_name(transaction.get("deposit_name"))
    amount_text = f"{int(transaction.get('amount') or 0):,}"
    return f"[{_date_label(transaction.get('transaction_date'))}] {masked_name}님 {amount_text}원 입금자를 찾습니다."


def _list_billboard_transactions(limit=50):
    return fetch_rows(
        "bank_transactions",
        params={
            "select": "id,deposit_name,amount,transaction_date,status,is_billboard_approved",
            "status": "eq.UNMATCHED",
            "is_billboard_approved": "eq.true",
            "order": "transaction_date.desc,id.desc",
            "limit": str(limit),
        },
    )


def get_billboard_ticker_messages(limit=10):
    transactions = _list_billboard_transactions(limit=limit)

    messages = []
    for transaction in transactions[:limit]:
        messages.append(
            {
                "id": f"bank-{transaction['id']}",
                "transaction_id": transaction["id"],
                "content": build_billboard_message(transaction),
                "display_seconds": 4,
                "sort_order": 999,
                "is_active": True,
                "source_type": "BANK",
            }
        )
    return messages


def get_billboard_manage_messages(limit=50):
    return get_billboard_ticker_messages(limit=limit)