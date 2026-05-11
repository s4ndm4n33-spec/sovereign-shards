"""Host security auditor — SCAN layer.

Subcommands:
  ports [target]     — Scan common ports on localhost or target IP.
  creds [path]       — Scan for exposed credentials/secrets in files.
  security           — Audit Windows security settings (firewall, UAC, Defender).
  network            — Audit network configuration (interfaces, listeners, shares).
  services           — Enumerate running services, flag risky ones.
  permissions [path] — Check file permissions for security issues.
  full [path]        — Run ALL audits. Comprehensive report.

Usage:  python scan.py <subcommand> [args...]
"""

import os
import re
import socket
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Port Scanner ────────────────────────────────────────────────────

# Common ports: service name, port, risk level
COMMON_PORTS = [
    ("FTP", 21, "HIGH"), ("SSH", 22, "INFO"), ("Telnet", 23, "CRITICAL"),
    ("SMTP", 25, "MEDIUM"), ("DNS", 53, "INFO"), ("HTTP", 80, "LOW"),
    ("POP3", 110, "MEDIUM"), ("NetBIOS", 139, "HIGH"), ("IMAP", 143, "MEDIUM"),
    ("HTTPS", 443, "LOW"), ("SMB", 445, "HIGH"), ("MSSQL", 1433, "HIGH"),
    ("MySQL", 3306, "HIGH"), ("RDP", 3389, "HIGH"), ("PostgreSQL", 5432, "HIGH"),
    ("VNC", 5900, "HIGH"), ("WinRM", 5985, "HIGH"), ("Redis", 6379, "CRITICAL"),
    ("HTTP-Alt", 8080, "MEDIUM"), ("MongoDB", 27017, "CRITICAL"),
]


def cmd_ports(target: str = "127.0.0.1") -> list[dict]:
    findings = []
    print(f"[SCAN] Port scan: {target}")
    print(f"{'PORT':<8} {'SERVICE':<12} {'STATUS':<8} {'RISK'}")
    print("-" * 40)

    for service, port, risk in COMMON_PORTS:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((target, port))
            sock.close()
            if result == 0:
                print(f"{port:<8} {service:<12} {'OPEN':<8} {risk}")
                findings.append({
                    "type": "open_port", "port": port, "service": service,
                    "risk": risk, "target": target
                })
        except (socket.error, OSError):
            pass

    if not findings:
        print("No open ports found.")
    else:
        print(f"\n[SCAN] {len(findings)} open port(s) found.")
    return findings


# ── Credential Scanner ──────────────────────────────────────────────

# Patterns that indicate exposed secrets
_CRED_PATTERNS = [
    (r"(?i)(password|passwd|pwd)\s*[=:]\s*\S+", "PASSWORD", "HIGH"),
    (r"(?i)(api[_-]?key|apikey)\s*[=:]\s*\S+", "API_KEY", "HIGH"),
    (r"(?i)(secret|token)\s*[=:]\s*\S+", "SECRET/TOKEN", "HIGH"),
    (r"(?i)(aws_access_key_id)\s*[=:]\s*\S+", "AWS_KEY", "CRITICAL"),
    (r"(?i)(aws_secret_access_key)\s*[=:]\s*\S+", "AWS_SECRET", "CRITICAL"),
    (r"ghp_[a-zA-Z0-9]{36}", "GITHUB_TOKEN", "CRITICAL"),
    (r"sk-[a-zA-Z0-9]{32,}", "OPENAI_KEY", "CRITICAL"),
    (r"xox[bprs]-[a-zA-Z0-9\-]+", "SLACK_TOKEN", "CRITICAL"),
    (r"(?i)(private[_-]?key|PRIVATE KEY)", "PRIVATE_KEY", "CRITICAL"),
    (r"(?i)(connection[_-]?string)\s*[=:]\s*\S+", "CONN_STRING", "HIGH"),
]

SCAN_EXTENSIONS = {".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml",
                   ".cfg", ".ini", ".conf", ".env", ".txt", ".xml", ".properties",
                   ".sh", ".bat", ".ps1", ".md"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
             "models", "model-server", "Lib", "Scripts", "site-packages"}
MAX_FILE_SIZE = 512 * 1024  # 512 KB


