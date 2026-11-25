from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Challenge, Experiment, Idea, LearningPath
from ..security import get_current_user
from ..serializers import challenge_card, fmt_date, user_out
from ..services import path_state, plural, progress_map

router = APIRouter(prefix="/api", tags=["home"])


@router.get("/home")
def home(db: Session = Depends(get_db), user=Depends(get_current_user)):
    ideas = list(db.scalars(select(Idea).where(Idea.owner_id == user.id, Idea.is_duplicate.is_(False))
                            .order_by(Idea.id)))
    exps = list(db.scalars(select(Experiment).where(Experiment.owner_id == user.id).order_by(Experiment.id)))
    progress = progress_map(db, user)
    paths = list(db.scalars(select(LearningPath).order_by(LearningPath.sort_order)))

    in_progress = [(p, path_state(p, progress.get(p.id))) for p in paths]
    in_progress = [(p, s) for p, s in in_progress if s["status"] == "in_progress"]
    in_progress.sort(key=lambda x: -x[1]["percent"])
    lead = in_progress[0] if in_progress else None

    actions = [i.action_label for i in ideas if i.action_label]
    actions += [e.action_label for e in exps if e.action_label]
    actions += [p.action_label for p, _ in in_progress if p.action_label]

    dates = [e.next_decision_date for e in exps if e.next_decision_date]
    featured = db.scalar(select(Challenge).where(Challenge.is_featured.is_(True))) or \
        db.scalar(select(Challenge).order_by(Challenge.sort_order))
    challenge_count = db.scalar(select(func.count()).select_from(Challenge)
                                .where(Challenge.is_illustrative.is_(True)))
    return {
        "user": user_out(user),
        "tiles": {
            "ideas": {"count": len(ideas), "items": [{"title": i.title, "status": i.status} for i in ideas]},
            "experiments": {"count": len(exps),
                            "items": [{"title": e.title, "status": e.stage.name.upper()} for e in exps],
                            "next_review": fmt_date(min(dates)) if dates else None},
            "learning": {"percent": lead[1]["percent"] if lead else 0,
                         "title": lead[0].title if lead else "No path in progress",
                         "in_progress_text": f"{plural(len(in_progress), 'learning path')} in progress"},
            "next_actions": {"count": len(actions), "items": actions},
        },
        "featured_challenge": challenge_card(featured) if featured else None,
        "challenge_count": challenge_count,
    }
