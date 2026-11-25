"""Shared logic used by several routers."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Idea, LearningPath, User, UserPathProgress


def progress_map(db: Session, user: User) -> dict[int, UserPathProgress]:
    rows = db.scalars(select(UserPathProgress).where(UserPathProgress.user_id == user.id))
    return {p.path_id: p for p in rows}


def path_state(path: LearningPath, prog: UserPathProgress | None) -> dict:
    total = len(path.modules) or 1
    done = min(prog.completed_modules, total) if prog else 0
    completed = bool(prog and prog.completed_at)
    percent = 100 if completed else round(100 * done / total)
    status = "completed" if completed else ("in_progress" if done > 0 else "not_started")
    return {"percent": percent, "status": status, "done": done, "total": total}


def path_card(path: LearningPath, prog: UserPathProgress | None) -> dict:
    s = path_state(path, prog)
    base = path.footer_label or ""
    if s["status"] == "in_progress":
        footer, cta, badge = f"{s['percent']}% complete \u2022 {base}", "Continue path", f"{s['percent']}%"
    elif s["status"] == "completed":
        footer, cta, badge = f"Completed \u2022 {base}", "Review path", "DONE"
    else:
        footer, cta, badge = base, path.cta_label or "Start path", path.badge or "PATH"
    return {
        "id": path.id, "title": path.title, "description": path.description, "section": path.section,
        "badge": badge, "footer": footer, "cta": cta, "percent": s["percent"], "status": s["status"],
        "modules_done": s["done"], "modules_total": s["total"], "recommended_for": path.recommended_for,
    }


def leaderboard_rows(db: Session, tab: str) -> list[dict]:
    completed = dict(db.execute(
        select(UserPathProgress.user_id, func.count())
        .where(UserPathProgress.completed_at.is_not(None))
        .group_by(UserPathProgress.user_id)).all())
    ideas = dict(db.execute(
        select(Idea.owner_id, func.count())
        .where(Idea.status != "Draft", Idea.is_duplicate.is_(False))
        .group_by(Idea.owner_id)).all())
    rows = [{"user_id": u.id, "name": u.name, "initials": u.initials,
             "completed_paths": completed.get(u.id, 0), "ideas_submitted": ideas.get(u.id, 0)}
            for u in db.scalars(select(User))]
    key = "completed_paths" if tab == "learning" else "ideas_submitted"
    rows.sort(key=lambda r: (-r[key], r["name"]))
    for rank, r in enumerate(rows, 1):
        r["rank"], r["value"] = rank, r[key]
    return rows


def plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")
