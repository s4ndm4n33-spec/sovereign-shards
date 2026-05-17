# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""Application package for the Sovereign Shard."""

from .file_tools import read_file, write_file, list_dir
from .system_tools import get_system_snapshot

TOOLS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
    "system_snapshot": get_system_snapshot,
}