def cmd_creds(scan_path: str = ".") -> list[dict]:
    findings = []
    scan_root = os.path.abspath(scan_path)
    print(f"[SCAN] Credential scan: {scan_root}")

    file_count = 0
    for dirpath, dirnames, filenames in os.walk(scan_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            # Always scan dotfiles (.env, .gitconfig, etc.)
            if ext not in SCAN_EXTENSIONS and not fname.startswith("."):
                continue
            full = os.path.join(dirpath, fname)
            try:
                if os.path.getsize(full) > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue

            file_count += 1
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        for pattern, cred_type, risk in _CRED_PATTERNS:
                            if re.search(pattern, line):
                                rel = os.path.relpath(full, scan_root).replace("\\", "/")
                                # Redact the actual value
                                clean = line.strip()[:80]
                                findings.append({
                                    "type": "exposed_cred", "cred_type": cred_type,
                                    "risk": risk, "file": rel, "line": line_num,
                                    "preview": clean
                                })
                                break  # One finding per line max
            except OSError:
                continue

    if not findings:
        print(f"[SCAN] Scanned {file_count} files. No exposed credentials found.")
    else:
        print(f"[SCAN] Scanned {file_count} files. {len(findings)} credential exposure(s):\n")
        for f in findings:
            print(f"  [{f['risk']}] {f['cred_type']} in {f['file']}:{f['line']}")
            print(f"         {f['preview']}")
    return findings


# ── Windows Security Audit ──────────────────────────────────────────

def _run_cmd(cmd: str) -> str:
    """Run a shell command, return stdout or error string."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, timeout=10,
                           encoding="utf-8", errors="replace")
        return (r.stdout or "").strip()
    except Exception as e:
        return f"[ERROR] {e}"


def cmd_security() -> list[dict]:
    findings = []
    print("[SCAN] Windows security audit\n")

    # Firewall status
    fw = _run_cmd("netsh advfirewall show allprofiles state")
    if "ON" in fw.upper():
        print("  [OK] Firewall is ON")
    else:
        print("  [CRITICAL] Firewall may be OFF")
        findings.append({"type": "firewall", "risk": "CRITICAL",
                         "detail": "Windows Firewall is not fully enabled",
                         "fix": "netsh advfirewall set allprofiles state on"})

    # UAC status
    uac = _run_cmd('reg query "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" /v EnableLUA')
    if "0x1" in uac:
        print("  [OK] UAC is enabled")
    else:
        print("  [HIGH] UAC may be disabled")
        findings.append({"type": "uac", "risk": "HIGH",
                         "detail": "User Account Control is disabled",
                         "fix": 'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" /v EnableLUA /t REG_DWORD /d 1 /f'})

    # Windows Defender
    defender = _run_cmd('reg query "HKLM\\SOFTWARE\\Microsoft\\Windows Defender" /v DisableAntiSpyware')
    if "0x1" in defender:
        print("  [CRITICAL] Windows Defender is DISABLED")
        findings.append({"type": "defender", "risk": "CRITICAL",
                         "detail": "Windows Defender is disabled",
                         "fix": 'reg delete "HKLM\\SOFTWARE\\Microsoft\\Windows Defender" /v DisableAntiSpyware /f'})
    else:
        print("  [OK] Windows Defender appears active")

    # RDP status
    rdp = _run_cmd('reg query "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server" /v fDenyTSConnections')
    if "0x0" in rdp:
        print("  [HIGH] RDP is ENABLED (remote access open)")
        findings.append({"type": "rdp", "risk": "HIGH",
                         "detail": "Remote Desktop is enabled",
                         "fix": 'reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 1 /f'})
    else:
        print("  [OK] RDP is disabled")

    # Password policy
    pw = _run_cmd("net accounts")
    print(f"\n  Password policy:\n    {pw[:300]}")

    # Automatic updates
    wu = _run_cmd('reg query "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU" /v NoAutoUpdate')
    if "0x1" in wu:
        print("  [MEDIUM] Automatic updates are DISABLED")
        findings.append({"type": "updates", "risk": "MEDIUM",
                         "detail": "Windows automatic updates are disabled",
                         "fix": 'reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU" /v NoAutoUpdate /t REG_DWORD /d 0 /f'})
    else:
        print("  [OK] Automatic updates appear enabled")

    if not findings:
        print("\n[SCAN] Security audit clean. No issues found.")
    else:
        print(f"\n[SCAN] {len(findings)} security issue(s) found.")
    return findings


# ── Network Audit ───────────────────────────────────────────────────

def cmd_network() -> list[dict]:
    findings = []
    print("[SCAN] Network audit\n")

    # Network interfaces
    ifaces = _run_cmd("ipconfig /all") if os.name == "nt" else _run_cmd("ip addr")
    print("  Interfaces (summary):")
    for line in ifaces.split("\n")[:20]:
        stripped = line.strip()
        if stripped:
            print(f"    {stripped}")

    # Listening ports
    if os.name == "nt":
        netstat = _run_cmd("netstat -an | findstr LISTENING")
    else:
        netstat = _run_cmd("netstat -tlnp 2>/dev/null || ss -tlnp")
    listeners = [l.strip() for l in netstat.split("\n") if l.strip()]
    print(f"\n  Listening ports: {len(listeners)}")
    for l in listeners[:15]:
        print(f"    {l}")
    if len(listeners) > 15:
        print(f"    ... and {len(listeners) - 15} more")

    # Open shares (Windows)
    if os.name == "nt":
        shares = _run_cmd("net share")
        if shares and "ERROR" not in shares:
            non_default = [l for l in shares.split("\n")
                           if l.strip() and not l.startswith("-")
                           and "The command" not in l
                           and "Share name" not in l]
            open_shares = [s for s in non_default if "$" not in s.split()[0] if s.split()]
            if open_shares:
                print(f"\n  [HIGH] {len(open_shares)} non-default share(s):")
                for s in open_shares:
                    print(f"    {s.strip()}")
                    findings.append({"type": "open_share", "risk": "HIGH",
                                     "detail": f"Open share: {s.strip()[:60]}"})
            else:
                print("\n  [OK] No non-default shares")

    # ARP table (potential spoofing check)
    arp = _run_cmd("arp -a")
    arp_lines = [l for l in arp.split("\n") if l.strip() and "Interface" not in l and "Internet" not in l]
    print(f"\n  ARP entries: {len(arp_lines)}")
    # Check for duplicate MACs (ARP spoofing indicator)
    macs = {}
    for line in arp_lines:
        parts = line.split()
        if len(parts) >= 2:
            mac = parts[1] if os.name == "nt" else (parts[2] if len(parts) > 2 else "")
            if mac and mac != "ff-ff-ff-ff-ff-ff" and mac != "<incomplete>":
                macs.setdefault(mac, []).append(parts[0])
    dupes = {m: ips for m, ips in macs.items() if len(ips) > 1}
    if dupes:
        print(f"\n  [CRITICAL] Possible ARP spoofing — duplicate MACs:")
        for mac, ips in dupes.items():
            print(f"    {mac} → {', '.join(ips)}")
            findings.append({"type": "arp_spoof", "risk": "CRITICAL",
                             "detail": f"Duplicate MAC {mac}: {', '.join(ips)}"})

    if not findings:
        print("\n[SCAN] Network audit clean.")
    else:
        print(f"\n[SCAN] {len(findings)} network issue(s) found.")
    return findings


# ── Service Enumeration ─────────────────────────────────────────────

# Known risky services
_RISKY_SERVICES = {
    "telnet": "CRITICAL", "ftp": "HIGH", "remoteregistry": "HIGH",
    "sshd": "INFO", "w3svc": "MEDIUM", "snmp": "HIGH",
    "msftpsvc": "HIGH", "iisadmin": "MEDIUM",
}


def cmd_services() -> list[dict]:
    findings = []
    print("[SCAN] Service enumeration\n")

    if os.name == "nt":
        svc = _run_cmd('sc query type= service state= all | findstr "SERVICE_NAME DISPLAY_NAME STATE"')
    else:
        svc = _run_cmd("systemctl list-units --type=service --state=running --no-pager 2>/dev/null || service --status-all 2>/dev/null")

    running = []
    lines = svc.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "SERVICE_NAME:" in line:
            name = line.split("SERVICE_NAME:")[-1].strip().lower()
            # Look ahead for state
            state_line = ""
            for j in range(i+1, min(i+4, len(lines))):
                if "RUNNING" in lines[j]:
                    state_line = "RUNNING"
                    break
            if state_line == "RUNNING":
                running.append(name)
                if name in _RISKY_SERVICES:
                    risk = _RISKY_SERVICES[name]
                    print(f"  [{risk}] {name} is RUNNING")
                    findings.append({"type": "risky_service", "risk": risk,
                                     "detail": f"Service '{name}' is running",
                                     "fix": f"sc stop {name} && sc config {name} start= disabled"})
        i += 1

    print(f"\n  {len(running)} running service(s)")
    if not findings:
        print("[SCAN] No risky services detected.")
    else:
        print(f"[SCAN] {len(findings)} risky service(s) found.")
    return findings


# ── File Permission Audit ───────────────────────────────────────────

_SENSITIVE_PATTERNS = [".env", ".ssh", ".gnupg", "id_rsa", "id_ed25519",
                       ".gitconfig", "credentials", "wallet.dat",
                       "shadow", "passwd", "htpasswd"]


def cmd_permissions(scan_path: str = ".") -> list[dict]:
    findings = []
    scan_root = os.path.abspath(scan_path)
    print(f"[SCAN] File permission audit: {scan_root}\n")

    for dirpath, dirnames, filenames in os.walk(scan_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, scan_root).replace("\\", "/")

            # Check if this is a sensitive file
            is_sensitive = any(pat in fname.lower() for pat in _SENSITIVE_PATTERNS)
            if not is_sensitive:
                continue

            try:
                stat = os.stat(full)
            except OSError:
                continue

            # On Windows, check if file is accessible by everyone
            if os.name == "nt":
                try:
                    # If we can read it without elevation, flag it
                    with open(full, "r", encoding="utf-8", errors="ignore") as f:
                        f.read(1)
                    findings.append({
                        "type": "weak_permission", "risk": "HIGH",
                        "detail": f"Sensitive file readable: {rel}",
                        "fix": f'icacls "{full}" /inheritance:r /grant:r "%USERNAME%":F'
                    })
                    print(f"  [HIGH] Readable sensitive file: {rel}")
                except OSError:
                    pass
            else:
                # Unix: check for world-readable
                mode = stat.st_mode
                if mode & 0o004:  # world-readable
                    findings.append({
                        "type": "weak_permission", "risk": "HIGH",
                        "detail": f"World-readable sensitive file: {rel}",
                        "fix": f"chmod 600 {full}"
                    })
                    print(f"  [HIGH] World-readable: {rel}")

    if not findings:
        print("[SCAN] No permission issues found.")
    else:
        print(f"\n[SCAN] {len(findings)} permission issue(s) found.")
    return findings


# ── Full Audit ──────────────────────────────────────────────────────

def cmd_full(scan_path: str = ".") -> None:
    all_findings: list[dict] = []

    print("=" * 60)
    print("        SOVEREIGN SHARDS — FULL SECURITY AUDIT")
    print("=" * 60)
    print()

    all_findings.extend(cmd_ports())
    print()
    all_findings.extend(cmd_creds(scan_path))
    print()
    all_findings.extend(cmd_security())
    print()
    all_findings.extend(cmd_network())
    print()
    all_findings.extend(cmd_services())
    print()
    all_findings.extend(cmd_permissions(scan_path))

    # Summary
    print()
    print("=" * 60)
    print("        AUDIT SUMMARY")
    print("=" * 60)

    by_risk: dict[str, int] = {}
    for f in all_findings:
        r = f.get("risk", "UNKNOWN")
        by_risk[r] = by_risk.get(r, 0) + 1

    total = len(all_findings)
    if total == 0:
        print("\n  [ALL CLEAR] No security issues detected.")
    else:
        print(f"\n  Total findings: {total}")
        for risk in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            count = by_risk.get(risk, 0)
            if count:
                print(f"    {risk:<10} {count}")
        print()

    # Save findings to JSON for bridge layer
    out_path = BASE_DIR / "logs" / "last_audit.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(out_path), "w", encoding="utf-8") as f:
        json.dump(all_findings, f, indent=2, ensure_ascii=True)
    print(f"  Findings saved: {out_path}")


def main() -> None:
    if len(sys.argv) < 2:
        print("[SCAN] Subcommands: ports, creds, security, network, services, permissions, full")
        return

    sub = sys.argv[1].lower()
    arg = sys.argv[2] if len(sys.argv) > 2 else None

    if sub == "ports":
        cmd_ports(arg or "127.0.0.1")
    elif sub == "creds":
        cmd_creds(arg or ".")
    elif sub == "security":
        cmd_security()
    elif sub == "network":
        cmd_network()
    elif sub == "services":
        cmd_services()
    elif sub == "permissions":
        cmd_permissions(arg or ".")
    elif sub == "full":
        cmd_full(arg or ".")
    else:
        print(f"[SCAN ERROR] Unknown subcommand: {sub}")


if __name__ == "__main__":
    main()
