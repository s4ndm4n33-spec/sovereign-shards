"""Local file tools with chunking and storage-safe size limits."""

from __future__ import annotations

from pathlib import Path

BASE = Path.cwd()
MAX_FILE_BYTES = 4 * 1024 * 1024 * 1024  # 4GB cap (FAT32-safe)
DEFAULT_CHUNK_BYTES = 1024 * 1024  # 1MB


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else BASE / p


def read_file(path: str, offset: int = 0, chunk_bytes: int = DEFAULT_CHUNK_BYTES) -> str:
    """Read a file chunk for large-file safe processing."""
    p = _resolve(path)
    if not p.exists():
        return f"[ERROR] File not found: {path}"
    if p.is_dir():
        return f"[ERROR] Path is a directory: {path}"

    size = p.stat().st_size
    if size > MAX_FILE_BYTES:
        return f"[ERROR] File exceeds 4GB limit: {path} ({size} bytes)"

    if offset < 0:
        return "[ERROR] offset must be >= 0"
    if chunk_bytes <= 0:
        return "[ERROR] chunk_bytes must be > 0"

    with p.open("rb") as handle:
        handle.seek(offset)
        data = handle.read(chunk_bytes)

    text = data.decode("utf-8", errors="ignore")
    next_offset = offset + len(data)
    eof = next_offset >= size
    header = (
        f"[CHUNK] path={path} offset={offset} bytes={len(data)} "
        f"next_offset={next_offset} eof={str(eof).lower()} total={size}\n"
    )
    return header + text


def write_file(path: str, content: str, append: bool = False) -> str:
    """Write or append content while enforcing FAT32-safe max file size."""
    p = _resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    existing_size = p.stat().st_size if p.exists() else 0
    content_bytes = content.encode("utf-8")
    projected = (existing_size + len(content_bytes)) if append else len(content_bytes)
    if projected > MAX_FILE_BYTES:
        return f"[ERROR] Write would exceed 4GB limit: {path} ({projected} bytes)"

    mode = "ab" if append else "wb"
    with p.open(mode) as handle:
        handle.write(content_bytes)

    action = "Appended" if append else "Wrote"
    return f"[OK] {action} {len(content_bytes)} bytes to {path}"


def list_dir(path: str) -> str:
    p = _resolve(path)
    if not p.exists():
        return f"[ERROR] Directory not found: {path}"
    if not p.is_dir():
        return f"[ERROR] Not a directory: {path}"
    return "\n".join(str(x.name) for x in p.iterdir())
