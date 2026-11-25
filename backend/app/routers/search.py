from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Challenge, Experiment, Idea, LearningPath, LibraryItem
from ..security import get_current_user

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
def search(q: str = Query("", max_length=80), db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = q.strip()
    if len(q) < 2:
        return {"results": []}
    like = f"%{q}%"
    out = []
    for c in db.scalars(select(Challenge).where(or_(Challenge.title.ilike(like), Challenge.how_might_we.ilike(like)))
                        .order_by(Challenge.sort_order).limit(3)):
        out.append({"type": "Challenge", "title": c.title, "subtitle": c.horizon.name, "path": f"/explore/{c.id}"})
    for i in db.scalars(select(Idea).where(Idea.owner_id == user.id, Idea.is_duplicate.is_(False),
                                           or_(Idea.title.ilike(like), Idea.problem.ilike(like))).limit(3)):
        path = f"/ideas/new?draft={i.id}" if i.status == "Draft" else f"/workspace?record=idea-{i.id}"
        out.append({"type": "Idea", "title": i.title, "subtitle": i.status, "path": path})
    for e in db.scalars(select(Experiment).where(Experiment.owner_id == user.id, Experiment.title.ilike(like)).limit(3)):
        out.append({"type": "Experiment", "title": e.title, "subtitle": e.status,
                    "path": f"/workspace?record=experiment-{e.id}"})
    for p in db.scalars(select(LearningPath).where(or_(LearningPath.title.ilike(like),
                                                       LearningPath.description.ilike(like))).limit(3)):
        out.append({"type": "Learning", "title": p.title, "subtitle": "Learning path", "path": f"/learn/paths/{p.id}"})
    for item in db.scalars(select(LibraryItem).where(or_(LibraryItem.title.ilike(like),
                                                         LibraryItem.summary.ilike(like))).limit(3)):
        out.append({"type": "Library", "title": item.title, "subtitle": item.kind,
                    "path": f"/knowledge/library/{item.category}"})
    return {"results": out[:12]}
