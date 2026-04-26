"""Preflight diagnostics for deterministic startup validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
from urllib.request import Request, urlopen

import psutil

from app.client import create_client


BASE_DIR = Path(__file__).resolve().parent.parent
BUILD_INFO_PATH = BASE_DIR / "BUILD_INFO.json"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _normalize_path_for_compare(path: str) -> str:
    return path.replace("\\", "/").rstrip("/").lower()


def _paths_compatible(expected: str, actual: str) -> bool:
    if not expected or not actual:
        return True
    if expected == actual:
        return True
    # Handle cross-host comparisons (Windows absolute path vs current host path).
    expected_tail = "/".join(expected.split("/")[-2:])
    actual_tail = "/".join(actual.split("/")[-2:])
    return expected_tail == actual_tail

def _check_python_deps() -> CheckResult:
    required = ["dotenv", "psutil"]
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    if missing:
        return CheckResult("python_deps", False, f"missing={','.join(missing)}")
    return CheckResult("python_deps", True, "ok")


def _check_paths() -> list[CheckResult]:
    config = create_client()
    checks = [
        CheckResult("model_path", config.model_path.exists(), str(config.model_path)),
        CheckResult("server_binary", config.server_binary.exists(), str(config.server_binary)),
        CheckResult("chat_template_file", config.chat_template_file.exists(), str(config.chat_template_file)),
    ]
    sessions_dir = BASE_DIR / "logs" / "sessions"
    runtime_dir = BASE_DIR / "logs" / "runtime"
    for target in [sessions_dir, runtime_dir]:
        target.mkdir(parents=True, exist_ok=True)
        writable = os.access(target, os.W_OK)
        checks.append(CheckResult(f"writable:{target.name}", writable, str(target)))
    return checks


def _check_resources() -> list[CheckResult]:
    disk = shutil.disk_usage(BASE_DIR)
    ram = psutil.virtual_memory()
    free_gb = round(disk.free / (1024**3), 2)
    ram_gb = round(ram.available / (1024**3), 2)
    return [
        CheckResult("disk_free", free_gb >= 1.0, f"free_gb={free_gb}"),
        CheckResult("ram_available", ram_gb >= 2.0, f"available_gb={ram_gb}"),
    ]


def _check_server_health() -> CheckResult:
    config = create_client()
    if config.backend != "llama_cpp":
        return CheckResult("server_health", True, "skipped_non_llama_cpp")
    try:
        request = Request(f"{config.base_url}/v1/models", method="GET")
        with urlopen(request, timeout=2):
            return CheckResult("server_health", True, "reachable")
    except Exception as error:
        return CheckResult("server_health", False, f"unreachable={error}")


def _check_repo_location_hint() -> CheckResult:
    expected_root = os.getenv("SHARD_EXPECTED_ROOT", "E:\\dev shard")
    current = str(BASE_DIR)
    expected = _normalize_path_for_compare(expected_root)
    current_norm = _normalize_path_for_compare(current)
    if platform.system() != "Windows":
        return CheckResult(
            "repo_location",
            True,
            f"non_windows_host current={current} expected_hint={expected_root}",
        )
    in_expected = current_norm.startswith(expected)
    return CheckResult("repo_location", in_expected, f"current={current} expected_hint={expected_root}")


def _check_build_info_alignment() -> CheckResult:
    if not BUILD_INFO_PATH.exists():
        return CheckResult("build_info_alignment", True, "missing_build_info_skipped")

    config = create_client()
    try:
        payload = json.loads(BUILD_INFO_PATH.read_text(encoding="utf-8"))
    except Exception as error:
        return CheckResult("build_info_alignment", False, f"invalid_build_info={error}")

    runtime = payload.get("default_runtime") or {}
    expected_server = _normalize_path_for_compare(str(runtime.get("server_binary", "")))
    expected_model = _normalize_path_for_compare(str(runtime.get("model_path", "")))

    actual_server = _normalize_path_for_compare(str(config.server_binary))
    actual_model = _normalize_path_for_compare(str(config.model_path))

    aligned = True
    reasons: list[str] = []
    if expected_server and not _paths_compatible(expected_server, actual_server):
        aligned = False
        reasons.append(f"server_mismatch build={runtime.get('server_binary')} runtime={config.server_binary}")
    if expected_model and not _paths_compatible(expected_model, actual_model):
        aligned = False
        reasons.append(f"model_mismatch build={runtime.get('model_path')} runtime={config.model_path}")

    if aligned:
        return CheckResult("build_info_alignment", True, "runtime_matches_build_info")
    return CheckResult("build_info_alignment", False, " | ".join(reasons))


def run_doctor() -> int:
    """Run preflight checks and print JSON + human summary."""
    checks = [
        _check_python_deps(),
        *_check_paths(),
        *_check_resources(),
        _check_server_health(),
        _check_repo_location_hint(),
        _check_build_info_alignment(),
    ]
    payload = {
        "ok": all(item.ok for item in checks),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cwd": str(Path.cwd()),
            "repo_root": str(BASE_DIR),
        },
        "checks": [asdict(item) for item in checks],
    }
    print(json.dumps(payload, indent=2))
    print("\n--- Doctor Summary ---")
    for item in checks:
        icon = "PASS" if item.ok else "FAIL"
        print(f"[{icon}] {item.name}: {item.detail}")
    return 0 if payload["ok"] else 1
