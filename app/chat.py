"""Chat loop for talking with the Sovereign Shard assistant."""

from __future__ import annotations

from json import dumps, loads
from pathlib import Path
from urllib.request import Request, urlopen

from app.client import RuntimeConfig, create_client
from app.errors import TransportError
from app.local_server import LocalLlamaServer
from app.runtime_log import RuntimeJsonLogger
from app.session import SessionLogger
from app.system_tools import get_system_snapshot

BASE_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"
SYSTEM_PROMPT = (PROMPTS_DIR / "system.txt").read_text(encoding="utf-8")
DEVELOPER_PROMPT = (PROMPTS_DIR / "developer.txt").read_text(encoding="utf-8")
COMBINED_SYSTEM_PROMPT = f"{SYSTEM_PROMPT}\n\n{DEVELOPER_PROMPT}"


def build_history(system_context: str = "") -> list[dict[str, str]]:
    """Build the initial chat history."""
    history = [{"role": "system", "content": COMBINED_SYSTEM_PROMPT}]
    if system_context:
        history.append({"role": "system", "content": system_context})
    return history


def _ollama_chat(client: RuntimeConfig, messages: list[dict[str, str]]):
    """Send a chat request to an Ollama-compatible endpoint."""
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
        raise TransportError("E_TRANSPORT_CONNECT", "Connection failed", str(error)) from error


def _llama_cpp_chat(client: RuntimeConfig, messages: list[dict[str, str]]):
    """Send a chat request to the local llama.cpp server."""
    payload = {
        "model": client.model,
        "messages": messages,
        "stream": True,
        "max_tokens": client.num_predict,
        "temperature": client.temperature,
        "top_p": client.top_p,
        "stop": list(client.stop_tokens),
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
        raise TransportError("E_TRANSPORT_CONNECT", "Connection failed", str(error)) from error


def _format_hardware_context() -> str:
    """Create the system context injected into the chat."""
    snapshot = get_system_snapshot()
    if snapshot.get("status") != "ONLINE":
        return "[Sovereign Identity Unavailable]"

    return (
        "\n[Sovereign Identity Verified]\n"
        f"Node: {snapshot['network']['node_name']}\n"
        f"CPU: {snapshot['host_machine']['cpu']}\n"
        f"Memory: {snapshot['live_metrics']['ram_usage_percent']} used of "
        f"{snapshot['host_machine']['ram_total_gb']}GB\n"
        f"Storage: {snapshot['live_metrics']['disk_free_gb']}GB free on local disk.\n"
    )


def _stream_reply(client: RuntimeConfig, messages: list[dict[str, str]]) -> str:
    """Stream a reply from the configured backend."""
    reply = ""
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
                if content:
                    print(content, end="", flush=True)
                    reply += content
        return reply

    with _ollama_chat(client, messages) as response:
        for line in response:
            if not line:
                continue
            chunk = loads(line.decode("utf-8"))
            if "message" in chunk:
                content = chunk["message"]["content"]
                print(content, end="", flush=True)
                reply += content
            if chunk.get("done"):
                break
    return reply


def _stage_input(messages: list[dict[str, str]], logger: SessionLogger, user_message: str) -> None:
    messages.append({"role": "user", "content": user_message})
    logger.append("user", user_message)


def _stage_model_reply(client: RuntimeConfig, messages: list[dict[str, str]]) -> str:
    return _stream_reply(client, messages)


def _stage_commit_reply(messages: list[dict[str, str]], logger: SessionLogger, reply: str) -> None:
    print()
    messages.append({"role": "assistant", "content": reply})
    logger.append("assistant", reply)


def _run_turn(
    client: RuntimeConfig,
    messages: list[dict[str, str]],
    logger: SessionLogger,
    runtime_logger: RuntimeJsonLogger,
    user_message: str,
) -> str:
    """Run a single conversation turn through explicit pipeline stages."""
    runtime_logger.event("stage_start", stage="input_normalization")
    _stage_input(messages, logger, user_message)

    runtime_logger.event("stage_start", stage="executor")
    reply = _stage_model_reply(client, messages)

    runtime_logger.event("stage_start", stage="memory_writer")
    _stage_commit_reply(messages, logger, reply)

    runtime_logger.event("turn_complete", chars=len(reply))
    return reply


def run_chat(initial_message: str | None = None) -> None:
    """Run the interactive chat loop with real-time streaming."""
    client = create_client()
    logger = SessionLogger(model=f"{client.backend}:{client.model}")
    runtime_logger = RuntimeJsonLogger(session_id=logger.session_id)
    messages = build_history(_format_hardware_context())
    local_server = LocalLlamaServer(client)

    try:
        runtime_logger.event("startup", backend=client.backend, model=client.model)
        local_server.ensure_started()

        print(f"--- SOVEREIGN SHARD ONLINE [{logger.session_id}] ---")
        print(f"Backend: {client.backend}")
        print(f"Model: {client.model}")
        print("Commands: quit, exit, /snapshot")

        if initial_message:
            print("\nJ.: ", end="", flush=True)
            _run_turn(client, messages, logger, runtime_logger, initial_message)
            return

        while True:
            user_message = input("\nYou: ").strip()
            if user_message.lower() in {"quit", "exit"}:
                print(f"Session saved to {logger.transcript_path}")
                runtime_logger.event("shutdown", reason="user_exit")
                break
            if not user_message:
                continue
            if user_message == "/snapshot":
                snapshot = dumps(get_system_snapshot(), indent=2)
                print(snapshot)
                logger.append("system", snapshot)
                runtime_logger.event("snapshot", length=len(snapshot))
                continue
            try:
                print("\nJ.: ", end="", flush=True)
                _run_turn(client, messages, logger, runtime_logger, user_message)
            except TransportError as error:
                print(f"\nJ. Error: {error}")
                logger.append("error", str(error))
                runtime_logger.event("error", code=error.code, message=error.message)
    finally:
        local_server.stop()
