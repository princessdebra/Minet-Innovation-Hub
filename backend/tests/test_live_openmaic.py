"""LIVE tests: these need a running OpenMAIC and are skipped otherwise.

Everything here is still UNVERIFIED against a real instance. Run them against an
OpenMAIC started with OWNER_SINGLE_USER=true, ACCESS_CODE unset, on a private
network. They spend AI credits only in `test_live_generation`, which is opt-in.

    set OPENMAIC_LIVE_URL=http://localhost:3000
    pytest tests/test_live_openmaic.py -q
    set OPENMAIC_LIVE_GENERATE=1       (opt in to one real, billable generation)
"""
from __future__ import annotations

import os

import pytest

from app.integrations.openmaic import OpenMAICClient

LIVE_URL = os.getenv("OPENMAIC_LIVE_URL")
live = pytest.mark.skipif(not LIVE_URL, reason="set OPENMAIC_LIVE_URL to run live tests")


def _client() -> OpenMAICClient:
    return OpenMAICClient(base_url=LIVE_URL, cookie="", access_code="")


@live
def test_live_health_route_responds():
    assert _client().health()["reachable"] is True


@live
def test_live_documents_list_works_with_no_cookie_in_single_user_mode():
    """Settles: do cookie-less persistence reads work, and what is the real shape?"""
    payload = _client()._request("GET", "/api/persistence/documents", headers={"accept": "application/json"})
    assert isinstance(payload, list)          # DocumentSummary[] per the storage contract


@live
def test_live_an_existing_document_matches_the_shape_the_mapper_expects():
    from app.importer.maic import extract_document
    from app.importer.report import ImportReport
    client = _client()
    summaries = client._request("GET", "/api/persistence/documents", headers={"accept": "application/json"})
    if not summaries:
        pytest.skip("No documents on this OpenMAIC yet; generate one first.")
    document = client.fetch_classroom_document(summaries[0]["id"])
    extract_document(document, ImportReport())      # must not raise MaicFormatError


@live
def test_live_every_asset_in_a_document_is_downloadable():
    from app.importer.maic import extract_document
    from app.importer.report import ImportReport
    client = _client()
    summaries = client._request("GET", "/api/persistence/documents", headers={"accept": "application/json"})
    if not summaries:
        pytest.skip("No documents on this OpenMAIC yet; generate one first.")
    course = extract_document(client.fetch_classroom_document(summaries[0]["id"]), ImportReport())
    refs = {b.media_ref for s in course.scenes for b in s.blocks
            if b.media_ref and b.media_ref.startswith("ast_")}
    for ref in refs:
        payload, _ = client.fetch_asset(ref)
        assert payload


@live
@pytest.mark.skipif(not os.getenv("OPENMAIC_LIVE_GENERATE"),
                    reason="spends AI credits; set OPENMAIC_LIVE_GENERATE=1 to opt in")
def test_live_generation_end_to_end():
    client = _client()
    job = client.start_generation(requirement="A two-slide primer on insurance claims triage.")
    assert job.job_id
