# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Security gap remediation — BRIDGE layer.

Reads audit findings from the SCAN layer and generates actionable output.

Subcommands:
  report            — Generate a markdown remediation report from last audit.
  script            — Generate a fix script (.bat/.sh) from last audit findings.
  rescan            — Run a fresh full audit and compare against previous findings.

Usage:  python bridge.py <subcommand>
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
AUDIT_PATH = BASE_DIR / "logs" / "last_audit.json"
REPORT_DIR = BASE_DIR / "logs" / "reports"


def _load_findings() -> list[dict]:
    if not AUDIT_PATH.exists():
        print("[BRIDGE ERROR] No audit data. Run: run_scan full")
        return []
    try:
        return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[BRIDGE ERROR] Cannot read audit data: {e}")
        return []


def cmd_report() -> None:
    findings = _load_findings()
    if not findings:
        return

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"remediation_{ts}.md"

    # Group by risk
    by_risk: dict[str, list[dict]] = {}
    for f in findings:
        r = f.get("risk", "UNKNOWN")
        by_risk.setdefault(r, []).append(f)

    lines = [
        "# Security Remediation Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total findings: {len(findings)}",
        "",
        "## Summary",
        "",
        "| Risk | Count |",
        "|------|-------|",
    ]
    for risk in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
        count = len(by_risk.get(risk, []))
        if count:
            lines.append(f"| {risk} | {count} |")
    lines.append("")

    # Detail by risk level
    for risk in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
        group = by_risk.get(risk, [])
        if not group:
            continue
        lines.append(f"## {risk} ({len(group)})")
        lines.append("")
        for i, f in enumerate(group, 1):
            ftype = f.get("type", "unknown")
            detail = f.get("detail", "No detail")
            fix = f.get("fix", "")

            lines.append(f"### {i}. [{ftype}] {detail}")
            lines.append("")

            # Type-specific details
            if ftype == "open_port":
                lines.append(f"- **Port:** {f.get('port', '?')}")
                lines.append(f"- **Service:** {f.get('service', '?')}")
                lines.append(f"- **Target:** {f.get('target', '?')}")
                if not fix:
                    fix = f"netsh advfirewall firewall add rule name=\"Block port {f.get('port', '?')}\" dir=in action=block protocol=TCP localport={f.get('port', '?')}"
            elif ftype == "exposed_cred":
                lines.append(f"- **Credential type:** {f.get('cred_type', '?')}")
                lines.append(f"- **File:** `{f.get('file', '?')}` line {f.get('line', '?')}")
                lines.append(f"- **Preview:** `{f.get('preview', '?')}`")
                if not fix:
                    fix = f"1. Rotate the exposed credential immediately\\n2. Remove from {f.get('file', 'the file')}\\n3. Use environment variables or a vault"
            elif ftype in ("firewall", "uac", "defender", "rdp", "updates"):
                pass  # fix already populated from scan
            elif ftype == "open_share":
                if not fix:
                    share_name = detail.split(":")[-1].strip().split()[0] if ":" in detail else "SHARE"
                    fix = f"net share {share_name} /delete"
            elif ftype == "risky_service":
                pass  # fix already populated
            elif ftype == "weak_permission":
                pass  # fix already populated
            elif ftype == "arp_spoof":
                if not fix:
                    fix = "Investigate network for ARP spoofing. Consider static ARP entries for critical hosts."

            if fix:
                lines.append(f"- **Fix:**")
                lines.append(f"  ```")
                lines.append(f"  {fix}")
                lines.append(f"  ```")
            lines.append("")

    # Write report
    content = "\n".join(lines)
    with open(str(report_path), "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[BRIDGE] Remediation report: {report_path}")
    print(f"  {len(findings)} findings documented with fix instructions.")
    print(f"\n{content[:500]}")
    if len(content) > 500:
        print(f"  ... ({len(content)} chars total, see full report)")


