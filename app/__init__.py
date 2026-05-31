# Copyright (c) 2026 Mike McCollum
#
# Licensed under the Sovereign Shards License.
# See LICENSE.md for details.

"""Application package for the Sovereign Shard."""

from .file_tools import read_file, write_file, list_dir
from .system_tools import get_system_snapshot

TOOLS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
    "system_snapshot": get_system_snapshot,
}
