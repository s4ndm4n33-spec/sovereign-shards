"""Runtime configuration helpers for the Sovereign Shard."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent


def _resolve_path(value: str | Path, default: str | Path) -> Path:
    """Resolve an env path relative to the shard root."""
    raw = value or default
    path = Path(raw)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


@dataclass(frozen=True)
class RuntimeConfig:
    """Store the settings needed to talk to a local runtime."""

    backend: str
    host: str
    port: int
    model: str
    model_path: Path
    server_binary: Path
    cli_binary: Path
    num_predict: int
    num_ctx: int
    num_thread: int
    temperature: float
    top_p: float
    top_k: int
    min_p: float
    keep_alive: str
    require_gpu: bool
    startup_timeout: int
    chat_template: str
    chat_template_file: Path
    chat_template_kwargs: str
    reasoning_budget: int
    reasoning_format: str
    stop_tokens: tuple[str, ...]

    @property
    def base_url(self) -> str:
        """Return the local HTTP base URL."""
        return f"http://{self.host}:{self.port}"


def create_client() -> RuntimeConfig:
    """Create and return a runtime configuration object."""
    load_dotenv()

    backend = os.getenv("RUNTIME_BACKEND", "llama_cpp").strip().lower()
    host = os.getenv("LLAMA_HOST", "127.0.0.1").strip()
    port = int(os.getenv("LLAMA_PORT", "8080"))
    model = os.getenv("LLAMA_MODEL_ALIAS", os.getenv("OLLAMA_MODEL", "qwen2.5-coder-14b")).strip()
    num_predict = int(os.getenv("OLLAMA_NUM_PREDICT", "1024"))
    num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
    num_thread = int(os.getenv("OLLAMA_NUM_THREAD", "4"))
    temperature = float(os.getenv("OLLAMA_TEMPERATURE", "0.1"))
    top_p = float(os.getenv("LLAMA_TOP_P", "0.85"))
    top_k = int(os.getenv("LLAMA_TOP_K", "20"))
    min_p = float(os.getenv("LLAMA_MIN_P", "0"))
    keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "5m")
    require_gpu = os.getenv("REQUIRE_GPU", "false").lower() == "true"
    startup_timeout = int(os.getenv("LLAMA_STARTUP_TIMEOUT", "120"))
    chat_template = os.getenv("LLAMA_CHAT_TEMPLATE", "J").strip()
    chat_template_file = _resolve_path(
        os.getenv("LLAMA_CHAT_TEMPLATE_FILE", ""),
        Path("prompts") / "J-chat-template.jinja",
    )
    chat_template_kwargs = os.getenv(
        "LLAMA_CHAT_TEMPLATE_KWARGS",
        "",
    ).strip()
    reasoning_budget = int(os.getenv("LLAMA_REASONING_BUDGET", "0"))
    reasoning_format = os.getenv("LLAMA_REASONING_FORMAT", "none").strip()
    stop_tokens = tuple(
        token.strip()
        for token in os.getenv(
            "LLAMA_STOP_TOKENS",
            "<|im_end|>,<|im_start|>",
        ).split(",")
        if token.strip()
    )

    model_path = _resolve_path(
        os.getenv("LLAMA_MODEL_PATH", ""),
        Path("models") / "qwen2.5-coder-14b-instruct-q4_k_m.gguf",
    )
    server_binary = _resolve_path(
        os.getenv("LLAMA_SERVER_BINARY", ""),
        Path("model-server") / "server.exe",
    )
    cli_binary = _resolve_path(
        os.getenv("LLAMA_CLI_BINARY", ""),
        Path("model-server") / "llama.exe",
    )

    return RuntimeConfig(
        backend=backend,
        host=host,
        port=port,
        model=model,
        model_path=model_path,
        server_binary=server_binary,
        cli_binary=cli_binary,
        num_predict=num_predict,
        num_ctx=num_ctx,
        num_thread=num_thread,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        min_p=min_p,
        keep_alive=keep_alive,
        require_gpu=require_gpu,
        startup_timeout=startup_timeout,
        chat_template=chat_template,
        chat_template_file=chat_template_file,
        chat_template_kwargs=chat_template_kwargs,
        reasoning_budget=reasoning_budget,
        reasoning_format=reasoning_format,
        stop_tokens=stop_tokens,
    )
