"""HTTP STUB tests: Minet's real client and worker against a local server.

The stub implements only routes verified in OpenMAIC's source:

    POST /api/materials                      raw bytes + x-material-filename
    POST /api/generate-classroom             {requirement, materialIds}
    GET  /api/generate-classroom/{jobId}     job view
    GET  /api/persistence/documents/{id}     the MaicDocument (raw body)
    GET  /api/persistence/assets/{id}/content  asset bytes
    POST /api/access-code/verify             {"code"} -> Set-Cookie openmaic_access
    middleware: when ACCESS_CODE is set, /api/* needs the openmaic_access cookie

It proves Minet's side. It does NOT prove a real OpenMAIC behaves this way; the
unverified items are listed in docs/openmaic-source-findings.md and covered by
tests/test_live_openmaic.py.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import config
from app.db import SessionLocal
from app.integrations import openmaic
from app.jobs import tasks
from app.lms_models import ContentBlock, CourseModule, GenerationJob, Lesson
from app.main import app
from app.storage import get_storage
from tests import maic_fixtures as fx
from tests.test_lms import _delete_course

client = TestClient(app)
ADMIN = "/api/lms/admin"
ACCESS_TOKEN = "signed-token-123"
STATE: dict = {}


class StubOpenMAIC(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, status, payload, content_type="application/json", extra=None):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _gate(self) -> bool:
        """middleware.ts: with ACCESS_CODE set, /api/* needs the cookie."""
        STATE.setdefault("seen", []).append(
            {"path": self.path, "x-access-code": self.headers.get("x-access-code"),
             "cookie": self.headers.get("cookie")})
        if not STATE.get("access_code"):
            return True
        if self.path.startswith("/api/access-code/") or self.path == "/api/health":
            return True
        if f"openmaic_access={ACCESS_TOKEN}" in (self.headers.get("cookie") or ""):
            return True
        self._send(401, {"success": False, "errorCode": "INVALID_REQUEST",
                         "error": "Access code required"})
        return False

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self.path == "/api/access-code/verify":
            STATE["verify_calls"] = STATE.get("verify_calls", 0) + 1
            if json.loads(raw or b"{}").get("code") != STATE.get("access_code"):
                return self._send(401, {"success": False, "errorCode": "INVALID_REQUEST",
                                        "error": "Invalid access code"})
            return self._send(200, {"success": True, "data": {"valid": True}},
                              extra={"Set-Cookie": f"openmaic_access={ACCESS_TOKEN}; Path=/"})
        if not self._gate():
            return
        if self.path == "/api/materials":
            STATE.setdefault("materials", []).append(self.headers.get("x-material-filename"))
            return self._send(201, {"materialId": f"mat-{len(STATE['materials'])}",
                                    "originalName": "x", "bytes": len(raw), "mime": "application/pdf",
                                    "mediaKind": "document", "extraction": "queued"})
        if self.path == "/api/generate-classroom":
            body = json.loads(raw or b"{}")
            STATE["requirement"], STATE["polls"] = body.get("requirement"), 0
            return self._send(202, {"success": True, "data": {
                "jobId": "run-1", "runId": "run-1", "status": "queued", "step": "queued",
                "progress": 0, "done": False}})
        self._send(404, {"error": {"code": "NOT_FOUND", "message": "no route"}})

    def do_GET(self):
        if not self._gate():
            return
        if self.path.startswith("/api/generate-classroom/"):
            STATE["polls"] = STATE.get("polls", 0) + 1
            if STATE["polls"] < 2:
                return self._send(200, {"success": True, "data": {
                    "jobId": "run-1", "status": "running", "step": "generating_scenes",
                    "progress": 45, "done": False}})
            return self._send(200, {"success": True, "data": {
                "jobId": "run-1", "status": "succeeded", "step": "completed", "progress": 100,
                "done": True, "result": {"classroomId": STATE.get("stage_id", "stage-abc123"),
                                         "url": "/classroom/x", "scenesCount": 5}}})
        if self.path.startswith("/api/persistence/documents/"):
            if STATE.get("no_document"):
                return self._send(404, {"error": {"code": "DOCUMENT_NOT_FOUND", "message": "x"}})
            return self._send(200, STATE.get("document") or fx.document())
        if self.path.startswith("/api/persistence/assets/") and self.path.endswith("/content"):
            asset_id = self.path.split("/")[4]
            STATE.setdefault("asset_calls", []).append(asset_id)
            payload = fx.ASSETS.get(asset_id)
            if payload is None:
                return self._send(404, {"error": {"code": "ASSET_NOT_FOUND", "message": "x"}})
            return self._send(200, payload, content_type="application/octet-stream",
                              extra={"X-Asset-Revision": "1"})
        self._send(404, {"error": {"code": "ROUTE_NOT_FOUND", "message": "no route"}})


@pytest.fixture(scope="module")
def stub_server():
    server = HTTPServer(("127.0.0.1", 0), StubOpenMAIC)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    original = (config.OPENMAIC_BASE_URL, config.OPENMAIC_COOKIE, config.OPENMAIC_ACCESS_CODE)
    config.OPENMAIC_BASE_URL = f"http://127.0.0.1:{server.server_address[1]}"
    config.OPENMAIC_COOKIE = config.OPENMAIC_ACCESS_CODE = ""
    yield config.OPENMAIC_BASE_URL
    config.OPENMAIC_BASE_URL, config.OPENMAIC_COOKIE, config.OPENMAIC_ACCESS_CODE = original
    server.shutdown()
    server.server_close()


@pytest.fixture(autouse=True)
def reset(stub_server):
    STATE.clear()
    openmaic._ACCESS_TOKENS.clear()
    config.OPENMAIC_ACCESS_CODE = ""
    yield
    config.OPENMAIC_ACCESS_CODE = ""


@pytest.fixture
def course():
    response = client.post(f"{ADMIN}/courses", json={
        "title": "OpenMAIC generation (integration test)", "summary": "Created by a test.",
        "objectives": ["Understand triage"], "target_audience": "Claims team"})
    assert response.status_code == 201
    data = response.json()
    yield data
    _delete_course(data["id"])
    get_storage().delete_prefix(f"courses/{data['id']}")


def _queue(course_id: int, instructions="Build a short claims triage course.") -> int:
    queued = client.post(f"{ADMIN}/courses/{course_id}/generate",
                         json={"instructions": instructions, "material_ids": []})
    assert queued.status_code == 202, queued.text
    return queued.json()["id"]


def _drive(job_id: int, steps: int = 3) -> GenerationJob:
    with SessionLocal() as db:
        job = db.get(GenerationJob, job_id)
        for _ in range(steps):
            job.next_poll_at = None
            db.commit()
            tasks.advance(db, job)
            if job.status in ("imported", "failed") or job.step == "awaiting_export":
                break
        db.refresh(job)
        db.expunge(job)
        return job


def test_http_full_generation_downloads_the_document_and_every_asset(course):
    material = client.post(
        f"{ADMIN}/courses/{course['id']}/materials",
        files={"file": ("handbook.pdf", b"%PDF-1.4 handbook", "application/pdf")},
        data={"sensitivity": "internal"}).json()
    queued = client.post(f"{ADMIN}/courses/{course['id']}/generate", json={
        "instructions": "Build a short course on claims triage.",
        "material_ids": [material["id"]]})
    assert queued.status_code == 202
    job = _drive(queued.json()["id"])

    assert job.status == "imported", job.last_error
    assert STATE["materials"] == ["handbook.pdf"]
    assert "Claims team" in STATE["requirement"]
    # every distinct downloadable asset was fetched through the verified route, once
    fetched = STATE["asset_calls"]
    assert sorted(set(fetched)) == sorted({fx.IMG, fx.VID, fx.AUD, fx.AUD2, fx.MISSING})
    assert fetched.count(fx.IMG) == 1

    report = job.import_report
    assert (report["lessons"], report["questions"]) == (5, 3)
    assert report["needs_review"] is True                 # the missing asset, interactive, PBL
    with SessionLocal() as db:
        assert db.get(type(job), job.id).status == "imported"
        titles = {l.title for m in db.scalars(select(CourseModule).where(
            CourseModule.course_id == course["id"])) for l in db.scalars(
                select(Lesson).where(Lesson.module_id == m.id))}
        assert "Why triage matters" in titles and "Claims simulator" in titles
        blocks = db.scalars(select(ContentBlock).join(Lesson).join(CourseModule).where(
            CourseModule.course_id == course["id"])).all()
        assert not any("ast_" in json.dumps(b.data) for b in blocks if not b.data.get("broken_media"))
    assert client.get(f"{ADMIN}/courses/{course['id']}").json()["status"] == "awaiting_review"


def test_http_single_user_mode_sends_no_credentials_at_all(course):
    job = _drive(_queue(course["id"]))
    assert job.status == "imported", job.last_error
    assert all(r["cookie"] is None and r["x-access-code"] is None for r in STATE["seen"])


def test_http_access_code_is_exchanged_for_the_cookie_never_a_header(course):
    STATE["access_code"] = "secret-code"
    config.OPENMAIC_ACCESS_CODE = "secret-code"
    job = _drive(_queue(course["id"]))
    assert job.status == "imported", job.last_error
    gated = [r for r in STATE["seen"] if not r["path"].startswith("/api/access-code/")]
    assert gated and all(f"openmaic_access={ACCESS_TOKEN}" in r["cookie"] for r in gated)
    assert all(r["x-access-code"] is None for r in STATE["seen"])
    assert STATE["verify_calls"] == 1                      # exchanged once, then reused


def test_http_a_wrong_access_code_fails_the_job_clearly(course):
    STATE["access_code"] = "right"
    config.OPENMAIC_ACCESS_CODE = "wrong"
    job = _drive(_queue(course["id"]))
    assert job.status == "failed"
    assert "OPENMAIC_ACCESS_CODE" in job.last_error


def test_http_missing_access_code_is_reported_not_swallowed(course):
    STATE["access_code"] = "right"            # gate on, but Minet has no code configured
    job = _drive(_queue(course["id"]))
    assert job.status == "failed" and "credentials" in job.last_error.lower()


def test_http_a_missing_document_falls_back_to_the_manual_export(course):
    STATE["no_document"] = True
    job = _drive(_queue(course["id"]))
    assert job.status == "generated" and job.step == "awaiting_export"
    assert "upload the export" in job.message
    assert client.get(f"{ADMIN}/courses/{course['id']}").json()["status"] == "awaiting_review"


def test_http_an_unrecognised_document_shape_falls_back_without_losing_the_job(course):
    STATE["document"] = {"something": "else"}
    job = _drive(_queue(course["id"]))
    assert job.status == "generated" and job.step == "awaiting_export"
    assert "not recognised" in job.import_report["warnings"][0]


def test_http_a_failed_asset_does_not_abort_the_import(course):
    job = _drive(_queue(course["id"]))
    assert job.status == "imported"
    kinds = {u["kind"] for u in job.import_report["unsupported"]}
    assert "missing_media" in kinds                      # ast_gone... returned 404
    assert client.post(f"{ADMIN}/courses/{course['id']}/publish",
                       json={"acknowledged_ai_review": True}).status_code == 422


def test_http_a_job_that_finished_before_is_not_imported_twice(course):
    first = _drive(_queue(course["id"]))
    assert first.status == "imported"
    second = _drive(_queue(course["id"], "A different brief for the same classroom."))
    assert second.status == "imported"
    assert second.import_report["already_imported"] is True
    with SessionLocal() as db:
        assert db.scalar(select(CourseModule).where(CourseModule.course_id == course["id"])
                         .limit(1)) is not None
        assert len(db.scalars(select(CourseModule).where(
            CourseModule.course_id == course["id"])).all()) == 1


def test_http_duplicate_and_confidential_guards_still_hold(course):
    payload = {"instructions": "Exactly the same instructions for the duplicate check.",
               "material_ids": []}
    first = client.post(f"{ADMIN}/courses/{course['id']}/generate", json=payload)
    assert first.status_code == 202
    assert client.post(f"{ADMIN}/courses/{course['id']}/generate", json=payload).status_code == 409
    secret = client.post(f"{ADMIN}/courses/{course['id']}/materials",
                         files={"file": ("schedule.pdf", b"%PDF-1.4 x", "application/pdf")},
                         data={"sensitivity": "confidential"}).json()
    blocked = client.post(f"{ADMIN}/courses/{course['id']}/generate", json={
        "instructions": "Summarise the attached client schedule into a course.",
        "material_ids": [secret["id"]]})
    assert blocked.status_code == 422 and "confidential" in str(blocked.json())
    assert not STATE.get("materials")                  # nothing reached OpenMAIC


def test_http_asset_and_document_ids_are_validated_before_any_request():
    client_ = openmaic.OpenMAICClient(base_url="http://127.0.0.1:1")
    for bad in ("../../etc/passwd", "ast_", "gen_img_1", "http://evil/x", ""):
        with pytest.raises(openmaic.OpenMAICError):
            client_.fetch_asset(bad)
    with pytest.raises(openmaic.OpenMAICError):
        client_.fetch_classroom_document("../../admin")
