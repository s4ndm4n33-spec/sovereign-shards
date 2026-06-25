"""Crawler for shared chat links.

Supports:
  - ChatGPT shared links (chat.openai.com/share/*, chatgpt.com/share/*)
  - Claude shared links (claude.ai/share/*)
  - Gemini shared links (g.co/gemini/share/*, gemini.google.com/share/*)
  - Generic URLs whose HTML embeds a transcript

Strategy:
  1. Detect provider from the URL host.
  2. Try a lightweight HTTP fetch first (urllib). Many share pages embed
     the conversation as JSON-LD or text in the initial HTML.
  3. If the lightweight fetch yields nothing usable, fall back to a
     headless Chromium (selenium) render to execute client-side JS, then
     re-extract from the fully-rendered DOM.

The crawler never executes user content — it only renders the page that
the link points to, exactly as a browser would.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

from .models import Conversation, Message

log = logging.getLogger("vic.crawler")

# Browser-like headers so share endpoints don't return a bare 403.
_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_RENDER_TIMEOUT = 25  # seconds for headless render
_LIGHT_TIMEOUT = 15


@dataclass
class CrawlError(Exception):
    """Raised when a chat URL cannot be fetched or parsed."""

    url: str
    reason: str

    def __str__(self) -> str:  # noqa: D401
        return f"Crawl failed for {self.url}: {self.reason}"


def detect_provider_from_url(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    if "openai.com" in host or "chatgpt.com" in host:
        return "chatgpt"
    if "claude.ai" in host or "anthropic" in host:
        return "claude"
    if "gemini.google" in host or "g.co/gemini" in url.lower() or "aistudio.google" in host:
        return "gemini"
    return "unknown"


def _detect_provider_from_html(url: str, html: str) -> str:
    """Refine provider detection using page-content signals.

    Used when the URL host is unrecognised (e.g. a mirror, a local test
    fixture, or an alias) so the correct DOM extractor still runs.
    """
    url_provider = detect_provider_from_url(url)
    if url_provider != "unknown":
        return url_provider
    low = html.lower()
    if 'data-message-author-role' in low or 'chatgpt' in low or 'openai' in low:
        return "chatgpt"
    if 'font-user' in low and 'font-claude' in low or 'claude' in low:
        return "claude"
    if 'gemini' in low or 'my activity' in low:
        return "gemini"
    return "unknown"


def crawl_chat_url(url: str) -> Conversation:
    """Fetch a shared chat link and return a normalized Conversation.

    Raises :class:`CrawlError` if the page can't be reached or yields no
    conversation content.
    """
    provider = detect_provider_from_url(url)
    log.info("Crawling %s as %s", url, provider)

    # 1. Lightweight fetch
    html = _fetch_html(url)
    conv = _extract_from_html(url, provider, html)

    # 2. Headless fallback for JS-rendered shares
    if conv is None or not conv.messages:
        log.info("Lightweight fetch empty — falling back to headless render")
        rendered = _render_headless(url)
        if rendered:
            conv = _extract_from_html(url, provider, rendered) or conv

    if conv is None or not conv.messages:
        raise CrawlError(url, "No conversation content found in the shared page")

    return conv


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

def _fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=_LIGHT_TIMEOUT) as resp:
            # Some share endpoints 403 the bare UA; selenium path handles those.
            ctype = resp.headers.get("Content-Type", "")
            if "text/html" not in ctype and "json" not in ctype:
                log.info("Non-HTML content-type for %s: %s", url, ctype)
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:  # noqa: BLE001
        log.warning("Lightweight fetch failed for %s: %s", url, exc)
        return ""


def _render_headless(url: str) -> str:
    """Render a URL with headless Chromium and return the DOM HTML.

    Gracefully degrades: if selenium/chromium isn't installed, returns "".
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
    except ImportError:
        log.warning("selenium not installed — cannot render JS-heavy pages")
        return ""

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--user-agent={_UA}")
    # Find a chrome/chromium binary
    for binname in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        import shutil

        path = shutil.which(binname)
        if path:
            options.binary_location = path
            break

    try:
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as exc:  # noqa: BLE001
        log.warning("Headless browser unavailable: %s", exc)
        return ""

    try:
        driver.set_page_load_timeout(_RENDER_TIMEOUT)
        driver.get(url)
        # Give client-side renderers time to populate the DOM.
        time.sleep(4)
        # ChatGPT and Claude both stream; wait for stable message count.
        _wait_for_stable_dom(driver)
        return driver.page_source or ""
    except Exception as exc:  # noqa: BLE001
        log.warning("Headless render error for %s: %s", url, exc)
        return ""
    finally:
        try:
            driver.quit()
        except Exception:  # noqa: BLE001
            pass


