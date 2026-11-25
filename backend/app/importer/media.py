"""Bring media referenced by imported content into Minet storage.

Rules enforced here, because employee-facing content must never depend on
OpenMAIC URLs or asset ids:

  * Only references we can resolve safely are fetched. An `ast_…` asset id goes
    to OpenMAIC's asset endpoint; an archive path is read from the uploaded ZIP.
    Arbitrary http(s) URLs are never downloaded; `data:` URIs and legacy
    placeholder ids are refused.
  * Bytes are validated (size cap, media-type allowlist, magic-number sniffing)
    before being stored.
  * The same reference is downloaded once per import, and identical bytes are
    stored once per course (checksum), including across re-imports.
  * A reference that cannot be imported yields `None`; the caller flags the
    block. Nothing is silently dropped and nothing broken is left looking fine.
"""
from __future__ import annotations

import hashlib
import logging
import mimetypes
import re
from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..lms_models import Course, MediaAsset
from ..storage import get_storage, sanitize_filename
from .report import ImportReport

log = logging.getLogger("minet.importer.media")

ASSET_ID = re.compile(r"^ast_[A-Za-z0-9_-]{8,128}$")
ALLOWED_PREFIXES = ("image/", "audio/", "video/")
KIND_BY_PREFIX = {"image/": "image", "audio": "audio", "video/": "video"}


