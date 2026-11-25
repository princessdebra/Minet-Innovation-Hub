from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..constants import LIBRARY_CATEGORIES
from ..db import get_db
from ..models import Horizon, ImpactMetric, LibraryItem, PortfolioStat

router = APIRouter(prefix="/api", tags=["knowledge"])


@router.get("/impact")
def impact(db: Session = Depends(get_db)):
    strip = [{"key": s.key, "label": s.label, "value": s.value}
             for s in db.scalars(select(PortfolioStat).order_by(PortfolioStat.sort_order))]
    horizons = []
    metrics_all = list(db.scalars(select(ImpactMetric).order_by(ImpactMetric.sort_order)))
    for h in db.scalars(select(Horizon).order_by(Horizon.sort_order)):
        ms = [m for m in metrics_all if m.horizon_id == h.id]
        horizons.append({"id": h.id, "name": h.name, "headline": h.description.rstrip("."),
                         "metrics": [{"id": m.id, "name": m.name, "status": m.status,
                                      "evidence_status": "Validated" if m.validated else "Evidence pending",
                                      "validated": m.validated} for m in ms]})
    total = len(metrics_all)
    validated = sum(1 for m in metrics_all if m.validated)
    with_evidence = sum(1 for m in metrics_all if (m.evidence or "").strip())
    owners = sum(1 for m in metrics_all if (m.benefits_owner or "").strip())
    periods = sum(1 for m in metrics_all if (m.measurement_period or "").strip())

    def state(n: int, none: str, label: str) -> str:
        return none if n == 0 else f"Provided for {n} of {total} {label}"

    return {
        "strip": strip,
        "horizons": horizons,
        "validation": {
            "evidence": state(with_evidence, "Pending", "metrics"),
            "benefits_owner": state(owners, "Not assigned", "metrics"),
            "measurement_period": state(periods, "Not set", "metrics"),
            "status": "VALIDATED" if validated == total and total else
                      ("PARTLY VALIDATED" if validated else "NOT VALIDATED"),
            "statement": ("No realised benefit is claimed in this illustrative view." if validated == 0
                          else f"{validated} of {total} metrics meet all three conditions."),
            "validated_count": validated, "metric_count": total,
        },
        "library": [{**c, "count": db.scalar(select(func.count()).select_from(LibraryItem)
                                             .where(LibraryItem.category == c["slug"]))}
                    for c in LIBRARY_CATEGORIES],
    }


@router.get("/library/{slug}")
def library(slug: str, db: Session = Depends(get_db)):
    category = next((c for c in LIBRARY_CATEGORIES if c["slug"] == slug), None)
    if not category:
        raise HTTPException(404, "Library section not found")
    items = db.scalars(select(LibraryItem).where(LibraryItem.category == slug).order_by(LibraryItem.sort_order))
    return {"category": category, "items": [{"id": i.id, "title": i.title, "kind": i.kind,
                                             "summary": i.summary} for i in items]}
