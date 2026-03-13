from urllib.parse import urljoin

import requests
from flask import current_app


def _raise_for_status_with_context(response, table_name):
    if response.status_code == 404:
        raise RuntimeError(
            f"Supabase 테이블 또는 엔드포인트를 찾지 못했습니다: {table_name}. "
            "Supabase SQL Editor에서 supabase_schema.sql을 먼저 실행했는지 확인하세요."
        )
    response.raise_for_status()


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


def fetch_rows(table_name, params=None, use_service_role=True):
    response = requests.get(_endpoint(table_name), headers=_headers(use_service_role), params=params, timeout=20)
    _raise_for_status_with_context(response, table_name)
    return response.json()


def insert_row(table_name, payload, use_service_role=True):
    response = requests.post(
        _endpoint(table_name),
        headers=_headers(use_service_role, prefer="return=representation"),
        json=payload,
        timeout=20,
    )
    _raise_for_status_with_context(response, table_name)
    return response.json()


def patch_rows(table_name, payload, params=None, use_service_role=True):
    response = requests.patch(
        _endpoint(table_name),
        headers=_headers(use_service_role, prefer="return=representation"),
        params=params,
        json=payload,
        timeout=20,
    )
    _raise_for_status_with_context(response, table_name)
    return response.json()


def delete_rows(table_name, params=None, use_service_role=True):
    response = requests.delete(
        _endpoint(table_name),
        headers=_headers(use_service_role, prefer="return=representation"),
        params=params,
        timeout=20,
    )
    _raise_for_status_with_context(response, table_name)
    return response.json() if response.text else []