class MediaFetchError(RuntimeError):
    """A reference could not be fetched. `reason` is shown to the administrator."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class Fetched:
    payload: bytes
    content_type: Optional[str] = None
    filename: Optional[str] = None


# A source turns a reference into bytes. It raises MediaFetchError on failure.
Source = Callable[[str], Fetched]

_MAGIC: list[tuple[bytes, int, str]] = [
    (b"\x89PNG\r\n\x1a\n", 0, "image/png"),
    (b"\xff\xd8\xff", 0, "image/jpeg"),
    (b"GIF87a", 0, "image/gif"),
    (b"GIF89a", 0, "image/gif"),
    (b"ID3", 0, "audio/mpeg"),
    (b"OggS", 0, "audio/ogg"),
    (b"\x1aE\xdf\xa3", 0, "video/webm"),
    (b"fLaC", 0, "audio/flac"),
]


def sniff(payload: bytes) -> Optional[str]:
    """Identify common media by magic number. None if it is not recognised."""
    head = payload[:32]
    for magic, offset, mime in _MAGIC:
        if head[offset:offset + len(magic)] == magic:
            return mime
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio/wav"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"avif", b"avis"):
            return "image/avif"
        if brand in (b"M4A ", b"M4B "):
            return "audio/mp4"
        return "video/mp4"
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        return "audio/mpeg"
    stripped = payload[:512].lstrip()
    if stripped.startswith((b"<svg", b"<?xml")) and b"<svg" in payload[:2048]:
        return "image/svg+xml"
    return None


def classify(ref: str) -> str:
    """'asset' | 'path' | 'external' | 'data' | 'placeholder' | 'empty'."""
    value = (ref or "").strip()
    if not value:
        return "empty"
    lowered = value.lower()
    if lowered.startswith("data:"):
        return "data"
    if lowered.startswith(("http://", "https://", "//")):
        return "external"
    if ASSET_ID.match(value):
        return "asset"
    if "/" in value or "." in value.rsplit("/", 1)[-1]:
        return "path"
    return "placeholder"


class MediaImporter:
    def __init__(self, db: Session, course: Course, report: ImportReport, *,
                 source: Source, uploaded_by_id: Optional[int],
                 resolve_path: Optional[Callable[[str], Optional[str]]] = None) -> None:
        self.db = db
        self.course = course
        self.report = report
        self.source = source
        self.uploaded_by_id = uploaded_by_id
        self.resolve_path = resolve_path
        self._cache: dict[str, Optional[int]] = {}
        self._failures: dict[str, str] = {}

    def failure_reason(self, ref: str) -> str:
        return self._failures.get(ref, "The media could not be imported.")

    def import_ref(self, ref: str, kind_hint: str = "image") -> Optional[MediaAsset]:
        """Return the stored Minet asset for `ref`, or None (with a recorded reason)."""
        key = (ref or "").strip()
        if key in self._cache:
            cached = self._cache[key]
            return self.db.get(MediaAsset, cached) if cached else None
        asset = self._import(key, kind_hint)
        self._cache[key] = asset.id if asset else None
        return asset

    def _fail(self, key: str, kind: str, reason: str) -> None:
        self._failures[key] = reason
        self.report.unsupported_item(kind, f"{key[:160]}: {reason}")

    def _import(self, key: str, kind_hint: str) -> Optional[MediaAsset]:
        kind = classify(key)
        if kind == "empty":
            self._fail(key or "(empty)", "missing_media", "The reference was empty.")
            return None
        if kind == "data":
            self._fail(key[:40], "data_uri", "Inline data URIs are not imported.")
            return None
        if kind == "external":
            self._fail(key, "external_media",
                       "External URLs are not downloaded. Replace it with an uploaded file.")
            return None
        if kind == "placeholder":
            self._fail(key, "legacy_reference",
                       "This is a legacy placeholder id with no asset to download.")
            return None

        lookup = key
        if kind == "path" and self.resolve_path is not None:
            lookup = self.resolve_path(key) or key
        try:
            fetched = self.source(lookup)
        except MediaFetchError as exc:
            self._fail(key, "missing_media", exc.reason)
            return None
        except Exception as exc:  # noqa: BLE001 - never abort an import for one asset
            log.warning("Unexpected media failure for %s: %s", key, exc)
            self._fail(key, "missing_media", f"Unexpected error: {exc}")
            return None

        payload = fetched.payload or b""
        if not payload:
            self._fail(key, "missing_media", "The file was empty.")
            return None
        if len(payload) > config.MAX_UPLOAD_BYTES:
            self._fail(key, "missing_media", "The file is larger than the per-file limit.")
            return None

        sniffed = sniff(payload)
        declared = (fetched.content_type or "").split(";")[0].strip().lower()
        guessed = mimetypes.guess_type(fetched.filename or key)[0] or ""
        mime = sniffed or (declared if declared.startswith(ALLOWED_PREFIXES) else "") \
            or (guessed if guessed.startswith(ALLOWED_PREFIXES) else "")
        if not mime or not mime.startswith(ALLOWED_PREFIXES):
            self._fail(key, "unexpected_file_type",
                       f"Not a recognised image, audio or video file ({declared or 'unknown'}).")
            return None

        checksum = hashlib.sha256(payload).hexdigest()
        existing = self.db.scalar(select(MediaAsset).where(
            MediaAsset.course_id == self.course.id, MediaAsset.checksum == checksum,
            MediaAsset.visibility == "course", MediaAsset.deleted_at.is_(None)))
        if existing is not None:
            self.report.assets_reused += 1
            return existing

        extension = mimetypes.guess_extension(mime) or ""
        filename = sanitize_filename(fetched.filename or key.rsplit("/", 1)[-1] or "media")
        if extension and not filename.lower().endswith(extension):
            filename = f"{filename}{extension}"
        stored = get_storage().save_bytes(f"courses/{self.course.id}/media", filename, payload)
        asset = MediaAsset(
            original_filename=filename, stored_filename=stored.stored_filename,
            storage_key=stored.storage_key, mime_type=mime, size_bytes=stored.size_bytes,
            checksum=stored.checksum, visibility="course", course_id=self.course.id,
            kind=("image" if mime.startswith("image/")
                  else "audio" if mime.startswith("audio/") else "video"),
            uploaded_by_id=self.uploaded_by_id)
        self.db.add(asset)
        self.db.flush()
        self.report.media_files += 1
        self.report.media_bytes += asset.size_bytes
        return asset
