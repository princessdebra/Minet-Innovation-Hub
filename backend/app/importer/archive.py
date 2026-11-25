"""Safe reading of an uploaded OpenMAIC export archive.

Threats handled: path traversal (`../`, absolute paths, Windows drive letters,
NTFS streams), symlink entries, zip bombs (declared and actual size, entry
count, per-entry ratio), and unexpected file types.

Nothing is written to disk during inspection -- entries are read into memory
one at a time, each capped, so a malicious archive cannot fill the volume.
"""
from __future__ import annotations

import posixpath
import re
import zipfile
from dataclasses import dataclass
from typing import Iterator, Optional

from .. import config
from .report import ImportReport

# Extensions we are prepared to take out of an archive.
TEXTUAL = {"html", "htm", "json", "txt", "md", "markdown", "csv", "vtt", "srt", "xml"}
IMAGES = {"png", "jpg", "jpeg", "gif", "webp", "svg", "avif"}
AUDIO = {"mp3", "wav", "m4a", "aac", "ogg", "opus"}
VIDEO = {"mp4", "webm", "mov", "m4v"}
DOCUMENTS = {"pdf", "pptx", "docx", "xlsx"}
ALLOWED_EXTENSIONS = TEXTUAL | IMAGES | AUDIO | VIDEO | DOCUMENTS

# Per-entry decompression ratio above which we treat an entry as hostile.
MAX_COMPRESSION_RATIO = 200
UNSAFE_NAME = re.compile(r"(^/)|(^[A-Za-z]:)|(\.\.)|(^\\)|(:\$)")


class ArchiveError(ValueError):
    """The archive is unusable or unsafe. Never partially imported."""


@dataclass
class ArchiveEntry:
    name: str              # normalised, forward-slashed, relative
    size: int
    extension: str

    @property
    def kind(self) -> str:
        ext = self.extension
        if ext in IMAGES:
            return "image"
        if ext in AUDIO:
            return "audio"
        if ext in VIDEO:
            return "video"
        if ext in DOCUMENTS:
            return "document"
        if ext in TEXTUAL:
            return "text"
        return "other"


def _normalise(name: str) -> Optional[str]:
    """Return a safe relative path, or None if the entry must be refused."""
    if not name or name.endswith("/"):
        return None
    candidate = name.replace("\\", "/")
    if UNSAFE_NAME.search(candidate):
        return None
    normalised = posixpath.normpath(candidate)
    if normalised.startswith(("/", "../")) or normalised == ".." or normalised == ".":
        return None
    if any(part in ("..", "") for part in normalised.split("/")):
        return None
    if "\x00" in normalised:
        return None
    return normalised


