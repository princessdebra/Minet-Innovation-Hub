from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..constants import HORIZON_CHOICES
from ..db import get_db
from ..models import Challenge, Experiment, Horizon, Idea, InnovationType, Stage
from ..security import get_current_user, require_permission
from ..serializers import experiment_card, experiment_detail, idea_card, idea_detail

router = APIRouter(prefix="/api", tags=["ideas and experiments"])


class IdeaIn(BaseModel):
    title: str = Field("", max_length=160)
    problem: str = Field("", max_length=4000)
    solution: str = Field("", max_length=4000)
    expected_value: str = Field("", max_length=2000)
    evidence: str = Field("", max_length=4000)
    horizon: Optional[str] = None  # Core, Adjacent, Transformational or "Not sure"
    type_ids: list[int] = []
    collaborators: str = Field("", max_length=300)
    challenge_id: Optional[int] = None
    submit: bool = False


def validate(p: IdeaIn, db: Session) -> dict[str, str]:
    errors: dict[str, str] = {}
    title = p.title.strip()
    if p.submit:
        if len(title) < 5:
            errors["title"] = "Add a short, clear title (at least 5 characters)."
        if len(p.problem.strip()) < 10:
            errors["problem"] = "Describe who experiences the problem and when."
        if len(p.solution.strip()) < 10:
            errors["solution"] = "Describe what could be done differently."
        if len(p.expected_value.strip()) < 3:
            errors["expected_value"] = "Say what could improve: customer, colleague, cost, revenue, risk or speed."
        if not p.horizon:
            errors["horizon"] = "Select one primary horizon, or choose Not sure."
        if not p.type_ids:
            errors["type_ids"] = "Select at least one innovation type."
    elif not title:
        errors["title"] = "Add a title so you can find this draft later."
    if p.horizon and p.horizon not in HORIZON_CHOICES:
        errors["horizon"] = "Choose one of the listed horizons."
    if p.type_ids:
        found = db.scalars(select(InnovationType.id).where(InnovationType.id.in_(p.type_ids))).all()
        if len(set(found)) != len(set(p.type_ids)):
            errors["type_ids"] = "One or more innovation types are not valid."
    if p.challenge_id and not db.get(Challenge, p.challenge_id):
        errors["challenge_id"] = "That challenge does not exist."
    return errors


def apply(idea: Idea, p: IdeaIn, db: Session) -> None:
    idea.title = p.title.strip()
    idea.problem, idea.solution = p.problem.strip(), p.solution.strip()
    idea.expected_value, idea.evidence = p.expected_value.strip(), p.evidence.strip()
    idea.collaborators = p.collaborators.strip() or None
    idea.challenge_id = p.challenge_id
    if p.horizon == "Not sure":
        idea.horizon_id, idea.horizon_unsure = None, True
    elif p.horizon:
        idea.horizon_id = db.scalar(select(Horizon.id).where(Horizon.name == p.horizon))
        idea.horizon_unsure = False
    else:
        idea.horizon_id, idea.horizon_unsure = None, False
    idea.types = list(db.scalars(select(InnovationType).where(InnovationType.id.in_(p.type_ids))
                                 .order_by(InnovationType.sort_order)))


def finalize(idea: Idea, previous_status: Optional[str]) -> None:
    now = datetime.now()
    if previous_status == "Needs clarification":
        idea.status, idea.next_text = "In review", "Clarification sent; back with the Innovation team"
    else:
        idea.status, idea.next_text = "Submitted", "Acknowledgement and initial triage by the Innovation team"
    idea.next_label = "Next action"
    idea.action_label = None
    idea.reference_id = idea.reference_id or f"IDEA-{now.year}-{idea.id:04d}"
    idea.submitted_at = idea.submitted_at or now


def _owned(db: Session, idea_id: int, user) -> Idea:
    idea = db.get(Idea, idea_id)
    if not idea or idea.owner_id != user.id:
        raise HTTPException(404, "Idea not found")
    return idea


@router.get("/workspace")
def workspace(db: Session = Depends(get_db), user=Depends(get_current_user)):
    ideas = db.scalars(select(Idea).where(Idea.owner_id == user.id, Idea.is_duplicate.is_(False))
                       .order_by(Idea.id))
    exps = db.scalars(select(Experiment).where(Experiment.owner_id == user.id).order_by(Experiment.id))
    return {"ideas": [idea_card(i) for i in ideas], "experiments": [experiment_card(e) for e in exps]}


@router.get("/ideas/{idea_id}")
def get_idea(idea_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return idea_detail(_owned(db, idea_id, user))


@router.post("/ideas", status_code=201)
def create_idea(payload: IdeaIn, db: Session = Depends(get_db), user=Depends(require_permission("idea:create"))):
    errors = validate(payload, db)
    if errors:
        raise HTTPException(422, {"errors": errors})
    source = db.scalar(select(Stage).where(Stage.name == "Source"))
    idea = Idea(owner_id=user.id, stage_id=source.id, status="Draft", next_label="Next action",
                next_text="Complete and submit your draft")
    apply(idea, payload, db)
    db.add(idea)
    db.flush()
    if payload.submit:
        finalize(idea, None)
    db.commit()
    return {"id": idea.id, "status": idea.status, "reference_id": idea.reference_id}


@router.put("/ideas/{idea_id}")
def update_idea(idea_id: int, payload: IdeaIn, db: Session = Depends(get_db),
                user=Depends(require_permission("idea:update"))):
    idea = _owned(db, idea_id, user)
    if idea.status not in ("Draft", "Needs clarification"):
        raise HTTPException(409, "This idea has been submitted and can no longer be edited here.")
    errors = validate(payload, db)
    if errors:
        raise HTTPException(422, {"errors": errors})
    previous = idea.status
    apply(idea, payload, db)
    if payload.submit:
        finalize(idea, previous)
    db.commit()
    return {"id": idea.id, "status": idea.status, "reference_id": idea.reference_id}


@router.delete("/ideas/{idea_id}", status_code=204)
def delete_idea(idea_id: int, db: Session = Depends(get_db), user=Depends(require_permission("idea:delete"))):
    idea = _owned(db, idea_id, user)
    if idea.status != "Draft":
        raise HTTPException(409, "Only drafts can be deleted.")
    db.delete(idea)
    db.commit()


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    exp = db.get(Experiment, experiment_id)
    if not exp or exp.owner_id != user.id:
        raise HTTPException(404, "Experiment not found")
    return experiment_detail(exp)
