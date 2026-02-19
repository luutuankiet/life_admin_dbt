from __future__ import annotations

import shlex
from collections.abc import Iterable

from .schemas import CredentialProfileCreate


def _iter_headers(tokens: Iterable[str]) -> list[str]:
    pairs: list[str] = []
    tokens_list = list(tokens)
    for i, token in enumerate(tokens_list):
        if token in ("-H", "--header") and i + 1 < len(tokens_list):
            pairs.append(tokens_list[i + 1])
    return pairs


def parse_curl_profile(curl_text: str, account_id: str = "default") -> CredentialProfileCreate:
    tokens = shlex.split(curl_text)
    headers = _iter_headers(tokens)
    if not headers:
        raise ValueError("No headers found in curl text. Expected at least User-Agent and Cookie.")

    header_map: dict[str, str] = {}
    for item in headers:
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        header_map[key.strip().lower()] = value.strip()

    cookie_header = header_map.get("cookie")
    user_agent = header_map.get("user-agent")
    x_device = header_map.get("x-device")
    timezone = header_map.get("x-tz", "Asia/Ho_Chi_Minh")
    locale = header_map.get("hl", "en_US")
    csrf_header = header_map.get("x-csrftoken")

    if not cookie_header:
        raise ValueError("Cookie header is required.")
    if "t=" not in cookie_header:
        raise ValueError("Cookie header must include TickTick session token `t=`.")
    if not user_agent:
        raise ValueError("User-Agent header is required.")
    if not x_device:
        raise ValueError("X-Device header is required.")

    return CredentialProfileCreate(
        account_id=account_id,
        user_agent=user_agent,
        x_device=x_device,
        timezone=timezone,
        locale=locale,
        csrf_header=csrf_header,
        cookie_header=cookie_header,
    )