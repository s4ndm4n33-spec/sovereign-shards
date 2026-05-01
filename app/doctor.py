"""Doctor: Startup Diagnostics & System Check

Runs preflight checks before launching the agent.
Validates config, tools, LLM connectivity, and disk space.
"""
from __future__ import annotations

import sys
from pathlib import Path

from app.client import create_client, RuntimeConfig
from app.local_server import LocalLlamaServer
from app.system_tools import get_system_snapshot
from app.agent.scaffold import build_default_registry


def check_config() -> tuple[bool, str]:
    """Validate runtime configuration."""
    try:
        config = create_client()
        issues = []

        # Check paths
        if not config.model_path.exists():
            issues.append(f"Model not found: {config.model_path}")
        if not config.server_binary.exists():
            issues.append(f"Server binary not found: {config.server_binary}")
        if not config.chat_template_file.exists():
            issues.append(f"Chat template not found: {config.chat_template_file}")

        if issues:
            return False, "\n".join(f"  ✗ {issue}" for issue in issues)
        return True, "  ✓ Config valid"
    except Exception as e:
        return False, f"  ✗ Config error: {e}"


def check_llm_server(config: RuntimeConfig) -> tuple[bool, str]:
    """Check if LLM server is ready or can be started."""
    try:
        server = LocalLlamaServer(config)
        if server._is_ready():
            return True, f"  ✓ LLM server online at {config.base_url}"

        # Try to start
        print("  → Starting LLM server...")
        server.ensure_started()
        return True, f"  ✓ LLM server started at {config.base_url}"
    except Exception as e:
        return False, f"  ✗ LLM error: {e}"


def check_tools() -> tuple[bool, str]:
    """Validate tool registry."""
    try:
        registry = build_default_registry()
        tools = registry.tools
        if not tools:
            return False, "  ✗ No tools found"
        return True, f"  ✓ {len(tools)} tools registered"
    except Exception as e:
        return False, f"  ✗ Tool registry error: {e}"


def check_disk() -> tuple[bool, str]:
    """Check disk space."""
    try:
        snapshot = get_system_snapshot()
        if snapshot["status"] != "ONLINE":
            return False, "  ✗ System offline"

        free_gb = snapshot["live_metrics"]["disk_free_gb"]
        if free_gb < 0.1:
            return False, f"  ✗ Disk full ({free_gb} GB free)"
        elif free_gb < 1:
            return False, f"  ⚠ Low disk space ({free_gb} GB free)"
        return True, f"  ✓ {free_gb} GB free"
    except Exception as e:
        return False, f"  ✗ Disk check failed: {e}"


def run_doctor() -> int:
    """Run full diagnostic suite."""
    print("\n" + "="*60)
    print("B.L.U.E.-J. DIAGNOSTIC SUITE")
    print("="*60)

    checks = [
        ("Configuration", check_config),
        ("Tool Registry", check_tools),
        ("Disk Space", check_disk),
    ]

    results = []
    for name, check_fn in checks:
        print(f"\n[{name}]")
        success, message = check_fn()
        print(message)
        results.append(success)

    # LLM check (separate, optional)
    print(f"\n[LLM Server]")
    try:
        config = create_client()
        success, message = check_llm_server(config)
        print(message)
        results.append(success)
    except Exception as e:
        print(f"  ⚠ LLM check skipped: {e}")
        # Don't fail if LLM is not available

    print("\n" + "="*60)
    if all(results[:3]):  # Core checks (config, tools, disk)
        print("✓ SYSTEM READY FOR LAUNCH")
        return 0
    else:
        print("✗ STARTUP CHECKS FAILED")
        return 1
