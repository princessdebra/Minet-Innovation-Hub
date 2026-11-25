from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Challenge, Horizon, Idea, InnovationType
from ..security import get_current_user
from ..serializers import challenge_card, idea_card

router = APIRouter(prefix="/api", tags=["challenges"])


@router.get("/challenges")
def list_challenges(search: Optional[str] = None, source: list[str] = Query(default=[]),
                    horizon: list[str] = Query(default=[]), type: list[str] = Query(default=[]),
                    db: Session = Depends(get_db)):
    q = select(Challenge).join(Horizon, Challenge.horizon_id == Horizon.id).order_by(Challenge.sort_order)
    if source:
        q = q.where(Challenge.source.in_(source))
    if horizon:
        q = q.where(Horizon.name.in_(horizon))
    if type:
        q = q.where(Challenge.types.any(InnovationType.name.in_(type)))
    if search and search.strip():
        like = f"%{search.strip()}%"
        q = q.where(or_(Challenge.title.ilike(like), Challenge.how_might_we.ilike(like),
                        Challenge.background.ilike(like), Challenge.sponsor.ilike(like),
                        Challenge.source.ilike(like), Horizon.name.ilike(like),
                        Challenge.types.any(InnovationType.name.ilike(like))))
    items = [challenge_card(c) for c in db.scalars(q)]
    return {"items": items, "total": len(items)}


@router.get("/challenges/{challenge_id}")
def get_challenge(challenge_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = db.get(Challenge, challenge_id)
    if not c:
        raise HTTPException(404, "Challenge not found")
    mine = list(db.scalars(select(Idea).where(Idea.challenge_id == c.id, Idea.owner_id == user.id)
                           .order_by(Idea.id)))
    others = db.scalar(select(func.count()).select_from(Idea).where(
        Idea.challenge_id == c.id, Idea.owner_id != user.id, Idea.status != "Draft"))
    return {**challenge_card(c), "background": c.background, "success_looks_like": c.success_looks_like,
            "my_ideas": [idea_card(i) for i in mine], "colleague_idea_count": others}
