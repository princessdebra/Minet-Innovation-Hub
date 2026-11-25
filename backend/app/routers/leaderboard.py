from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..security import get_current_user
from ..services import leaderboard_rows, plural

router = APIRouter(prefix="/api", tags=["leaderboard"])


@router.get("/leaderboard")
def leaderboard(tab: str = Query("learning", pattern="^(learning|ideas)$"),
                limit: int | None = Query(None, ge=1, le=100),
                db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = leaderboard_rows(db, tab)
    me = next(r for r in rows if r["user_id"] == user.id)
    n = me["value"]
    count_text = plural(n, "completed path") if tab == "learning" else \
        f"{n} {'idea' if n == 1 else 'ideas'} submitted"
    summary = f"Rank {me['rank']} \u00b7 {count_text}"
    entries = [{**r, "is_me": r["user_id"] == user.id} for r in (rows[:limit] if limit else rows)]
    return {
        "tab": tab, "period": "This quarter",
        "column_label": "Completed learning paths" if tab == "learning" else "Ideas submitted",
        "entries": entries,
        "me": {"rank": me["rank"], "name": me["name"], "initials": me["initials"],
               "value": me["value"], "summary": summary},
        "total": len(rows),
        "note": ("Learning counts completed paths, not current-path progress. Ideas exclude drafts and "
                 "duplicates; submission volume is not quality or business impact."),
    }
