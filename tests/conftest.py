"""Test configuration: mock unavailable optional deps before any app imports.

On the target USB hardware psutil is installed. In CI or clean environments
where it may be absent, we mock it here so tests can still validate all
the pure-Python agent logic.
"""

import sys
import types

# Mock psutil if not installed (it's only used by system_tools.py)
if "psutil" not in sys.modules:
    try:
        import psutil  # noqa: F401
    except ImportError:
        _mock = types.ModuleType("psutil")

        _mock.cpu_percent = lambda: 50.0
        _mock.cpu_count = lambda logical=True: 4

        _MemInfo = type("MemInfo", (), {
            "percent": 60.0, "total": 16 * 1024**3, "available": 8 * 1024**3,
        })
        _mock.virtual_memory = lambda: _MemInfo()

        _DiskInfo = type("DiskInfo", (), {
            "percent": 40.0, "total": 16 * 1024**3, "free": 8 * 1024**3,
        })
        _mock.disk_usage = lambda path="/": _DiskInfo()

        _mock.Process = type("Process", (), {
            "__init__": lambda self, pid=None: None,
            "memory_info": lambda self: type("", (), {"rss": 100 * 1024**2})(),
        })

        sys.modules["psutil"] = _mock
