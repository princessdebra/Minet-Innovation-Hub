"""Tests for the typed OpenMAIC importer.

Test layers (labelled, because they prove different things):

  UNIT         pure extraction from fixture documents; no database, no network.
  INTEGRATION  importer + MySQL + local file storage, with an in-memory asset
               source standing in for OpenMAIC's asset route.
  HTTP STUB    Minet's real HTTP client against a local server that implements the
               verified routes (see test_openmaic_integration.py).
  LIVE         needs a running OpenMAIC; see test_live_openmaic.py (skipped here).

Fixtures follow the real @openmaic/dsl types (see maic_fixtures.py). Not verified
against source, so assumed: QuizOption shape, PBL project schema, outline fields.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.importer.archive import ArchiveError
from app.importer.maic import MaicFormatError, extract_document, import_document
from app.importer.mapper import import_archive
from app.importer.media import Fetched, MediaFetchError, classify, sniff
from app.importer.report import ImportReport
from app.lms_models import (Assessment, ContentBlock, Course, CourseModule, Lesson,
                            MediaAsset)
from app.lms_services import grade_attempt, unique_slug
from app.main import app
from app.storage import get_storage
from tests import maic_fixtures as fx
from tests.test_lms import _delete_course

client = TestClient(app)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class Source:
    """An asset source backed by a dict, counting every download."""

    def __init__(self, assets: dict[str, bytes] | None = None) -> None:
        self.assets = fx.ASSETS if assets is None else assets
        self.calls: list[str] = []

    def __call__(self, ref: str) -> Fetched:
        self.calls.append(ref)
        if ref not in self.assets:
            raise MediaFetchError("OpenMAIC returned 404 for this asset.")
        return Fetched(payload=self.assets[ref], content_type="application/octet-stream")


@pytest.fixture
def course():
    with SessionLocal() as db:
        record = Course(slug=unique_slug(db, "maic import test"), title="MAIC import test",
                        summary="Test course.", owner_id=1, status="draft")
        db.add(record)
        db.commit()
        course_id = record.id
    yield course_id
    _delete_course(course_id)
    get_storage().delete_prefix(f"courses/{course_id}")


def _import(course_id: int, source: Source | None = None, *, replace: bool = False,
            document: dict | None = None) -> tuple[ImportReport, Source]:
    source = source or Source()
    report = ImportReport()
    with SessionLocal() as db:
        record = db.get(Course, course_id)
        import_document(db, record, document or fx.document(), source=source,
                        uploaded_by_id=1, report=report, replace=replace)
        db.commit()
    return report, source


def _lessons(course_id: int) -> dict[str, tuple[Lesson, list[ContentBlock]]]:
    with SessionLocal() as db:
        out = {}
        for module in db.scalars(select(CourseModule).where(CourseModule.course_id == course_id)):
            for lesson in db.scalars(select(Lesson).where(Lesson.module_id == module.id)
                                     .order_by(Lesson.position)):
                blocks = list(db.scalars(select(ContentBlock).where(
                    ContentBlock.lesson_id == lesson.id).order_by(ContentBlock.position)))
                db.expunge_all()
                out[lesson.title] = (lesson, blocks)
        return out


# ---------------------------------------------------------------------------
# UNIT: extraction
# ---------------------------------------------------------------------------

def test_unit_scenes_are_ordered_by_the_order_field_not_array_position():
    course = extract_document(fx.document(), ImportReport())
    assert [s.title for s in course.scenes] == [
        "Why triage matters", "The three checks", "Check your understanding",
        "Claims simulator", "Redesign the journey"]


def test_unit_slide_text_is_read_from_canvas_elements_in_reading_order():
    report = ImportReport()
    course = extract_document(fx.document(), report)
    slide = course.scenes[0]
    text_blocks = [b for b in slide.blocks if b.block_type == "rich_text"]
    combined = " ".join(b.data["text"] for b in text_blocks)
    # reading order: top 120 before top 200, then the shape callout
    assert combined.index("what happens next") < combined.index("Second paragraph")
    assert "Callout inside a shape" in combined
    # the title element duplicated the lesson title and the page number is decoration
    assert "Why triage matters" not in combined
    assert report.decorative_skipped >= 3          # partNumber, plain shape, line, background


def test_unit_slide_tables_charts_latex_and_code_become_readable_text():
    slide = extract_document(fx.document(), ImportReport()).scenes[0]
    html = " ".join(b.data["html"] for b in slide.blocks if b.block_type == "rich_text")
    assert "<table>" in html and "Claims team" in html           # table cells
    assert "Chart (column)" in html and "Q2" in html             # chart data as a table
    assert "x^2 + y^2" in html                                    # latex source kept
    assert "print(&#x27;triage&#x27;)" in html or "print('triage')" in html


def test_unit_media_elements_become_blocks_that_reference_assets():
    slide = extract_document(fx.document(), ImportReport()).scenes[0]
    by_type = {b.block_type: b for b in slide.blocks if b.media_ref}
    assert by_type["image"].media_ref == fx.IMG       # background image was skipped
    assert by_type["video"].media_ref == fx.VID
    assert [b.media_ref for b in slide.blocks if b.block_type == "audio"] == [fx.AUD, fx.AUD2]


def test_unit_narration_keeps_text_and_audio_references():
    slide = extract_document(fx.document(), ImportReport()).scenes[0]
    notes = next(b for b in slide.blocks if b.block_type == "notes")
    assert notes.title == "Narration"
    assert "Triage decides what happens next." in notes.data["text"]
    assert "Let us look at the journey." in notes.data["text"]
    assert "spotlight" not in notes.data["text"]


def test_unit_discussion_prompts_are_reported_not_silently_lost():
    report = ImportReport()
    extract_document(fx.document(), report)
    assert any("discussion" in w for w in report.warnings)


def test_unit_quiz_questions_map_to_gradable_minet_questions():
    report = ImportReport()
    course = extract_document(fx.document(), report)
    by_prompt = {q.prompt: q for q in course.questions}
    single = by_prompt["What comes first?"]
    assert (single.kind, single.correct, single.marks) == ("single", ["a"], 2)
    assert [o["text"] for o in single.options] == ["Triage", "Payment"]
    assert single.explanation == "Triage always comes first."
    assert by_prompt["Which are valid channels?"].correct == ["a", "b"]
    assert by_prompt["Name the first step."].correct == ["triage", "triaging"]
    # a correctly mapped quiz is NOT flagged merely for coming from OpenMAIC
    quiz_scene = next(s for s in course.scenes if s.title == "Check your understanding")
    assert any("ungradable" in u["kind"] for u in report.unsupported)   # only the open-ended one
    assert "Reflect on a claim" not in {q.prompt for q in course.questions}
    assert quiz_scene.needs_review is True      # because one question was dropped
    clean = fx.document()
    clean["scenes"][0]["content"]["questions"].pop()          # remove the ungradable one
    clean_scene = extract_document(clean, ImportReport()).scenes
    assert not next(s for s in clean_scene if s.title == "Check your understanding").needs_review


def test_unit_interactive_scene_is_preserved_and_flagged_without_its_script():
    report = ImportReport()
    course = extract_document(fx.document(), report)
    scene = next(s for s in course.scenes if s.title == "Claims simulator")
    block = scene.blocks[0]
    assert block.block_type == "unsupported" and scene.needs_review
    assert block.data["widget_type"] == "simulation"
    assert "Simulate a claim here." in block.data["text"]
    assert "steal()" not in block.data["text"]                  # script text never extracted
    assert block.data["source"]["html"].startswith("<div>")     # original preserved for review
    assert any(u["kind"] == "interactive_scene" for u in report.unsupported)


def test_unit_pbl_scene_instructions_are_extracted_and_original_preserved():
    course = extract_document(fx.document(), ImportReport())
    scene = next(s for s in course.scenes if s.title == "Redesign the journey")
    block = scene.blocks[0]
    assert scene.needs_review and block.block_type == "unsupported"
    assert "Redesign a claims journey" in block.data["text"]
    assert "Propose one change" in block.data["text"]
    assert block.data["source"]["project"]["tasks"][0]["title"] == "Map the current journey"


def test_unit_unknown_scene_type_is_preserved_not_dropped():
    document = fx.document()
    document["scenes"].append({"id": "s9", "title": "Hologram", "order": 9, "type": "hologram",
                               "content": {"type": "hologram", "mesh": "x"}})
    scene = next(s for s in extract_document(document, ImportReport()).scenes
                 if s.title == "Hologram")
    assert scene.needs_review and scene.blocks[0].data["source"]["content"]["mesh"] == "x"


def test_unit_non_documents_are_rejected():
    for bad in (None, [], {"scenes": "nope"}, {"stage": {}, "scenes": []}):
        with pytest.raises(MaicFormatError):
            extract_document(bad, ImportReport())


def test_unit_reference_classification_and_sniffing():
    assert classify(fx.IMG) == "asset"
    assert classify("audio/audio-1.mp3") == "path"
    assert classify("https://example.com/a.png") == "external"
    assert classify("data:image/png;base64,AAAA") == "data"
    assert classify("gen_img_legacy_4") == "placeholder"
    assert classify("") == "empty"
    assert sniff(fx.PNG) == "image/png" and sniff(fx.MP4) == "video/mp4"
    assert sniff(fx.MP3) == "audio/mpeg" and sniff(b"<html>nope</html>") is None


# ---------------------------------------------------------------------------
# INTEGRATION: persistence, media, idempotency
# ---------------------------------------------------------------------------

def test_integration_import_creates_lessons_blocks_and_stores_media(course):
    report, source = _import(course)
    assert (report.modules, report.lessons) == (1, 5)
    lessons = _lessons(course)
    first, blocks = lessons["Why triage matters"]
    kinds = [b.block_type for b in blocks]
    assert {"rich_text", "image", "video", "audio", "notes"} <= set(kinds)
    for block in blocks:
        if block.block_type in ("image", "video", "audio") and not block.data.get("broken_media"):
            assert block.data["src"].startswith("/api/lms/assets/")
            assert block.asset_id is not None
            # employee-facing data carries no OpenMAIC asset id
            assert "ast_" not in json.dumps(block.data)
    with SessionLocal() as db:
        asset = db.get(MediaAsset, next(b.asset_id for b in blocks if b.block_type == "image"))
        assert asset.visibility == "course" and asset.mime_type == "image/png"
        assert get_storage().exists(asset.storage_key)


def test_integration_duplicate_asset_references_download_once(course):
    _, source = _import(course)
    # IMG appears on two slides but is fetched a single time
    assert source.calls.count(fx.IMG) == 1
    assert source.calls.count(fx.AUD) == 1


def test_integration_identical_bytes_are_stored_once_per_course(course):
    shared = {**fx.ASSETS, fx.AUD2: fx.MP3}        # a different id with identical bytes
    report, _ = _import(course, Source(shared))
    assert report.assets_reused >= 1
    with SessionLocal() as db:
        rows = db.scalars(select(MediaAsset).where(
            MediaAsset.course_id == course, MediaAsset.kind == "audio")).all()
        assert len(rows) == 1
        assert len({r.checksum for r in rows}) == len(rows)


def test_integration_failed_missing_legacy_and_external_media_are_flagged(course):
    report, _ = _import(course)
    kinds = {u["kind"] for u in report.unsupported}
    assert {"missing_media", "legacy_reference", "external_media"} <= kinds
    lesson, blocks = _lessons(course)["The three checks"]
    broken = [b for b in blocks if b.data.get("broken_media")]
    assert len(broken) == 3 and lesson.needs_review
    assert all(b.needs_review and b.import_note and "src" not in b.data for b in broken)
    # the external URL was never fetched
    assert all(not r.startswith("http") for r in Source().calls)


def test_integration_publishing_is_blocked_while_media_is_broken(course):
    _import(course)
    refused = client.post(f"/api/lms/admin/courses/{course}/publish",
                          json={"acknowledged_ai_review": True})
    assert refused.status_code == 422
    assert "failed to import" in refused.json()["detail"]["errors"]["media"]
    # deleting the broken blocks clears the guard
    with SessionLocal() as db:
        for block in db.scalars(select(ContentBlock)):
            if (block.data or {}).get("broken_media"):
                db.delete(block)
        db.commit()
    assert client.post(f"/api/lms/admin/courses/{course}/publish",
                       json={"acknowledged_ai_review": True}).status_code == 200


def test_integration_quiz_becomes_a_graded_assessment_without_review_flag(course):
    report, _ = _import(course)
    assert report.questions == 3
    with SessionLocal() as db:
        assessment = db.scalar(select(Assessment).where(Assessment.course_id == course))
        assert assessment.is_published and not assessment.needs_review
        questions = list(assessment.questions)
        ids = {q.prompt: q.id for q in questions}
        right = grade_attempt(questions, {
            str(ids["What comes first?"]): "a",
            str(ids["Which are valid channels?"]): ["a", "b"],
            str(ids["Name the first step."]): "Triaging"})
        assert right["percent"] == 100 and right["max_score"] == 4
        wrong = grade_attempt(questions, {str(ids["What comes first?"]): "b"})
        assert wrong["percent"] == 0


def test_integration_unsupported_scenes_keep_their_original_data(course):
    _import(course)
    lessons = _lessons(course)
    sim = lessons["Claims simulator"]
    assert sim[0].needs_review
    assert sim[1][0].meta["original"]["html"].startswith("<div>")
    assert sim[1][0].needs_review and sim[1][0].import_note
    pbl = lessons["Redesign the journey"][1][0]
    assert pbl.meta["original"]["project"]["title"] == "Redesign a claims journey"


def test_integration_reimporting_the_same_course_does_not_duplicate(course):
    _import(course)
    report, source = _import(course)
    assert report.already_imported and report.lessons == 0
    assert source.calls == []                       # nothing downloaded again
    assert sum(len(b) for _, b in _lessons(course).values()) > 0
    assert len(_lessons(course)) == 5


def test_integration_replace_overwrites_instead_of_duplicating(course):
    _import(course)
    report, _ = _import(course, replace=True)
    assert not report.already_imported and report.lessons == 5
    assert len(_lessons(course)) == 5
    with SessionLocal() as db:
        assert db.scalar(select(Assessment).where(Assessment.course_id == course)) is not None
        assert len(db.scalars(select(Assessment).where(Assessment.course_id == course)).all()) == 1


def test_integration_stage_description_fills_an_empty_course_description(course):
    with SessionLocal() as db:
        db.get(Course, course).description = None
        db.commit()
    _import(course)
    with SessionLocal() as db:
        assert db.get(Course, course).description == "How claims are triaged."


# ---------------------------------------------------------------------------
# INTEGRATION: archives
# ---------------------------------------------------------------------------

def _post_zip(course_id: int, payload: bytes, **data):
    return client.post(f"/api/lms/admin/courses/{course_id}/import",
                       files={"file": ("classroom.maic.zip", payload, "application/zip")},
                       data=data)


def test_integration_real_maic_zip_uses_the_same_typed_mapper(course):
    response = _post_zip(course, fx.maic_zip())
    assert response.status_code == 201, response.text
    report = response.json()["report"]
    assert report["source"] == "maic_zip"
    assert (report["lessons"], report["questions"]) == (5, 3)
    lessons = _lessons(course)
    blocks = lessons["Why triage matters"][1]
    # slide text, not just titles, came through a manifest scene
    assert any("what happens next" in str(b.data.get("text")) for b in blocks)
    audio = [b for b in blocks if b.block_type == "audio"]
    assert len(audio) == 2 and all(b.data["src"].startswith("/api/lms/assets/") for b in audio)
    assert any(b.block_type == "image" and b.data.get("src") for b in blocks)


def test_integration_maic_zip_reupload_is_recognised(course):
    payload = fx.maic_zip()
    assert _post_zip(course, payload).status_code == 201
    again = _post_zip(course, payload).json()["report"]
    assert again["already_imported"] and again["lessons"] == 0
    assert len(_lessons(course)) == 5
    replaced = _post_zip(course, payload, replace="true").json()["report"]
    assert replaced["lessons"] == 5 and len(_lessons(course)) == 5


def test_integration_maic_zip_flags_media_missing_from_the_archive(course):
    manifest = fx.manifest()
    import io, zipfile
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))   # no media files at all
    response = _post_zip(course, buffer.getvalue())
    assert response.status_code == 201
    report = response.json()["report"]
    assert any(u["kind"] == "missing_media" for u in report["unsupported"])
    assert client.post(f"/api/lms/admin/courses/{course}/publish",
                       json={"acknowledged_ai_review": True}).status_code == 422


def test_integration_hand_made_html_archive_still_imports(course):
    html = b"""<html><head><title>Basics</title></head><body>
    <section class="slide"><h2>What is a claim?</h2><p>A request for payment.</p>
    <img src="media/diagram.png" alt="Journey"></section></body></html>"""
    import io, zipfile
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("index.html", html)
        archive.writestr("media/diagram.png", fx.PNG)
    response = _post_zip(course, buffer.getvalue())
    assert response.status_code == 201, response.text
    report = response.json()["report"]
    assert report["source"] == "export_archive" and report["lessons"] == 1
    assert report["media_files"] == 1
    assert _post_zip(course, buffer.getvalue()).json()["report"]["already_imported"]


def test_integration_archive_without_a_usable_manifest_or_html_is_refused(course):
    import io, zipfile
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notes.txt", "nothing useful")
    response = _post_zip(course, buffer.getvalue())
    assert response.status_code == 422
    assert "manifest.json" in response.json()["detail"]["errors"]["file"]
