# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Hardware and OS snapshot helpers."""

from __future__ import annotations

import os
import platform
import socket
from pathlib import Path

import psutil


def _disk_root() -> str:
    """Return the current drive root for disk inspection."""
    return Path.cwd().anchor or os.getenv("SystemDrive", "C:\\")


def get_system_snapshot() -> dict:
    """Return current hardware and OS vitals."""
    try:
        cpu_usage = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage(_disk_root())
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)

        return {
            "status": "ONLINE",
            "host_machine": {
                "os": f"{platform.system()} {platform.release()}",
                "cpu": platform.processor() or "Unknown CPU",
                "cores_logical": psutil.cpu_count(logical=True),
                "ram_total_gb": round(ram.total / (1024 ** 3), 2),
                "ram_available_gb": round(ram.available / (1024 ** 3), 2),
            },
            "live_metrics": {
                "cpu_utilization": f"{cpu_usage}%",
                "ram_usage_percent": f"{ram.percent}%",
                "disk_free_gb": round(disk.free / (1024 ** 3), 2),
            },
            "network": {
                "local_ip": local_ip,
                "node_name": hostname,
            },
        }
    except Exception as error:
        return {"status": "ERROR", "message": str(error)}
