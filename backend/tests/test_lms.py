"""LMS tests: the full workflow plus the importer and OpenMAIC adapter.

Runs against the real MySQL database like the existing smoke tests. Everything
it creates is removed again so the seeded demo data is left as designed.

    pytest -q
"""
from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.lms_models import (Assessment, AssessmentAttempt, Certificate, ContentBlock,
                            Course, CourseModule, Enrollment, Lesson, LessonProgress,
                            MediaAsset)

client = TestClient(app)
ADMIN = "/api/lms/admin"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _delete_course(course_id: int) -> None:
    """Remove a course and everything hanging off it."""
    with SessionLocal() as db:
        enrolment_ids = [e.id for e in db.query(Enrollment).filter_by(course_id=course_id)]
        if enrolment_ids:
            db.query(LessonProgress).filter(
                LessonProgress.enrollment_id.in_(enrolment_ids)).delete(
                    synchronize_session=False)
        db.query(Enrollment).filter_by(course_id=course_id).delete(synchronize_session=False)
        db.query(Certificate).filter_by(course_id=course_id).delete(synchronize_session=False)
        assessment_ids = [a.id for a in db.query(Assessment).filter_by(course_id=course_id)]
        if assessment_ids:
            db.query(AssessmentAttempt).filter(
                AssessmentAttempt.assessment_id.in_(assessment_ids)).delete(
                    synchronize_session=False)
        db.query(Assessment).filter_by(course_id=course_id).delete(synchronize_session=False)
        course = db.get(Course, course_id)
        if course:
            course.thumbnail_asset_id = None
            db.flush()
            for module in list(course.modules):
                db.delete(module)
            db.flush()
            db.query(MediaAsset).filter_by(course_id=course_id).delete(
                synchronize_session=False)
            db.delete(course)
        db.commit()


@pytest.fixture
def course():
    response = client.post(f"{ADMIN}/courses", json={
        "title": "Claims Handling Fundamentals (test)",
        "summary": "A short internal course used by the automated tests.",
        "objectives": ["Explain the claims journey", "Apply the triage rules"],
        "category": "Claims", "difficulty": "Foundation",
        "target_audience": "New claims colleagues",
    })
    assert response.status_code == 201, response.text
    data = response.json()
    yield data
    _delete_course(data["id"])


def _add_lesson(course_id: int, *, title: str = "What is a claim?",
                completion_rule: str = "view") -> tuple[int, int]:
    module = client.post(f"{ADMIN}/courses/{course_id}/modules",
                         json={"title": "Getting started", "estimated_minutes": 10})
    assert module.status_code == 201, module.text
    module_id = module.json()["id"]
    lesson = client.post(f"{ADMIN}/modules/{module_id}/lessons", json={
        "title": title, "estimated_minutes": 6, "completion_rule": completion_rule})
    assert lesson.status_code == 201, lesson.text
    lesson_id = lesson.json()["id"]
    block = client.post(f"{ADMIN}/lessons/{lesson_id}/blocks", json={
        "block_type": "rich_text", "title": "Overview",
        "data": {"html": "<p>A claim is a request for payment.</p>",
                 "text": "A claim is a request for payment."}})
    assert block.status_code == 201, block.text
    return module_id, lesson_id


def _publish(course_id: int) -> None:
    response = client.post(f"{ADMIN}/courses/{course_id}/publish",
                           json={"acknowledged_ai_review": True})
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# Course authoring and publication
# ---------------------------------------------------------------------------

def test_course_is_created_as_a_draft(course):
    assert course["status"] == "draft"
    assert course["slug"].startswith("claims-handling-fundamentals")
    assert course["origin"] == "manual"


def test_publishing_is_refused_without_lessons(course):
    response = client.post(f"{ADMIN}/courses/{course['id']}/publish", json={})
    assert response.status_code == 422
    assert "modules" in response.json()["detail"]["errors"]


def test_draft_course_is_invisible_to_learners(course):
    _add_lesson(course["id"])
    ids = [c["id"] for c in client.get("/api/lms/catalog").json()["courses"]]
    assert course["id"] not in ids
    assert client.get(f"/api/lms/courses/{course['id']}").status_code == 404


