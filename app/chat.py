"""Chat loop for talking with the Sovereign Shard J."""

from __future__ import annotations

import ast
import re
from json import JSONDecodeError, dumps, loads
from pathlib import Path
from urllib.request import Request, urlopen

from app.client import RuntimeConfig, create_client
from app.file_tools import list_dir, read_file, write_file
from app.local_server import LocalLlamaServer
from app.session import SessionLogger
from app.system_tools import get_system_snapshot
from core.fivemasters import evaluate_code


BASE_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"

SYSTEM_PROMPT = (PROMPTS_DIR / "J-system.txt").read_text(encoding="utf-8")

TOOL_INSTRUCTIONS = (
    "\n\n[Tool Usage]\n"
    "You may use a local tool when you need to inspect or modify the repository. "
    "When a tool is required, respond with exactly the following format:\n"
    "ACTION:\n"
    "{\"tool\": \"<tool_name>\", \"args\": [arg1, arg2, ...]}\n"
    "Only use these tools when they are necessary. If no tool is needed, answer directly.\n"
    "Available tools:\n"
    "- read_file(path)\n"
    "- write_file(path, content)\n"
    "- list_dir(path)\n"
    "- system_snapshot()\n"
    "All paths are relative to the shard root unless an absolute path is provided."
)


def _assistant_role(client: RuntimeConfig) -> str:
    return "J" if client.backend == "llama_cpp" else "assistant"


def _system_role(client: RuntimeConfig) -> str:
    return "J" if client.backend == "llama_cpp" else "system"


def build_history(client: RuntimeConfig, system_context: str = ""):
    return [
        {
            "role": _system_role(client),
            "content": SYSTEM_PROMPT + TOOL_INSTRUCTIONS + (
                f"\n\n[Context]\n{system_context}"
                if system_context else ""
            ),
        }
    ]


def _extract_action(content: str) -> dict | None:
    if "ACTION:" not in content:
        return None

    payload = content.split("ACTION:", 1)[1].strip()
    if not payload:
        return None

    if match := re.search(r"\{.*\}", payload, flags=re.S):
        payload = match.group(0)

    try:
        return loads(payload)
    except JSONDecodeError:
        try:
            return ast.literal_eval(payload)
        except Exception:
            return None


def _execute_tool(action: dict) -> str:
    tool_name = action.get("tool")
    tool_args = action.get("args", [])

    if not tool_name:
        return "[TOOL ERROR] Tool name is missing."
    if not isinstance(tool_args, list):
        return "[TOOL ERROR] Tool args must be a list."

    tools = {
        "read_file": read_file,
        "write_file": write_file,
        "list_dir": list_dir,
        "system_snapshot": get_system_snapshot,
    }

    tool = tools.get(tool_name)
    if tool is None:
        return f"[TOOL ERROR] Unknown tool: {tool_name}"

    try:
        return str(tool(*tool_args))
    except Exception as error:
        return f"[TOOL ERROR] {tool_name} failed: {error}"


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
        raise RuntimeError(f"Connection failed: {error}") from error


def _llama_cpp_chat(client: RuntimeConfig, messages: list[dict[str, str]]):
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
        raise RuntimeError(f"Connection failed: {error}") from error


def _format_hardware_context() -> str:
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
    """Stream reply with safe interception layer."""
    reply_chunks = []

    def emit(token: str) -> None:
        print(token, end="", flush=True)

    def maybe_evaluate(content: str) -> str:
        """Five Masters gate (SAFE, scoped, non-crashing)."""
        if "def " in content or "class " in content:
            try:
                report = evaluate_code(content)
                if report.score() < 5:
                    return f"\n[FIVE MASTERS WARNING]\n{report}\n\n{content}"
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

        return "".join(reply_chunks)

    # --- fallback (ollama) ---
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

        return full_reply


def _run_turn(
    client: RuntimeConfig,
    messages: list[dict[str, str]],
    logger: SessionLogger,
    user_message: str,
) -> str:

    messages.append({"role": "user", "content": user_message})
    logger.append("user", user_message)

    reply = _stream_reply(client, messages)
    print()

    assistant_role = _assistant_role(client)
    messages.append({"role": assistant_role, "content": reply})
    logger.append("assistant", reply)

    action = _extract_action(reply)
    if action is None:
        return reply

    tool_result = _execute_tool(action)
    tool_response = (
        "[TOOL EXECUTION]\n"
        f"tool: {action.get('tool')}\n"
        f"args: {action.get('args', [])}\n"
        f"result:\n{tool_result}"
    )

    print(f"\n{tool_response}\n")
    messages.append({"role": assistant_role, "content": tool_response})
    logger.append("assistant", tool_response)

    continuation_prompt = (
        "Continue your answer using the tool result above. "
        "Do not repeat the tool invocation."
    )
    messages.append({"role": "user", "content": continuation_prompt})
    logger.append("user", continuation_prompt)

    final_reply = _stream_reply(client, messages)
    print()
    messages.append({"role": assistant_role, "content": final_reply})
    logger.append("assistant", final_reply)

    return final_reply


def run_chat(
    initial_message: str | None = None,
    runtime_state: dict | None = None,
) -> None:

    if runtime_state is None:
        runtime_state = {"sandbox_enabled": False}

    client = create_client()
    logger = SessionLogger(model=f"{client.backend}:{client.model}")
    messages = build_history(client, _format_hardware_context())
    local_server = LocalLlamaServer(client)

    try:
        local_server.ensure_started()

        print(f"--- SOVEREIGN SHARD ONLINE [{logger.session_id}] ---")
        print(f"Backend: {client.backend}")
        print(f"Model: {client.model}")
        print("Commands: quit, exit, /snapshot")

        if initial_message:
            print("\nJ.: ", end="", flush=True)
            _run_turn(client, messages, logger, initial_message)
            return

        while True:
            user_message = input("\nYou: ").strip()

            if user_message.lower() in {"quit", "exit"}:
                print(f"Session saved to {logger.transcript_path}")
                break

            if not user_message:
                continue

            if user_message == "/snapshot":
                snapshot = dumps(get_system_snapshot(), indent=2)
                print(snapshot)
                logger.append("system", snapshot)
                continue

            # sandbox toggle
            if user_message.lower() == "bruce wayne":
                runtime_state["sandbox_enabled"] = True
                print("\n[SANDBOX ENABLED]")
                continue

            if runtime_state.get("sandbox_enabled"):
                user_message = f"[SANDBOX] {user_message}"

            try:
                print("\nJ.: ", end="", flush=True)
                _run_turn(client, messages, logger, user_message)

            except RuntimeError as error:
                print(f"\nJ. Error: {error}")
                logger.append("error", str(error))

    finally:
        local_server.stop()