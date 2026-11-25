from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..constants import MENTOR_AREAS
from ..db import get_db
from ..models import (CommunityMember, Experiment, InnovationType, LearningPath, MentorRequest,
                      UserPathProgress)
from ..security import get_current_user, require_permission
from ..services import path_card, path_state, progress_map

router = APIRouter(prefix="/api", tags=["learning"])


def _community(db: Session, user) -> dict:
    joined = db.get(CommunityMember, user.id) is not None
    count = db.scalar(select(func.count()).select_from(CommunityMember))
    return {"joined": joined, "member_count": count}


@router.get("/learning")
def learning(db: Session = Depends(get_db), user=Depends(get_current_user)):
    progress = progress_map(db, user)
    paths = list(db.scalars(select(LearningPath).order_by(LearningPath.sort_order)))
    cards = [path_card(p, progress.get(p.id)) for p in paths]
    active = [c for c in cards if c["status"] == "in_progress"]
    active.sort(key=lambda c: -c["percent"])
    return {
        "continue": active[0] if active else None,
        "recommended": [c for c in cards if c["section"] == "recommended"],
        "next": [c for c in cards if c["section"] == "next"],
        "types": [{"id": t.id, "name": t.name, "short_description": t.short_description}
                  for t in db.scalars(select(InnovationType).order_by(InnovationType.sort_order))],
        "mentor_areas": MENTOR_AREAS,
        "community": _community(db, user),
    }


def _detail(db: Session, path: LearningPath, user) -> dict:
    prog = progress_map(db, user).get(path.id)
    card = path_card(path, prog)
    done = card["modules_done"]
    exp = db.get(Experiment, path.linked_experiment_id) if path.linked_experiment_id else None
    return {
        **card,
        "linked_experiment": {"id": exp.id, "title": exp.title} if exp else None,
        "modules": [{"id": m.id, "title": m.title, "summary": m.summary, "minutes": m.minutes,
                     "done": idx < done} for idx, m in enumerate(path.modules)],
    }


@router.get("/learning/paths/{path_id}")
def get_path(path_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    path = db.get(LearningPath, path_id)
    if not path:
        raise HTTPException(404, "Learning path not found")
    return _detail(db, path, user)


@router.post("/learning/paths/{path_id}/complete-next")
def complete_next(path_id: int, db: Session = Depends(get_db),
                  user=Depends(require_permission("learning:progress"))):
    path = db.get(LearningPath, path_id)
    if not path:
        raise HTTPException(404, "Learning path not found")
    prog = db.get(UserPathProgress, (user.id, path.id))
    if not prog:
        prog = UserPathProgress(user_id=user.id, path_id=path.id, completed_modules=0)
        db.add(prog)
    total = len(path.modules)
    if prog.completed_modules < total:
        prog.completed_modules += 1
    if prog.completed_modules >= total and not prog.completed_at:
        prog.completed_at = datetime.now()
    db.commit()
    return _detail(db, path, user)


@router.post("/learning/paths/{path_id}/reset")
def reset_path(path_id: int, db: Session = Depends(get_db),
               user=Depends(require_permission("learning:progress"))):
    path = db.get(LearningPath, path_id)
    if not path:
        raise HTTPException(404, "Learning path not found")
    prog = db.get(UserPathProgress, (user.id, path.id))
    if prog:
        db.delete(prog)
        db.commit()
    return _detail(db, path, user)


class MentorIn(BaseModel):
    area: str
    message: Optional[str] = Field("", max_length=1000)


@router.post("/mentor-requests", status_code=201)
def request_mentor(payload: MentorIn, db: Session = Depends(get_db),
                   user=Depends(require_permission("mentor:request"))):
    if payload.area not in MENTOR_AREAS:
        raise HTTPException(422, {"errors": {"area": "Choose one of the listed areas."}})
    req = MentorRequest(user_id=user.id, area=payload.area, message=(payload.message or "").strip() or None)
    db.add(req)
    db.commit()
    return {"id": req.id, "status": req.status, "area": req.area}


@router.get("/mentor-requests")
def my_mentor_requests(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.scalars(select(MentorRequest).where(MentorRequest.user_id == user.id)
                      .order_by(MentorRequest.id.desc()))
    return [{"id": r.id, "area": r.area, "status": r.status, "created_at": r.created_at.isoformat()}
            for r in rows]


@router.get("/community")
def community(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _community(db, user)


@router.post("/community/join")
def join_community(db: Session = Depends(get_db), user=Depends(require_permission("community:join"))):
    if not db.get(CommunityMember, user.id):
        db.add(CommunityMember(user_id=user.id))
        db.commit()
    return _community(db, user)


@router.post("/community/leave")
def leave_community(db: Session = Depends(get_db), user=Depends(require_permission("community:join"))):
    member = db.get(CommunityMember, user.id)
    if member:
        db.delete(member)
        db.commit()
    return _community(db, user)