def cmd_script() -> None:
    findings = _load_findings()
    if not findings:
        return

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    is_windows = os.name == "nt"
    ext = ".bat" if is_windows else ".sh"
    script_path = REPORT_DIR / f"fix_{ts}{ext}"

    lines = []
    if is_windows:
        lines.append("@echo off")
        lines.append(f"REM Security fix script — generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"REM {len(findings)} finding(s) to remediate")
        lines.append("REM REVIEW EACH FIX BEFORE RUNNING")
        lines.append("")
        lines.append('echo [SECURITY FIX] Starting remediation...')
        lines.append("")
    else:
        lines.append("#!/bin/bash")
        lines.append(f"# Security fix script — generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"# {len(findings)} finding(s) to remediate")
        lines.append("# REVIEW EACH FIX BEFORE RUNNING")
        lines.append("")
        lines.append('echo "[SECURITY FIX] Starting remediation..."')
        lines.append("")

    fix_count = 0
    for f in findings:
        fix = f.get("fix", "")
        if not fix:
            continue
        ftype = f.get("type", "unknown")
        risk = f.get("risk", "?")
        detail = f.get("detail", "")

        if is_windows:
            lines.append(f"REM [{risk}] {ftype}: {detail}")
            lines.append(f"echo Fixing: {ftype} ({risk})")
            lines.append(fix)
            lines.append("")
        else:
            lines.append(f"# [{risk}] {ftype}: {detail}")
            lines.append(f'echo "Fixing: {ftype} ({risk})"')
            lines.append(fix)
            lines.append("")
        fix_count += 1

    if is_windows:
        lines.append(f'echo [DONE] {fix_count} fix(es) applied. Re-run audit to verify.')
        lines.append("pause")
    else:
        lines.append(f'echo "[DONE] {fix_count} fix(es) applied. Re-run audit to verify."')

    content = "\n".join(lines)
    with open(str(script_path), "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[BRIDGE] Fix script: {script_path}")
    print(f"  {fix_count} fixable issue(s) scripted.")
    print(f"\n  !! REVIEW THE SCRIPT BEFORE RUNNING !!")


def cmd_rescan() -> None:
    # Load previous findings
    old = _load_findings()
    old_types = {(f.get("type", ""), f.get("detail", "")) for f in old}

    print("[BRIDGE] Running fresh audit for comparison...\n")

    # Import and run the scan module
    scan_module = BASE_DIR / "tools" / "run" / "scan.py"
    import importlib.util
    spec = importlib.util.spec_from_file_location("scan", str(scan_module))
    scan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scan)
    scan.cmd_full(".")

    # Load new findings
    new = _load_findings()
    new_types = {(f.get("type", ""), f.get("detail", "")) for f in new}

    fixed = old_types - new_types
    new_issues = new_types - old_types
    remaining = old_types & new_types

    print("\n" + "=" * 60)
    print("        REMEDIATION PROGRESS")
    print("=" * 60)
    print(f"\n  Previous: {len(old)} finding(s)")
    print(f"  Current:  {len(new)} finding(s)")
    print(f"  Fixed:    {len(fixed)}")
    print(f"  New:      {len(new_issues)}")
    print(f"  Remaining: {len(remaining)}")

    if fixed:
        print("\n  Resolved:")
        for t, d in sorted(fixed):
            print(f"    ✓ [{t}] {d}")
    if new_issues:
        print("\n  New issues:")
        for t, d in sorted(new_issues):
            print(f"    ✗ [{t}] {d}")


def main() -> None:
    if len(sys.argv) < 2:
        print("[BRIDGE] Subcommands: report, script, rescan")
        return

    sub = sys.argv[1].lower()
    if sub == "report":
        cmd_report()
    elif sub == "script":
        cmd_script()
    elif sub == "rescan":
        cmd_rescan()
    else:
        print(f"[BRIDGE ERROR] Unknown subcommand: {sub}")


if __name__ == "__main__":
    main()
