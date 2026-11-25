"""Smoke tests against the real MySQL database. Run `python init_db.py --reset` first.

    pytest -q
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def get(path, **kw):
    r = client.get(path, **kw)
    assert r.status_code == 200, (path, r.status_code, r.text)
    return r.json()


def test_reference_and_me():
    ref = get("/api/reference")
    assert [h["name"] for h in ref["horizons"]] == ["Core", "Adjacent", "Transformational"]
    assert len(ref["innovation_types"]) == 10 and len(ref["stages"]) == 4
    me = get("/api/me")
    assert me["name"] == "Alex Mwangi" and "*" in me["permissions"]


def test_home_matches_wireframe():
    h = get("/api/home")["tiles"]
    assert h["ideas"]["count"] >= 2 and h["experiments"]["count"] == 2
    assert h["experiments"]["next_review"] == "18 Nov"
    assert h["learning"]["percent"] == 40 and h["next_actions"]["count"] == 3


def test_leaderboards():
    for tab in ("learning", "ideas"):
        lb = get(f"/api/leaderboard?tab={tab}")
        assert lb["me"]["rank"] == 8, tab
    top = get("/api/leaderboard?tab=learning&limit=3")["entries"]
    assert [e["name"] for e in top] == ["Wanjiku Otieno", "Brian Kamau", "Faith Njeri"]
    assert [e["value"] for e in top] == [6, 5, 4]
    assert get("/api/leaderboard?tab=learning")["me"]["summary"] == "Rank 8 \u00b7 1 completed path"


def test_challenge_filters():
    assert get("/api/challenges")["total"] == 5
    assert get("/api/challenges?horizon=Core")["total"] == 2
    assert get("/api/challenges?source=Partners&horizon=Adjacent")["total"] == 1
    assert get("/api/challenges?type=Process")["total"] == 2
    assert get("/api/challenges?search=claims")["total"] >= 1
    assert get("/api/challenges?search=zzzz")["total"] == 0
    assert get("/api/challenges/1")["title"] == "Improve claims experience"


def test_idea_validation_draft_submit_and_counts():
    bad = client.post("/api/ideas", json={"title": "x", "submit": True})
    assert bad.status_code == 422 and "problem" in bad.json()["detail"]["errors"]

    before = get("/api/home")["tiles"]["ideas"]["count"]
    draft = client.post("/api/ideas", json={"title": "Test draft idea"})
    assert draft.status_code == 201 and draft.json()["reference_id"] is None
    did = draft.json()["id"]

    payload = {"title": "Test draft idea", "problem": "Colleagues repeat the same step twice.",
               "solution": "Remove the repeated step.", "expected_value": "Faster work",
               "horizon": "Core", "type_ids": [4], "submit": True}
    done = client.put(f"/api/ideas/{did}", json=payload)
    assert done.status_code == 200 and done.json()["reference_id"].startswith("IDEA-2026-")
    assert get("/api/home")["tiles"]["ideas"]["count"] == before + 1
    ws = get("/api/workspace")
    assert any(i["id"] == did and i["status"] == "Submitted" for i in ws["ideas"])
    # submitted ideas are locked
    assert client.put(f"/api/ideas/{did}", json=payload).status_code == 409
    # ideas leaderboard counts it (Alex had 2, now 3)
    assert get("/api/leaderboard?tab=ideas")["me"]["value"] == 3
    # clean up so the dummy data stays as designed
    from app.db import SessionLocal
    from app.models import Idea
    with SessionLocal() as db:
        db.delete(db.get(Idea, did)); db.commit()


def test_learning_progress():
    detail = get("/api/learning/paths/1")
    assert detail["percent"] == 40 and len(detail["modules"]) == 5
    r = client.post("/api/learning/paths/1/complete-next")
    assert r.status_code == 200 and r.json()["percent"] == 60
    # restore
    from app.db import SessionLocal
    from app.models import UserPathProgress
    with SessionLocal() as db:
        db.get(UserPathProgress, (1, 1)).completed_modules = 2; db.commit()
    assert get("/api/learning")["continue"]["percent"] == 40


def test_impact_rule_and_library():
    imp = get("/api/impact")
    assert imp["validation"]["status"] == "NOT VALIDATED"
    assert all(not m["validated"] for h in imp["horizons"] for m in h["metrics"])
    assert [s["value"] for s in imp["strip"]] == [86, 12, 4, None]
    assert get("/api/library/playbooks")["items"]
    assert client.get("/api/library/nope").status_code == 404


def test_validated_property_needs_all_three():
    from app.models import ImpactMetric
    m = ImpactMetric(name="x", evidence="e", benefits_owner="o", measurement_period="")
    assert m.validated is False
    m.measurement_period = "Q1"
    assert m.validated is True


def test_search_and_mentor_and_community():
    assert any(r["type"] == "Challenge" for r in get("/api/search?q=claims")["results"])
    assert get("/api/search?q=a")["results"] == []
    created = client.post("/api/mentor-requests", json={"area": "Data", "message": "Hi"})
    assert created.status_code == 201
    from app.db import SessionLocal
    from app.models import MentorRequest
    with SessionLocal() as db:
        db.delete(db.get(MentorRequest, created.json()["id"])); db.commit()
    assert client.post("/api/mentor-requests", json={"area": "Nope"}).status_code == 422
    assert get("/api/community")["joined"] is False
    assert client.post("/api/community/join").json()["joined"] is True
    assert client.post("/api/community/leave").json()["joined"] is False