def _wait_for_stable_dom(driver, max_iters: int = 6, delay: float = 1.0) -> None:
    """Pause until the rendered DOM stops changing (or max_iters).

    Compares the page height + text length across short intervals. When
    they stabilize, the streamed transcript has finished loading.
    """
    prev_len = 0
    prev_h = 0
    for _ in range(max_iters):
        try:
            body_text = driver.execute_script("return document.body ? document.body.innerText.length : 0") or 0
            body_h = driver.execute_script("return document.body ? document.body.scrollHeight : 0") or 0
        except Exception:  # noqa: BLE001
            break
        if body_text == prev_len and body_h == prev_h:
            break
        prev_len, prev_h = body_text, body_h
        time.sleep(delay)


# ---------------------------------------------------------------------------
# Extraction from rendered HTML
# ---------------------------------------------------------------------------

# Many share pages embed the conversation as JSON-LD or a <script> blob.
_EMBEDDED_JSON_RE = re.compile(
    r"<script[^>]*type=\"application/(?:ld\+)?json\"[^>]*>(.*?)</script>",
    re.DOTALL | re.IGNORECASE,
)


def _extract_from_html(url: str, provider: str, html: str) -> Conversation | None:
    if not html:
        return None
    # Refine provider using page content when the URL host was unrecognised
    provider = _detect_provider_from_html(url, html) or provider
    # 1. Try embedded JSON-LD / __NEXT_DATA__ blobs
    conv = _extract_embedded_json(url, provider, html)
    if conv and conv.messages:
        return conv
    # 2. Provider-specific DOM selectors
    if provider == "chatgpt":
        conv = _extract_chatgpt_dom(url, html)
    elif provider == "claude":
        conv = _extract_claude_dom(url, html)
    elif provider == "gemini":
        conv = _extract_gemini_dom(url, html)
    else:
        # Unknown provider: try each extractor in turn
        for extractor in (_extract_chatgpt_dom, _extract_claude_dom, _extract_gemini_dom, _extract_generic_dom):
            conv = extractor(url, html)
            if conv and conv.messages:
                return conv
        return None
    return conv


def _extract_embedded_json(url: str, provider: str, html: str) -> Conversation | None:
    for match in _EMBEDDED_JSON_RE.finditer(html):
        raw = match.group(1).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        conv = _conversation_from_json_blob(url, provider, data)
        if conv and conv.messages:
            return conv

    # Next.js __NEXT_DATA__
    next_match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if next_match:
        try:
            data = json.loads(next_match.group(1).strip())
            # Walk props looking for message-shaped subtrees
            conv = _conversation_from_json_blob(url, provider, data)
            if conv and conv.messages:
                return conv
        except json.JSONDecodeError:
            pass

    return None


def _conversation_from_json_blob(url: str, provider: str, data) -> Conversation | None:
    """Recursively search a JSON blob for a message list and normalize it."""
    found = _find_message_list(data)
    if not found:
        return None
    msgs: list[Message] = []
    for m in found:
        if not isinstance(m, dict):
            continue
        role = (m.get("author") or {}).get("role") if isinstance(m.get("author"), dict) else m.get("role") or m.get("sender")
        # Normalize roles
        if role in ("human", "user"):
            role = "user"
        elif role in ("assistant", "ai", "model", "bot"):
            role = "assistant"
        content = m.get("text") or m.get("content") or _coerce_parts(m.get("content") or m.get("parts"))
        if isinstance(content, list):
            content = _coerce_parts(content)
        if not isinstance(content, str) or not content.strip():
            continue
        ts = _parse_ts(m.get("create_time") or m.get("created_at") or m.get("timestamp"))
        msgs.append(Message(role=role or "user", content=content.strip(), timestamp=ts))

    if not msgs:
        return None

    title = _find_title(data) or "Shared chat"
    return Conversation(
        provider=provider,
        source_file=url,
        raw_id=url,
        title=title,
        messages=msgs,
        created=msgs[0].timestamp,
        updated=msgs[-1].timestamp,
    )


def _find_message_list(node, depth: int = 0):
    """Recursively locate a list of message dicts within a JSON tree.

    Heuristic: a list whose elements are dicts containing a recognizable
    content/text key plus author or role.
    """
    if depth > 12:
        return None
    if isinstance(node, list):
        # Check if this looks like a message list itself
        if node and all(isinstance(x, dict) for x in node[:5]):
            if any(("content" in x or "text" in x or "parts" in x) and ("author" in x or "role" in x or "sender" in x) for x in node[:5]):
                return node
        # Otherwise recurse into elements
        for item in node:
            found = _find_message_list(item, depth + 1)
            if found:
                return found
    elif isinstance(node, dict):
        for key in ("mapping", "messages", "chat_messages", "turns", "messages"):
            v = node.get(key)
            if isinstance(v, (list, dict)):
                found = _find_message_list(v, depth + 1)
                if found:
                    return found
        # Recurse all values
        for v in node.values():
            found = _find_message_list(v, depth + 1)
            if found:
                return found
    return None