def test_publish_then_appears_in_the_catalogue(course):
    _add_lesson(course["id"])
    _publish(course["id"])
    catalog = client.get("/api/lms/catalog").json()
    entry = next(c for c in catalog["courses"] if c["id"] == course["id"])
    assert entry["lesson_count"] == 1
    assert entry["status"] == "not_started"
    assert "Claims" in catalog["categories"]


def test_admin_preview_works_before_publication(course):
    _add_lesson(course["id"])
    preview = client.get(f"{ADMIN}/courses/{course['id']}/preview")
    assert preview.status_code == 200
    assert preview.json()["preview"] is True
    assert len(preview.json()["modules"]) == 1


# ---------------------------------------------------------------------------
# Learning and progress
# ---------------------------------------------------------------------------

def test_lesson_completion_drives_progress_and_issues_a_certificate(course):
    _, lesson_id = _add_lesson(course["id"])
    _publish(course["id"])

    assert client.post(f"/api/lms/courses/{course['id']}/enrol").status_code == 201

    lesson = client.get(f"/api/lms/lessons/{lesson_id}").json()
    assert lesson["navigation"]["total"] == 1
    assert lesson["lesson"]["blocks"][0]["block_type"] == "rich_text"

    done = client.post(f"/api/lms/lessons/{lesson_id}/complete", json={"seconds_spent": 120})
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "completed"
    assert body["enrollment"]["progress_percent"] == 100
    assert body["enrollment"]["status"] == "completed"
    # No assessment on this course, so a completion certificate is issued.
    assert body["certificate"]["certificate_type"] == "completion"
    assert len(body["certificate"]["verification_code"]) == 12


def test_progress_cannot_be_forged_by_the_client(course):
    _, lesson_id = _add_lesson(course["id"])
    _publish(course["id"])
    client.post(f"/api/lms/courses/{course['id']}/enrol")
    # There is no endpoint that accepts a progress percentage or a status.
    assert client.post(f"/api/lms/lessons/{lesson_id}/complete",
                       json={"seconds_spent": 10, "progress_percent": 100,
                             "status": "completed"}).status_code == 200
    with SessionLocal() as db:
        enrolment = db.query(Enrollment).filter_by(course_id=course["id"]).one()
        # 100 because the single lesson really was completed, not because it was posted.
        assert enrolment.progress_percent == 100
        assert enrolment.seconds_spent == 10


def test_heartbeat_records_time_without_completing(course):
    _, lesson_id = _add_lesson(course["id"])
    _publish(course["id"])
    client.post(f"/api/lms/courses/{course['id']}/enrol")
    response = client.post(f"/api/lms/lessons/{lesson_id}/heartbeat", json={"seconds_spent": 60})
    assert response.status_code == 200
    assert response.json()["seconds_spent"] == 60
    with SessionLocal() as db:
        enrolment = db.query(Enrollment).filter_by(course_id=course["id"]).one()
        assert enrolment.status == "in_progress"
        assert enrolment.completed_at is None


# ---------------------------------------------------------------------------
# Assessments
# ---------------------------------------------------------------------------

