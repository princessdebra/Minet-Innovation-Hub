from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..constants import HORIZON_CHOICES, MENTOR_AREAS, SOURCES
from ..db import get_db
from ..models import Horizon, InnovationType, Stage
from ..security import get_current_user, permissions_for
from ..serializers import user_out

router = APIRouter(prefix="/api", tags=["reference"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/me")
def me(user=Depends(get_current_user)):
    return {**user_out(user), "permissions": permissions_for(user)}


@router.get("/reference")
def reference(db: Session = Depends(get_db)):
    return {
        "horizons": [{"id": h.id, "name": h.name, "description": h.description,
                      "short_description": h.short_description}
                     for h in db.scalars(select(Horizon).order_by(Horizon.sort_order))],
        "innovation_types": [{"id": t.id, "name": t.name, "short_description": t.short_description}
                             for t in db.scalars(select(InnovationType).order_by(InnovationType.sort_order))],
        "stages": [{"id": s.id, "name": s.name, "description": s.description}
                   for s in db.scalars(select(Stage).order_by(Stage.sort_order))],
        "sources": SOURCES,
        "horizon_choices": HORIZON_CHOICES,
        "mentor_areas": MENTOR_AREAS,
    }
