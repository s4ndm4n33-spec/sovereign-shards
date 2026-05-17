"""GitHub Models API adapter for J."""

from __future__ import annotations

import os
from typing import Any

import httpx


GITHUB_MODELS_URL = "https://models.inference.ai.azure.com/chat/completions"


def chat(model: str, messages: list[dict[str, str]]) -> str:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "[J ERROR] GITHUB_TOKEN is not set."

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2048,
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    timeout = httpx.Timeout(60.0, connect=10.0)
    try:
        response = httpx.post(GITHUB_MODELS_URL, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return "[J ERROR] No choices returned from GitHub Models API."
        first = choices[0]
        message = first.get("message") or {}
        content = message.get("content")
        if content is None:
            return "[J ERROR] Missing message content in GitHub Models response."
        return str(content)
    except httpx.TimeoutException:
        return "[J ERROR] GitHub Models API request timed out."
    except httpx.HTTPStatusError as error:
        body = error.response.text[:500]
        return f"[J ERROR] GitHub Models API HTTP error: {error.response.status_code}. {body}"
    except Exception as error:
        return f"[J ERROR] Unexpected GitHub Models API failure: {error}"