def _find_title(node) -> str | None:
    if isinstance(node, dict):
        for k in ("title", "name", "subject"):
            v = node.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def _coerce_parts(parts) -> str:
    if isinstance(parts, str):
        return parts
    if isinstance(parts, list):
        joined = []
        for p in parts:
            if isinstance(p, str):
                joined.append(p)
            elif isinstance(p, dict):
                t = p.get("text") or p.get("value") or p.get("content")
                if isinstance(t, str):
                    joined.append(t)
        return "\n".join(j for j in joined if j)
    return ""


def _parse_ts(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value) / 1000.0 if value > 1e12 else float(value))
        except (OSError, ValueError, OverflowError, ArithmeticError):
            return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return None


# ---------------------------------------------------------------------------
# DOM fallbacks (provider-specific CSS-ish extraction)
# ---------------------------------------------------------------------------

from html.parser import HTMLParser  # noqa: E402


def _strip_tags(html_fragment: str) -> str:
    out: list[str] = []
    class _Strip(HTMLParser):
        def handle_data(self, data: str) -> None:  # noqa: D401
            out.append(data)
    _Strip().feed(html_fragment)
    return "".join(out)


def _extract_chatgpt_dom(url: str, html: str) -> Conversation | None:
    # ChatGPT shares use class names like "markdown ... prose ..." in messages
    # but the safest signal is alternating [data-message-author-role] attributes.
    blocks = re.findall(r'data-message-author-role="([^"]+)"[^>]*>(.*?)</div>', html, re.DOTALL)
    msgs: list[Message] = []
    for role, body in blocks:
        text = _strip_tags(body).strip()
        if not text:
            continue
        if role == "user":
            msgs.append(Message(role="user", content=text))
        else:
            msgs.append(Message(role="assistant", content=text))
    if not msgs:
        # Fallback: text nodes between conversation borders
        return _fallback_text_extraction(url, "chatgpt", html, prompt_marker="human:", response_marker="assistant:")
    title = _title_from_html(html) or "ChatGPT shared chat"
    return Conversation(provider="chatgpt", source_file=url, raw_id=url, title=title, messages=msgs)


def _extract_claude_dom(url: str, html: str) -> Conversation | None:
    # Claude shares wrap turns in elements with font-user / font-claude classes
    user_blocks = re.findall(r'class="[^"]*font-user[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    asst_blocks = re.findall(r'class="[^"]*font-claude[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    msgs: list[Message] = []
    for body in user_blocks:
        text = _strip_tags(body).strip()
        if text:
            msgs.append(Message(role="user", content=text))
    for body in asst_blocks:
        text = _strip_tags(body).strip()
        if text:
            msgs.append(Message(role="assistant", content=text))
    if not msgs:
        return _fallback_text_extraction(url, "claude", html, prompt_marker="human:", response_marker="assistant:")
    title = _title_from_html(html) or "Claude shared chat"
    return Conversation(provider="claude", source_file=url, raw_id=url, title=title, messages=msgs)


def _extract_gemini_dom(url: str, html: str) -> Conversation | None:
    # Gemini shares don't expose clean attributes; fall back to heuristic
    conv = _fallback_text_extraction(url, "gemini", html, prompt_marker="you:", response_marker="model:")
    if conv:
        conv.title = _title_from_html(html) or "Gemini shared chat"
    return conv


def _extract_generic_dom(url: str, html: str) -> Conversation | None:
    return _fallback_text_extraction(url, "unknown", html, prompt_marker="user:", response_marker="assistant:")


def _title_from_html(html: str) -> str | None:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    if m:
        title = _strip_tags(m.group(1)).strip()
        if title:
            return title[:200]
    # og:title
    m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html)
    if m:
        return m.group(1).strip()[:200]
    return None


def _fallback_text_extraction(url: str, provider: str, html: str, prompt_marker: str, response_marker: str) -> Conversation | None:
    """Last-resort text extraction: strip HTML, split on role markers."""
    text = _strip_tags(html)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Split into alternating segments on role markers
    pattern = re.compile(rf"({re.escape(prompt_marker)}|{re.escape(response_marker)})", re.IGNORECASE)
    parts = pattern.split(text)
    msgs: list[Message] = []
    current_role: str | None = None
    buffer: list[str] = []
    for part in parts:
        stripped = part.strip()
        if not stripped:
            continue
        if stripped.lower() in (prompt_marker.lower(), response_marker.lower()):
            if current_role and buffer:
                msgs.append(Message(role="user" if current_role == "user" else "assistant", content="\n".join(buffer).strip()))
            current_role = "user" if stripped.lower() == prompt_marker.lower() else "assistant"
            buffer = []
        else:
            if current_role:
                buffer.append(stripped)
    if current_role and buffer:
        msgs.append(Message(role="user" if current_role == "user" else "assistant", content="\n".join(buffer).strip()))
    # Filter trivial fragments
    msgs = [m for m in msgs if len(m.content) > 3]
    if not msgs:
        return None
    return Conversation(provider=provider, source_file=url, raw_id=url, title=_title_from_html(html) or "Shared chat", messages=msgs)
