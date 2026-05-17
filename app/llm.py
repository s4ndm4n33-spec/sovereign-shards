# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""LLM backend communication layer.

Encapsulates Ollama and llama.cpp streaming, language drift detection,
and code evaluation gating.
"""

from json import dumps, loads
from urllib.request import Request, urlopen

from app.client import RuntimeConfig
from app import personality as persona
from app import ui
from app.agent.context import preflight_trim
from app.errors import TransportError
from core.fivemasters import evaluate_code


def _ollama_chat(client: RuntimeConfig, messages: list[dict[str, str]]):
    payload = {
        "model": client.model,
        "messages": messages,
        "stream": True,
        "keep_alive": client.keep_alive,
        "options": {
            "num_predict": client.num_predict,
            "num_ctx": client.num_ctx,
            "num_thread": client.num_thread,
            "temperature": client.temperature,
            "repeat_penalty": client.repeat_penalty,
        },
    }

    request = Request(
        url=f"{client.base_url}/api/chat",
        data=dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        return urlopen(request, timeout=300)
    except Exception as error:
        detail = str(error)
        # Read the actual response body for HTTP errors (4xx/5xx)
        if hasattr(error, "read"):
            try:
                body = error.read().decode("utf-8", errors="replace")[:500]
                if body:
                    detail = f"{detail}\n{body}"
            except Exception:
                pass
        raise TransportError("E_TRANSPORT", "Connection failed", detail) from error


def _llama_cpp_chat(client: RuntimeConfig, messages: list[dict[str, str]]):
    payload = {
        "model": client.model,
        "messages": messages,
        "stream": True,
        "max_tokens": client.num_predict,
        "temperature": client.temperature,
        "top_p": client.top_p,
        "stop": list(client.stop_tokens) + ["I am J"],
        "repeat_penalty": client.repeat_penalty,
        "frequency_penalty": client.repeat_penalty - 1.0,
    }

    request = Request(
        url=f"{client.base_url}/v1/chat/completions",
        data=dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        return urlopen(request, timeout=300)
    except Exception as error:
        detail = str(error)
        # Read the actual response body for HTTP errors (4xx/5xx)
        if hasattr(error, "read"):
            try:
                body = error.read().decode("utf-8", errors="replace")[:500]
                if body:
                    detail = f"{detail}\n{body}"
            except Exception:
                pass
        raise TransportError("E_TRANSPORT", "Connection failed", detail) from error


def _check_language_drift(reply: str, messages: list[dict[str, str]], client: RuntimeConfig) -> None:
    """Warn if the model drifted to a non-English language (CJK detection)."""
    sample = reply[:80]
    cjk_count = sum(1 for ch in sample if '\u4e00' <= ch <= '\u9fff' or '\u3040' <= ch <= '\u30ff')
    if cjk_count >= 3:
        sys_content = messages[0].get("content", "") if messages else ""
        sys_tokens = max(1, len(sys_content) // 4)
        budget = max(256, client.num_ctx - client.num_predict)
        print(f"\n{ui.warn_tag(persona.language_drift())}")
        print(f"  System prompt: ~{sys_tokens} tokens | Budget: {budget} tokens")


def stream_reply(client: RuntimeConfig, messages: list[dict[str, str]]) -> str:
    """Stream reply with pre-flight budget gate and Five Masters gate."""

    # ── Pre-flight: guarantee the payload fits the context window ──
    messages[:] = preflight_trim(messages, client.num_ctx, client.num_predict)

    reply_chunks: list[str] = []

    def emit(token: str) -> None:
        print(token, end="", flush=True)

    def maybe_evaluate(content: str) -> str:
        if "def " in content or "class " in content:
            try:
                report = evaluate_code(content)
                if report.score() < 5:
                    return f"\n[FIVE MASTERS WARNING]\n{report.summary()}\n\n{content}"
            except Exception:
                pass
        return content

    if client.backend == "llama_cpp":
        with _llama_cpp_chat(client, messages) as response:
            for raw_line in response:
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                chunk = loads(data)
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content") or ""
                if not content:
                    continue
                content = maybe_evaluate(content)
                emit(content)
                reply_chunks.append(content)
        result = persona.strip_bleed("".join(reply_chunks))
        _check_language_drift(result, messages, client)
        return result

    # Ollama fallback
    with _ollama_chat(client, messages) as response:
        full_reply = ""
        for line in response:
            if not line:
                continue
            chunk = loads(line.decode("utf-8"))
            if "message" in chunk:
                content = chunk["message"]["content"]
                emit(content)
                full_reply += content
            if chunk.get("done"):
                break
        full_reply = persona.strip_bleed(full_reply)
        _check_language_drift(full_reply, messages, client)
        return full_reply
