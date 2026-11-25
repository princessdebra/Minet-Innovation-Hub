"""Import entry points.

  import_archive(...)   an uploaded ZIP. Two shapes are recognised:
        * a real OpenMAIC `.maic.zip` -- `manifest.json` with formatVersion and
          typed scenes. Mapped by the same typed mapper used for the API path.
        * a hand-made HTML/JSON export -- decomposed into blocks as before.
  maic.import_document(...)   a document fetched from OpenMAIC's persistence API.

Both share `maic.persist_course` and `media.MediaImporter`, so media handling,
idempotency and review flagging behave identically.
"""
from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import posixpath
from typing import Optional

from sqlalchemy.orm import Session

from ..lms_models import Course
from . import html_blocks, maic
from .archive import ArchiveEntry, ArchiveError, ClassroomArchive
from .html_blocks import ExtractedLesson
from .maic import ExtractedCourse, ExtractedScene, MaicFormatError
from .media import Fetched, MediaFetchError, MediaImporter
from .report import ImportReport

log = logging.getLogger("minet.importer")


def _match_entry(ref: str, entries: list[ArchiveEntry]) -> Optional[ArchiveEntry]:
    cleaned = ref.split("?")[0].split("#")[0].replace("\\", "/").lstrip("./")
    if not cleaned:
        return None
    normalised = posixpath.normpath(cleaned)
    by_name = {e.name: e for e in entries}
    if normalised in by_name:
        return by_name[normalised]
    base = normalised.rsplit("/", 1)[-1].lower()
    for entry in entries:
        if entry.name.rsplit("/", 1)[-1].lower() == base:
            return entry
    for entry in entries:
        if entry.name.lower().endswith("/" + base):
            return entry
    return None


def _zip_source(archive: ClassroomArchive, source_index: dict[str, str]):
    """Resolve a reference to bytes inside the archive."""
    entries = list(archive.media())

    def source(ref: str) -> Fetched:
        target = source_index.get(ref) or ref
        entry = _match_entry(target, entries)
        if entry is None:
            raise MediaFetchError("The file is not in the uploaded archive.")
        payload = archive.read(entry)
        if payload is None:
            raise MediaFetchError("The file could not be read from the archive.")
        return Fetched(payload=payload, content_type=mimetypes.guess_type(entry.name)[0],
                       filename=entry.name.rsplit("/", 1)[-1])
    return source


def _is_maic_manifest(document: object) -> bool:
    return (isinstance(document, dict) and isinstance(document.get("scenes"), list)
            and isinstance(document.get("stage"), dict) and "formatVersion" in document)


def _from_manifest(manifest: dict, digest: str) -> dict:
    """Shape a `.maic.zip` manifest like an API document so one mapper serves both.

    The manifest's stage has no id, so one is derived from the file's checksum;
    re-uploading the identical export is therefore recognised as a re-import.
    """
    stage = dict(manifest["stage"])
    stage["id"] = f"zip-{digest[:20]}"
    return {"stage": stage, "scenes": manifest["scenes"], "outline": None}


def _html_to_course(lessons: list[ExtractedLesson], course: Course, digest: str) -> ExtractedCourse:
    scenes = [ExtractedScene(
        title=lesson.title, description=None, blocks=lesson.blocks,
        needs_review=any(b.needs_review for b in lesson.blocks)) for lesson in lessons]
    return ExtractedCourse(stage_id=f"html-{digest[:20]}", name="Course content",
                           description=None, scenes=scenes, questions=[])


def import_archive(db: Session, course: Course, archive_path, *,
                   uploaded_by_id: Optional[int], report: Optional[ImportReport] = None,
                   replace: bool = False) -> ImportReport:
    report = report or ImportReport()
    with open(archive_path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()

    with ClassroomArchive(archive_path, report) as archive:
        manifest_entry = archive.find_manifest()
        manifest = None
        if manifest_entry is not None:
            raw = archive.read_text(manifest_entry)
            if raw:
                try:
                    manifest = json.loads(raw)
                except ValueError:
                    report.warn(f"{manifest_entry.name} is not valid JSON; trying the HTML export.")

        # --- a real OpenMAIC export -------------------------------------------
        if _is_maic_manifest(manifest):
            report.source = "maic_zip"
            source_index = {
                str(entry.get("sourceRef")): path
                for path, entry in (manifest.get("mediaIndex") or {}).items()
                if isinstance(entry, dict) and entry.get("sourceRef")
                and not entry.get("missing")}
            for path, entry in (manifest.get("mediaIndex") or {}).items():
                if isinstance(entry, dict) and entry.get("missing"):
                    report.unsupported_item(
                        "missing_media", f"{path} was missing when OpenMAIC exported this.", "")
            document = _from_manifest(manifest, digest)
            extracted = maic.extract_document(document, report)
            media = MediaImporter(db, course, report, source=_zip_source(archive, source_index),
                                  uploaded_by_id=uploaded_by_id)
            return maic.persist_course(db, course, extracted, media, report, replace=replace)

        # --- a hand-made HTML export ------------------------------------------
        report.source = "export_archive"
        lessons: list[ExtractedLesson] = []
        html_entry = archive.find_primary_html()
        if html_entry is not None:
            markup = archive.read_text(html_entry)
            if markup:
                lessons = html_blocks.extract_lessons(markup, fallback_title=course.title)
            else:
                report.warn(f"{html_entry.name} could not be decoded as text.")
        if not lessons:
            raise ArchiveError(
                "No lessons could be read from this export. Expected an OpenMAIC "
                "manifest.json or an HTML export inside the archive.")

        media = MediaImporter(db, course, report, source=_zip_source(archive, {}),
                              uploaded_by_id=uploaded_by_id)
        # Capture references now: persisting clears them from the blocks.
        referenced = {b.media_ref for lsn in lessons for b in lsn.blocks if b.media_ref}
        extracted = _html_to_course(lessons, course, digest)
        persist = maic.persist_course(db, course, extracted, media, report, replace=replace)
        if persist.already_imported:
            return persist

        # Media in the archive that no lesson referenced is still preserved.
        referenced_names = {r.rsplit("/", 1)[-1].lower() for r in referenced}
        for entry in archive.media():
            if entry.name.rsplit("/", 1)[-1].lower() in referenced_names:
                continue
            asset = media.import_ref(entry.name, entry.kind)
            if asset is not None:
                report.unsupported_item(
                    "unreferenced_media",
                    f"{entry.name} was in the export but no lesson referenced it. "
                    f"It is stored as asset {asset.id}.", "")
        return persist


__all__ = ["import_archive", "MaicFormatError"]
