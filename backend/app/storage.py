"""File storage abstraction.

`LocalStorage` writes under `STORAGE_ROOT`. The interface is deliberately small
(`save`, `open`, `path`, `delete`, `exists`) so an S3 backend can be dropped in
without touching callers.

Storage keys are server-generated (`<prefix>/<uuid><ext>`); a client-supplied
filename never reaches the filesystem.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator, Optional

from . import config

SAFE_EXT = re.compile(r"^[A-Za-z0-9]{1,12}$")


@dataclass
class StoredFile:
    storage_key: str
    stored_filename: str
    size_bytes: int
    checksum: str


def safe_extension(filename: str) -> str:
    """Return a lowercase `.ext` we are willing to put on disk, or ''."""
    ext = os.path.splitext(filename or "")[1].lstrip(".").lower()
    return f".{ext}" if SAFE_EXT.match(ext) else ""


def sanitize_filename(filename: str) -> str:
    """A display-safe original name. Never used as a path."""
    name = os.path.basename(filename or "").strip() or "file"
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    return name[:255]


class LocalStorage:
    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root or config.STORAGE_ROOT)

    # -- helpers ------------------------------------------------------------

    def _resolve(self, storage_key: str) -> Path:
        """Resolve a key inside the root, refusing anything that escapes it."""
        if not storage_key or storage_key.startswith(("/", "\\")) or ".." in storage_key:
            raise ValueError(f"Unsafe storage key: {storage_key!r}")
        root = self.root.resolve()
        target = (root / storage_key).resolve()
        if root != target and root not in target.parents:
            raise ValueError(f"Storage key escapes the root: {storage_key!r}")
        return target

    # -- API ----------------------------------------------------------------

    def save_stream(self, prefix: str, filename: str, stream: BinaryIO,
                    max_bytes: Optional[int] = None) -> StoredFile:
        """Stream to disk while hashing and enforcing a size cap."""
        limit = config.MAX_UPLOAD_BYTES if max_bytes is None else max_bytes
        ext = safe_extension(filename)
        stored_filename = f"{uuid.uuid4().hex}{ext}"
        storage_key = f"{prefix.strip('/')}/{stored_filename}"
        target = self._resolve(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)

        digest = hashlib.sha256()
        size = 0
        try:
            with open(target, "wb") as out:
                while True:
                    chunk = stream.read(1024 * 256)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > limit:
                        raise ValueError(f"File exceeds the {limit} byte limit")
                    digest.update(chunk)
                    out.write(chunk)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return StoredFile(storage_key, stored_filename, size, digest.hexdigest())

    def save_bytes(self, prefix: str, filename: str, payload: bytes,
                   max_bytes: Optional[int] = None) -> StoredFile:
        import io
        return self.save_stream(prefix, filename, io.BytesIO(payload), max_bytes)

    def open(self, storage_key: str) -> BinaryIO:
        return open(self._resolve(storage_key), "rb")

    def read_bytes(self, storage_key: str) -> bytes:
        return self._resolve(storage_key).read_bytes()

    def path(self, storage_key: str) -> Path:
        return self._resolve(storage_key)

    def exists(self, storage_key: str) -> bool:
        try:
            return self._resolve(storage_key).is_file()
        except ValueError:
            return False

    def delete(self, storage_key: str) -> bool:
        try:
            target = self._resolve(storage_key)
        except ValueError:
            return False
        if target.is_file():
            target.unlink()
            return True
        return False

    def delete_prefix(self, prefix: str) -> int:
        try:
            target = self._resolve(prefix)
        except ValueError:
            return 0
        if not target.is_dir():
            return 0
        count = sum(1 for _ in target.rglob("*") if _.is_file())
        shutil.rmtree(target, ignore_errors=True)
        return count

    def stream(self, storage_key: str, chunk_size: int = 1024 * 256) -> Iterator[bytes]:
        with self.open(storage_key) as fh:
            while True:
                chunk = fh.read(chunk_size)
                if not chunk:
                    return
                yield chunk


_storage: Optional[LocalStorage] = None


def get_storage() -> LocalStorage:
    global _storage
    if _storage is None:
        if config.STORAGE_BACKEND != "local":
            raise RuntimeError(
                f"STORAGE_BACKEND={config.STORAGE_BACKEND!r} is not implemented; "
                "only 'local' is available in this build.")
        _storage = LocalStorage()
    return _storage
