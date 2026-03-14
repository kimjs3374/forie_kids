from urllib.parse import urljoin

import requests
from flask import current_app
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class SupabaseRequestError(RuntimeError):
    def __init__(self, message, status_code=None, response_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


_SUPABASE_SESSION = None


def _get_session():
    global _SUPABASE_SESSION
    if _SUPABASE_SESSION is None:
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.5,
            status_forcelist=(408, 429, 500, 502, 503, 504),
            allowed_methods=frozenset({"DELETE", "GET", "HEAD", "PATCH", "POST"}),
        )
        adapter = HTTPAdapter(max_retries=retry)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        _SUPABASE_SESSION = session
    return _SUPABASE_SESSION


def _read_error_payload(response):
    try:
        payload = response.json()
        return payload if isinstance(payload, dict) else {"data": payload}
    except ValueError:
        text = (response.text or "").strip()
        return {"message": text[:500]} if text else {}


def _request(method, url, *, headers=None, params=None, json=None, timeout=20):
    return _get_session().request(method, url, headers=headers, params=params, json=json, timeout=timeout)


def _raise_for_status_with_context(response, table_name):
    if response.status_code == 404:
        raise RuntimeError(
            f"Supabase 테이블 또는 엔드포인트를 찾지 못했습니다: {table_name}. "
            "Supabase SQL Editor에서 supabase_schema.sql을 먼저 실행했는지 확인하세요."
        )
    if response.status_code >= 400:
        payload = _read_error_payload(response)
        detail = payload.get("details") or payload.get("message") or payload.get("hint") or "알 수 없는 오류"
        raise SupabaseRequestError(
            f"Supabase 요청 실패({table_name}): {detail}",
            status_code=response.status_code,
            response_data=payload,
        )


def _headers(use_service_role=True, prefer=None):
    key = (
        current_app.config["SUPABASE_SERVICE_ROLE_KEY"]
        if use_service_role
        else current_app.config["SUPABASE_ANON_KEY"]
    )
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _endpoint(table_name):
    return urljoin(current_app.config["SUPABASE_URL"].rstrip("/") + "/", f"rest/v1/{table_name}")


def _rpc_endpoint(function_name):
    return urljoin(current_app.config["SUPABASE_URL"].rstrip("/") + "/", f"rest/v1/rpc/{function_name}")


def fetch_rows(table_name, params=None, use_service_role=True):
    response = _request("GET", _endpoint(table_name), headers=_headers(use_service_role), params=params, timeout=20)
    _raise_for_status_with_context(response, table_name)
    return response.json()


def insert_row(table_name, payload, use_service_role=True):
    response = _request(
        "POST",
        _endpoint(table_name),
        headers=_headers(use_service_role, prefer="return=representation"),
        json=payload,
        timeout=20,
    )
    _raise_for_status_with_context(response, table_name)
    return response.json()


def patch_rows(table_name, payload, params=None, use_service_role=True):
    response = _request(
        "PATCH",
        _endpoint(table_name),
        headers=_headers(use_service_role, prefer="return=representation"),
        params=params,
        json=payload,
        timeout=20,
    )
    _raise_for_status_with_context(response, table_name)
    return response.json()


def delete_rows(table_name, params=None, use_service_role=True):
    response = _request(
        "DELETE",
        _endpoint(table_name),
        headers=_headers(use_service_role, prefer="return=representation"),
        params=params,
        timeout=20,
    )
    _raise_for_status_with_context(response, table_name)
    return response.json() if response.text else []


def count_rows(table_name, params=None, use_service_role=True):
    query_params = dict(params or {})
    query_params.setdefault("select", "id")
    headers = _headers(use_service_role)
    headers["Prefer"] = "count=exact"
    response = _request("HEAD", _endpoint(table_name), headers=headers, params=query_params, timeout=20)
    _raise_for_status_with_context(response, table_name)

    content_range = str(response.headers.get("Content-Range") or "")
    if "/" not in content_range:
        return 0
    total_text = content_range.rsplit("/", 1)[-1].strip()
    return int(total_text) if total_text.isdigit() else 0


def call_rpc(function_name, payload=None, use_service_role=True):
    response = _request(
        "POST",
        _rpc_endpoint(function_name),
        headers=_headers(use_service_role),
        json=payload or {},
        timeout=30,
    )
    _raise_for_status_with_context(response, function_name)
    return response.json() if response.text else []