"""
Filesystem helpers shared across the application.
All paths are explicit — no hidden CWD assumptions.
"""

from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    """Create directory (and parents) if it does not exist. Return Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_filename(name: str, max_length: int = 200) -> str:
    """
    Replace unsafe characters and truncate filename.
    Preserves the file extension.
    """
    p = Path(name)
    stem = p.stem.replace(" ", "_")
    suffix = p.suffix.lower()

    # Remove characters that are not alphanumeric, dash, underscore, or dot
    stem = "".join(c for c in stem if c.isalnum() or c in "-_.")
    stem = stem or "file"

    if len(stem) + len(suffix) > max_length:
        stem = stem[: max_length - len(suffix)]

    return stem + suffix


def unique_filename(original: str) -> str:
    """Prefix a UUID4 to avoid name collisions."""
    safe = safe_filename(original)
    return f"{uuid.uuid4().hex[:8]}_{safe}"


def file_sha256(path: str | Path, chunk_size: int = 65536) -> str:
    """Return hex SHA-256 of a file without loading it all into memory."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def file_size_mb(path: str | Path) -> float:
    return round(Path(path).stat().st_size / (1024 * 1024), 2)


def delete_file(path: str | Path, missing_ok: bool = True) -> bool:
    """Delete a file. Returns True if deleted."""
    p = Path(path)
    if not p.exists():
        return False
    p.unlink(missing_ok=missing_ok)
    return True


def delete_directory(path: str | Path) -> bool:
    """Recursively delete a directory. Returns True if deleted."""
    p = Path(path)
    if not p.exists():
        return False
    shutil.rmtree(p)
    return True


def list_files_by_extension(
    directory: str | Path,
    extension: str,
    recursive: bool = False,
) -> list[Path]:
    """Return all files with `extension` in `directory`."""
    d = Path(directory)
    ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
    if not d.exists():
        return []
    pattern = f"**/*{ext}" if recursive else f"*{ext}"
    return sorted(d.glob(pattern))


def write_temp(data: bytes, suffix: str = ".pdf", prefix: str = "legalai_") -> Path:
    """Write bytes to a temp file and return its Path."""
    import tempfile

    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    try:
        with open(fd, "wb") as f:
            f.write(data)
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise
    return Path(path)