def _add_assessment(course_id: int, lesson_id: int | None = None, *,
                    required: bool = True) -> int:
    payload = {
        "title": "Claims triage check",
        "pass_percent": 60, "max_attempts": 3,
        "is_required_for_completion": required, "is_published": True,
        "lesson_id": lesson_id,
        "questions": [
            {"prompt": "Which comes first?", "kind": "single",
             "options": [{"id": "a", "text": "Triage"}, {"id": "b", "text": "Payment"}],
             "correct": ["a"], "marks": 1, "explanation": "Triage always comes first."},
            {"prompt": "Select the two valid channels.", "kind": "multiple",
             "options": [{"id": "a", "text": "Portal"}, {"id": "b", "text": "Email"},
                         {"id": "c", "text": "Carrier pigeon"}],
             "correct": ["a", "b"], "marks": 2},
        ],
    }
    response = client.post(f"{ADMIN}/courses/{course_id}/assessments", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_learner_never_receives_the_answer_key(course):
    _, lesson_id = _add_lesson(course["id"])
    assessment_id = _add_assessment(course["id"])
    _publish(course["id"])

    learner_view = client.get(f"/api/lms/assessments/{assessment_id}").json()
    serialised = repr(learner_view)
    for question in learner_view["questions"]:
        assert "correct" not in question
        assert "explanation" not in question
    assert "Triage always comes first" not in serialised

    admin_view = client.get(f"{ADMIN}/courses/{course['id']}").json()["assessments"][0]
    assert admin_view["questions"][0]["correct"] == ["a"]


def test_assessment_is_graded_on_the_server(course):
    _, lesson_id = _add_lesson(course["id"])
    assessment_id = _add_assessment(course["id"])
    _publish(course["id"])
    client.post(f"/api/lms/courses/{course['id']}/enrol")

    started = client.post(f"/api/lms/assessments/{assessment_id}/attempts")
    assert started.status_code == 201, started.text
    attempt_id = started.json()["id"]
    questions = started.json()["assessment"]["questions"]
    q1, q2 = questions[0]["id"], questions[1]["id"]

    # One right, one wrong -> 1 of 3 marks -> 33%, below the 60% pass mark.
    result = client.post(f"/api/lms/attempts/{attempt_id}/submit",
                         json={"answers": {str(q1): "a", str(q2): ["a"]}})
    assert result.status_code == 200, result.text
    body = result.json()
    assert (body["score"], body["max_score"], body["percent"]) == (1, 3, 33)
    assert body["passed"] is False
    assert body["attempts_left"] == 2
    # Explanations are returned only after submission.
    assert any(r["explanation"] for r in body["results"])


def test_course_completion_requires_passing_the_assessment(course):
    _, lesson_id = _add_lesson(course["id"])
    assessment_id = _add_assessment(course["id"])
    _publish(course["id"])
    client.post(f"/api/lms/courses/{course['id']}/enrol")

    done = client.post(f"/api/lms/lessons/{lesson_id}/complete", json={})
    assert done.json()["enrollment"]["status"] == "in_progress"
    assert done.json()["certificate"] is None

    claim = client.post(f"/api/lms/courses/{course['id']}/certificate")
    assert claim.status_code == 409
    assert any("not yet passed" in b for b in claim.json()["detail"]["blockers"])

    started = client.post(f"/api/lms/assessments/{assessment_id}/attempts").json()
    q1, q2 = [q["id"] for q in started["assessment"]["questions"]]
    passed = client.post(f"/api/lms/attempts/{started['id']}/submit",
                         json={"answers": {str(q1): "a", str(q2): ["a", "b"]}}).json()
    assert passed["percent"] == 100 and passed["passed"] is True
    assert passed["certificate"]["certificate_type"] == "assessed_competency"
    assert passed["certificate"]["score_percent"] == 100


def test_attempt_limit_is_enforced(course):
    _add_lesson(course["id"])
    assessment_id = _add_assessment(course["id"])
    _publish(course["id"])
    for _ in range(3):
        started = client.post(f"/api/lms/assessments/{assessment_id}/attempts").json()
        client.post(f"/api/lms/attempts/{started['id']}/submit", json={"answers": {}})
    refused = client.post(f"/api/lms/assessments/{assessment_id}/attempts")
    assert refused.status_code == 409
    assert "all 3 attempts" in refused.json()["detail"]["message"]


def test_an_attempt_cannot_be_submitted_twice(course):
    _add_lesson(course["id"])
    assessment_id = _add_assessment(course["id"])
    _publish(course["id"])
    started = client.post(f"/api/lms/assessments/{assessment_id}/attempts").json()
    assert client.post(f"/api/lms/attempts/{started['id']}/submit",
                       json={"answers": {}}).status_code == 200
    assert client.post(f"/api/lms/attempts/{started['id']}/submit",
                       json={"answers": {}}).status_code == 409


# ---------------------------------------------------------------------------
# Certificates
# ---------------------------------------------------------------------------

def test_certificate_verification_is_public_and_minimal(course):
    _, lesson_id = _add_lesson(course["id"])
    _publish(course["id"])
    client.post(f"/api/lms/courses/{course['id']}/enrol")
    certificate = client.post(f"/api/lms/lessons/{lesson_id}/complete",
                              json={}).json()["certificate"]

    verified = client.get(f"/api/lms/certificates/verify/{certificate['verification_code']}")
    assert verified.status_code == 200
    body = verified.json()
    assert body["valid"] is True
    assert body["course_title"] == course["title"]
    assert "not an externally accredited qualification" in body["note"]
    # Nothing beyond the certificate facts is exposed.
    assert "user_id" not in body and "email" not in repr(body)

    assert client.get("/api/lms/certificates/verify/NOTAREALCODE").json()["valid"] is False


def test_revoked_certificate_fails_verification(course):
    _, lesson_id = _add_lesson(course["id"])
    _publish(course["id"])
    client.post(f"/api/lms/courses/{course['id']}/enrol")
    certificate = client.post(f"/api/lms/lessons/{lesson_id}/complete",
                              json={}).json()["certificate"]

    revoked = client.post(f"{ADMIN}/certificates/{certificate['id']}/revoke",
                          json={"reason": "Issued in error during testing."})
    assert revoked.status_code == 200
    body = client.get(f"/api/lms/certificates/verify/{certificate['verification_code']}").json()
    assert body["valid"] is False and "revoked" in body["reason"].lower()


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def test_analytics_are_computed_from_real_records(course):
    _, lesson_id = _add_lesson(course["id"])
    _publish(course["id"])
    client.post(f"/api/lms/courses/{course['id']}/enrol")
    client.post(f"/api/lms/lessons/{lesson_id}/complete", json={})

    detail = client.get(f"{ADMIN}/analytics/courses/{course['id']}").json()
    assert detail["totals"]["enrolments"] == 1
    assert detail["totals"]["completions"] == 1
    assert detail["totals"]["completion_rate"] == 100
    assert detail["lesson_funnel"][0]["completed_by"] == 1

    overall = client.get(f"{ADMIN}/analytics").json()
    assert overall["totals"]["published_courses"] >= 1
    # A metric with no data is null, not a misleading zero.
    assert "average_assessment_score" in overall["totals"]


# ---------------------------------------------------------------------------
# Import: archive safety
# ---------------------------------------------------------------------------

def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


LESSON_HTML = b"""<!doctype html><html><head><title>Claims basics</title></head><body>
<section class="slide"><h2>What is a claim?</h2>
  <p>A claim is a <strong>request for payment</strong>.</p>
  <img src="media/diagram.png" alt="Claims journey">
  <script>alert('xss')</script>
</section>
<section class="slide"><h2>Key takeaways</h2>
  <ul><li>Triage first</li><li>Record evidence</li></ul>
</section>
</body></html>"""

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
       b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
       b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")


def test_import_builds_structured_blocks_and_copies_media(course):
    payload = _zip_bytes({"index.html": LESSON_HTML, "media/diagram.png": PNG})
    response = client.post(
        f"{ADMIN}/courses/{course['id']}/import",
        files={"file": ("classroom.maic.zip", payload, "application/zip")})
    assert response.status_code == 201, response.text
    report = response.json()["report"]
    assert report["lessons"] == 2
    assert report["media_files"] == 1
    assert report["blocks"] >= 3

    detail = client.get(f"{ADMIN}/courses/{course['id']}").json()
    assert detail["status"] == "awaiting_review"
    assert detail["origin"] == "ai_generated"
    blocks = [b for m in detail["modules"] for l in m["lessons"]
              for b in client.get(f"/api/lms/lessons/{l['id']}").json()["lesson"]["blocks"]] \
        if detail["status"] == "published" else None

    with SessionLocal() as db:
        lesson_ids = [l.id for m in db.query(CourseModule).filter_by(course_id=course["id"])
                      for l in db.query(Lesson).filter_by(module_id=m.id)]
        all_blocks = db.query(ContentBlock).filter(
            ContentBlock.lesson_id.in_(lesson_ids)).all()
        kinds = {b.block_type for b in all_blocks}
        assert "rich_text" in kinds
        assert "image" in kinds
        assert "key_takeaways" in kinds
        # The script tag never reaches the database.
        assert all("alert('xss')" not in str(b.data) for b in all_blocks)
        assert all("<script" not in str(b.data) for b in all_blocks)
        # The image now points at a Minet asset, not the export path.
        image = next(b for b in all_blocks if b.block_type == "image")
        assert image.data["src"].startswith("/api/lms/assets/")
        assert image.asset_id is not None


def test_import_preserves_the_original_export(course):
    payload = _zip_bytes({"index.html": LESSON_HTML})
    response = client.post(f"{ADMIN}/courses/{course['id']}/import",
                           files={"file": ("export.zip", payload, "application/zip")})
    assert response.status_code == 201
    export = response.json()["export_asset"]
    assert export["kind"] == "export"
    with SessionLocal() as db:
        asset = db.get(MediaAsset, export["id"])
        assert asset.visibility == "private"


def test_import_refuses_a_path_traversal_entry(course):
    payload = _zip_bytes({"../../evil.html": b"<p>no</p>", "index.html": LESSON_HTML})
    response = client.post(f"{ADMIN}/courses/{course['id']}/import",
                           files={"file": ("export.zip", payload, "application/zip")})
    assert response.status_code == 201
    skipped = response.json()["report"]["skipped_files"]
    assert any("unsafe path" in s["reason"] for s in skipped)


def test_import_rejects_a_non_zip(course):
    response = client.post(f"{ADMIN}/courses/{course['id']}/import",
                           files={"file": ("notes.zip", b"this is not a zip", "application/zip")})
    assert response.status_code == 422
    assert "not a readable ZIP" in response.json()["detail"]["errors"]["file"]


def test_import_reports_unreferenced_media_rather_than_dropping_it(course):
    payload = _zip_bytes({"index.html": LESSON_HTML, "media/diagram.png": PNG,
                          "media/orphan.png": PNG})
    response = client.post(f"{ADMIN}/courses/{course['id']}/import",
                           files={"file": ("export.zip", payload, "application/zip")})
    assert response.status_code == 201
    report = response.json()["report"]
    assert any(u["kind"] == "unreferenced_media" for u in report["unsupported"])
    assert report["needs_review"] is True


# ---------------------------------------------------------------------------
# Unit tests: importer internals
# ---------------------------------------------------------------------------

def test_sanitizer_removes_scripts_and_event_handlers():
    from app.importer.sanitize import sanitize_html, strip_to_text
    dirty = ('<p onclick="steal()">Hello</p><script>evil()</script>'
             '<a href="javascript:evil()">x</a><img src=x onerror=evil()>')
    clean = sanitize_html(dirty)
    assert "<script" not in clean and "onclick" not in clean
    assert "onerror" not in clean and "javascript:" not in clean
    assert "Hello" in clean
    assert strip_to_text("<p>a</p><script>bad()</script><p>b</p>").strip() == "a\nb"


def test_html_extractor_splits_slides_and_finds_media():
    from app.importer.html_blocks import extract_lessons, media_references
    lessons = extract_lessons(LESSON_HTML.decode())
    assert [lsn.title for lsn in lessons] == ["What is a claim?", "Key takeaways"]
    assert media_references(lessons) == ["media/diagram.png"]
    kinds = [b.block_type for lsn in lessons for b in lsn.blocks]
    assert "key_takeaways" in kinds and "image" in kinds


def test_html_without_sections_is_preserved_as_a_reviewable_fallback():
    from app.importer.html_blocks import extract_lessons
    lessons = extract_lessons("<html><body>Just loose text.</body></html>")
    assert len(lessons) == 1
    block = lessons[0].blocks[0]
    assert block.block_type in ("rich_text", "html_fallback")
    assert "Just loose text." in str(block.data)


def test_archive_rejects_a_zip_bomb_ratio():
    from app.importer.archive import ClassroomArchive
    from app.importer.report import ImportReport
    import tempfile, os
    payload = _zip_bytes({"index.html": LESSON_HTML, "bomb.txt": b"0" * 5_000_000})
    handle, path = tempfile.mkstemp(suffix=".zip")
    os.close(handle)
    try:
        with open(path, "wb") as fh:
            fh.write(payload)
        report = ImportReport()
        with ClassroomArchive(path, report) as archive:
            names = [e.name for e in archive.entries]
        assert "index.html" in names
        assert "bomb.txt" not in names
        assert any("hostile" in s["reason"] for s in report.skipped_files)
    finally:
        os.unlink(path)


def test_storage_refuses_keys_that_escape_the_root():
    from app.storage import LocalStorage
    storage = LocalStorage()
    for key in ("../secrets.txt", "/etc/passwd", "a/../../b"):
        with pytest.raises(ValueError):
            storage.path(key)


# ---------------------------------------------------------------------------
# Unit tests: OpenMAIC adapter
# ---------------------------------------------------------------------------

def test_openmaic_job_parsing_handles_both_response_shapes():
    from app.integrations.openmaic import OpenMAICClient
    raw = {"jobId": "run-1", "runId": "run-1", "status": "running", "step": "generating_scenes",
           "progress": 42, "message": "Working", "done": False}
    bare = OpenMAICClient._to_job(raw)
    wrapped = OpenMAICClient._to_job({"success": True, "data": raw})
    assert bare.job_id == wrapped.job_id == "run-1"
    assert bare.status == "running" and bare.progress == 42
    assert bare.done is False

    finished = OpenMAICClient._to_job({"jobId": "run-2", "status": "succeeded", "done": True,
                                       "result": {"classroomId": "c-9", "url": "/classroom/c-9",
                                                  "scenesCount": 7}})
    assert finished.classroom_id == "c-9" and finished.scenes_count == 7


def test_openmaic_client_requires_configuration():
    from app.integrations.openmaic import OpenMAICClient, OpenMAICNotConfigured
    with pytest.raises(OpenMAICNotConfigured):
        OpenMAICClient(base_url="").get_job("anything")


def test_material_extension_gate_matches_openmaics_policy():
    from app.integrations.openmaic import material_extension_supported
    assert material_extension_supported("handbook.pdf")
    assert material_extension_supported("deck.pptx")
    assert not material_extension_supported("archive.zip")
    assert not material_extension_supported("notes.rtf")


def test_generation_is_refused_without_openmaic_configured(course):
    response = client.post(f"{ADMIN}/courses/{course['id']}/generate", json={
        "instructions": "Build a short course on claims triage from the handbook.",
        "material_ids": []})
    # No OPENMAIC_BASE_URL in the test environment: an honest 503, not a fake success.
    assert response.status_code == 503
    assert "OPENMAIC_BASE_URL" in response.json()["detail"]


def test_settings_reports_integration_capabilities_honestly():
    settings = client.get(f"{ADMIN}/settings").json()
    assert settings["capabilities"]["automatic_export_download"] is False
    assert settings["capabilities"]["structured_content_api"] == "unverified"
    assert any("browser" in note for note in settings["capabilities"]["notes"])


# ---------------------------------------------------------------------------
# Existing functionality is untouched
# ---------------------------------------------------------------------------

def test_original_learning_paths_still_work():
    detail = client.get("/api/learning/paths/1")
    assert detail.status_code == 200
    assert detail.json()["modules_total"] == 5
    assert client.get("/api/learning").json()["continue"] is not None


def test_learner_dashboard_endpoint_works_on_this_database(course):
    """Regression: `NULLS LAST` is not valid MariaDB/MySQL and made this a 500."""
    _, lesson_id = _add_lesson(course["id"])
    _publish(course["id"])
    client.post(f"/api/lms/courses/{course['id']}/enrol")          # last_accessed_at gets set
    other = client.post(f"{ADMIN}/courses", json={"title": "Never opened (test)"}).json()
    try:
        response = client.get("/api/lms/me/learning")
        assert response.status_code == 200, response.text
        body = response.json()
        assert {"in_progress", "completed", "not_started", "recommended",
                "certificates", "recent_results", "totals"} <= set(body)
        assert any(c["id"] == course["id"] for c in body["not_started"] + body["in_progress"])
    finally:
        _delete_course(other["id"])


def test_certificate_download_url_is_a_complete_path_that_serves_a_pdf(course):
    """Regression: the frontend once prefixed `/api` onto an already-prefixed URL."""
    _, lesson_id = _add_lesson(course["id"])
    _publish(course["id"])
    client.post(f"/api/lms/courses/{course['id']}/enrol")
    cert = client.post(f"/api/lms/lessons/{lesson_id}/complete", json={}).json()["certificate"]
    assert cert["download_url"].startswith("/api/lms/certificates/")   # use as-is, never re-prefix
    response = client.get(cert["download_url"])
    assert response.status_code == 200
    assert response.content[:5] == b"%PDF-"
    assert "attachment" in response.headers["content-disposition"]


def test_sanitizer_only_allows_minet_hosted_images():
    """Regression: external images (tracking pixels) must never survive into a lesson."""
    from app.importer.sanitize import sanitize_html
    html = ('<p>a</p><img src="https://tracker.example/p.gif">'
            '<img src="http://evil.example/x.png" alt="x"><img src="x"><img src="//cdn.example/y.png">'
            '<img src="/api/lms/assets/42" alt="ok"><img src="/api/lms/assets/42/../../etc">')
    clean = sanitize_html(html)
    assert clean.count("<img") == 1 and "/api/lms/assets/42" in clean and 'alt="ok"' in clean
    assert "tracker" not in clean and "evil" not in clean and "cdn.example" not in clean