def _extension(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name.rsplit("/", 1)[-1] else ""


class ClassroomArchive:
    """A validated, read-only view of an export ZIP."""

    def __init__(self, path, report: ImportReport) -> None:
        self.path = path
        self.report = report
        self._zip: Optional[zipfile.ZipFile] = None
        self.entries: list[ArchiveEntry] = []

    def __enter__(self) -> "ClassroomArchive":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self) -> None:
        try:
            self._zip = zipfile.ZipFile(self.path)
        except zipfile.BadZipFile as exc:
            raise ArchiveError("That file is not a readable ZIP archive.") from exc

        bad = self._zip.testzip()
        if bad is not None:
            raise ArchiveError(f"The archive is corrupt (first bad entry: {bad}).")

        infos = self._zip.infolist()
        if len(infos) > config.MAX_ARCHIVE_ENTRIES:
            raise ArchiveError(
                f"The archive has {len(infos)} entries, above the "
                f"{config.MAX_ARCHIVE_ENTRIES} limit.")

        declared_total = 0
        for info in infos:
            if info.is_dir():
                continue
            # Unix mode high bits: 0xA000 marks a symlink.
            if (info.external_attr >> 16) & 0xF000 == 0xA000:
                self.report.skip_file(info.filename, "symbolic link")
                continue
            safe = _normalise(info.filename)
            if safe is None:
                self.report.skip_file(info.filename, "unsafe path")
                continue
            ext = _extension(safe)
            if ext not in ALLOWED_EXTENSIONS:
                self.report.skip_file(safe, f"file type .{ext or '(none)'} not accepted")
                continue
            if info.compress_size and info.file_size / max(info.compress_size, 1) > MAX_COMPRESSION_RATIO:
                self.report.skip_file(safe, "compression ratio looks hostile")
                continue
            declared_total += info.file_size
            if declared_total > config.MAX_EXTRACTED_BYTES:
                raise ArchiveError(
                    "The archive expands to more than "
                    f"{config.MAX_EXTRACTED_BYTES // (1024 * 1024)} MiB.")
            self.entries.append(ArchiveEntry(safe, info.file_size, ext))

        if not self.entries:
            raise ArchiveError("The archive contains no files this importer can use.")

    def close(self) -> None:
        if self._zip is not None:
            self._zip.close()
            self._zip = None

    # -- reading ------------------------------------------------------------

    def _original_name(self, safe_name: str) -> Optional[str]:
        assert self._zip is not None
        for info in self._zip.infolist():
            if not info.is_dir() and _normalise(info.filename) == safe_name:
                return info.filename
        return None

    def read(self, entry: ArchiveEntry, max_bytes: Optional[int] = None) -> Optional[bytes]:
        """Read one entry with a hard cap, regardless of its declared size."""
        assert self._zip is not None
        limit = max_bytes or config.MAX_UPLOAD_BYTES
        original = self._original_name(entry.name)
        if original is None:
            return None
        with self._zip.open(original) as fh:
            data = fh.read(limit + 1)
        if len(data) > limit:
            self.report.skip_file(entry.name, "entry larger than the per-file limit")
            return None
        return data

    def read_text(self, entry: ArchiveEntry, max_bytes: int = 8 * 1024 * 1024) -> Optional[str]:
        data = self.read(entry, max_bytes)
        if data is None:
            return None
        for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return None

    # -- discovery ----------------------------------------------------------

    def by_extension(self, *extensions: str) -> list[ArchiveEntry]:
        wanted = {e.lower().lstrip(".") for e in extensions}
        return [e for e in self.entries if e.extension in wanted]

    def media(self) -> Iterator[ArchiveEntry]:
        for entry in self.entries:
            if entry.kind in ("image", "audio", "video", "document"):
                yield entry

    def find_manifest(self) -> Optional[ArchiveEntry]:
        """The most plausible structured description of the classroom."""
        jsons = self.by_extension("json")
        if not jsons:
            return None
        preferred = ("classroom.json", "manifest.json", "course.json", "stage.json",
                     "document.json", "scenes.json", "index.json")
        by_base = {e.name.rsplit("/", 1)[-1].lower(): e for e in jsons}
        for name in preferred:
            if name in by_base:
                return by_base[name]
        # Otherwise the largest JSON at the shallowest depth.
        return sorted(jsons, key=lambda e: (e.name.count("/"), -e.size))[0]

    def find_primary_html(self) -> Optional[ArchiveEntry]:
        htmls = self.by_extension("html", "htm")
        if not htmls:
            return None
        by_base = {e.name.rsplit("/", 1)[-1].lower(): e for e in htmls}
        for name in ("index.html", "classroom.html", "lesson.html"):
            if name in by_base:
                return by_base[name]
        return sorted(htmls, key=lambda e: (e.name.count("/"), -e.size))[0]


def validate_upload_size(size_bytes: int) -> None:
    if size_bytes > config.MAX_ARCHIVE_BYTES:
        raise ArchiveError(
            f"The export is {size_bytes // (1024 * 1024)} MiB, above the "
            f"{config.MAX_ARCHIVE_BYTES // (1024 * 1024)} MiB limit.")
