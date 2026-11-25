from datetime import date
from typing import Optional

from .models import Challenge, Experiment, Idea, User


def type_names(types) -> list[str]:
    """Wireframe order, e.g. 'Service / Process' and 'Channel / Network'."""
    return [t.name for t in sorted(types, key=lambda t: -t.sort_order)]


def fmt_date(d: Optional[date]) -> Optional[str]:
    return f"{d.day} {d:%b}" if d else None


def user_out(u: User) -> dict:
    return {"id": u.id, "name": u.name, "initials": u.initials, "role": u.role}


def challenge_card(c: Challenge) -> dict:
    return {
        "id": c.id, "title": c.title, "how_might_we": c.how_might_we, "source": c.source,
        "horizon": c.horizon.name, "types": type_names(c.types), "sponsor": c.sponsor,
        "status": c.status, "is_illustrative": c.is_illustrative, "is_featured": c.is_featured,
    }


def idea_horizon(i: Idea) -> Optional[str]:
    if i.horizon:
        return i.horizon.name
    return "Not sure" if i.horizon_unsure else None


def idea_card(i: Idea) -> dict:
    return {
        "kind": "idea", "key": f"idea-{i.id}", "id": i.id, "title": i.title, "stage": i.stage.name,
        "status": i.status, "owner": i.owner.name, "horizon": idea_horizon(i),
        "types": type_names(i.types), "next_label": i.next_label, "next_text": i.next_text,
        "reference_id": i.reference_id, "is_draft": i.status == "Draft",
    }


def experiment_card(e: Experiment) -> dict:
    return {
        "kind": "experiment", "key": f"experiment-{e.id}", "id": e.id, "title": e.title,
        "stage": e.stage.name, "status": e.status, "owner": e.owner.name, "horizon": e.horizon.name,
        "types": type_names(e.types), "next_label": e.next_label, "next_text": e.next_text,
        "reference_id": None, "is_draft": False,
    }


def _tag(owner: User, illustrative: bool, reference: Optional[str], noun: str) -> str:
    first = owner.name.split()[0].upper()
    if illustrative:
        return f"{first}'S INITIATIVE \u2022 ILLUSTRATIVE DATA"
    return f"{first}'S {noun}" + (f" \u2022 {reference}" if reference else "")


def idea_detail(i: Idea) -> dict:
    lines = [f"{label}: {text}" for label, text in (
        ("Problem", i.problem), ("Proposed solution", i.solution),
        ("Expected value", i.expected_value), ("Evidence", i.evidence)) if text and text.strip()]
    return {
        **idea_card(i),
        "tag": _tag(i.owner, i.is_illustrative, i.reference_id, "IDEA"),
        "sponsor": i.sponsor, "evidence_lines": lines or ["No evidence added yet."],
        "resource_decision": None,
        "review_notes": i.review_notes or {
            "Strategic alignment": "To be assessed by the Innovation team",
            "Customer value": "To be assessed by the Innovation team",
            "Feasibility": "To be assessed by the Innovation team",
            "Risk and compliance": "To be assessed by the Innovation team",
            "Potential impact": "To be assessed by the Innovation team; evidence still needed",
        },
        "problem": i.problem, "solution": i.solution, "expected_value": i.expected_value,
        "evidence": i.evidence, "collaborators": i.collaborators,
        "type_ids": [t.id for t in i.types], "horizon_unsure": i.horizon_unsure,
        "challenge": {"id": i.challenge.id, "title": i.challenge.title} if i.challenge else None,
        "can_edit": i.status in ("Draft", "Needs clarification"),
    }


def experiment_detail(e: Experiment) -> dict:
    return {
        **experiment_card(e),
        "tag": _tag(e.owner, e.is_illustrative, None, "EXPERIMENT"),
        "sponsor": e.sponsor,
        "evidence_lines": [l for l in (e.evidence_learning or "").split("\n") if l.strip()]
                          or ["No evidence recorded yet."],
        "resource_decision": e.resource_decision,
        "review_notes": e.review_notes or {},
        "next_decision_date": fmt_date(e.next_decision_date),
        "challenge": None, "can_edit": False,
    }
