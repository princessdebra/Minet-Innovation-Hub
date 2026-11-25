"""Current user and permission seam.

The POC has one mock user. Historically every permission was allowed, and that
remains the default so existing behaviour is unchanged. The LMS adds a real
permission vocabulary and a strict role matrix behind `LMS_ENFORCE_ROLES`, so
that when the admin portal brings real authentication the switch is one
environment variable plus a real `get_current_user`.

When RBAC arrives:
  1. replace `get_current_user` with a real login lookup,
  2. set LMS_ENFORCE_ROLES=true and give users the roles below,
  3. keep `require_permission(...)` on the routes, which already call it.

Permission checks are always enforced server side. Note that several of the
LMS's protections do not depend on roles at all and apply regardless: learners
cannot see unpublished courses, cannot read source materials, never receive
correct answers before submitting, and cannot write their own progress.
"""
import os

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import User

# --- Permission vocabulary -------------------------------------------------

LEARNER_PERMISSIONS = {
    "learning:progress", "mentor:request", "community:join",
    "course:view", "course:enrol", "assessment:attempt", "certificate:view",
}
AUTHOR_PERMISSIONS = LEARNER_PERMISSIONS | {
    "course:create", "course:edit", "course:material:upload", "course:generate",
    "course:import", "assessment:manage",
}
LEARNING_ADMIN_PERMISSIONS = AUTHOR_PERMISSIONS | {
    "course:publish", "course:archive", "certificate:issue", "certificate:revoke",
    "analytics:view",
}

# Roles used once LMS_ENFORCE_ROLES is on.
STRICT_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "Employee": LEARNER_PERMISSIONS,
    "CourseAuthor": AUTHOR_PERMISSIONS,
    "LearningAdmin": LEARNING_ADMIN_PERMISSIONS,
    "InnovationAdmin": {"*"},
}

# POC default: every role may do everything (unchanged from before the LMS).
ROLE_PERMISSIONS: dict[str, set[str]] = {"Employee": {"*"}}


def _strict() -> bool:
    return (os.getenv("LMS_ENFORCE_ROLES", "") or "").strip().lower() in {"1", "true", "yes", "on"}


def _matrix() -> dict[str, set[str]]:
    return STRICT_ROLE_PERMISSIONS if _strict() else ROLE_PERMISSIONS


def permissions_for(user: User) -> list[str]:
    return sorted(_matrix().get(user.role, set()))


def has_permission(user: User, permission: str) -> bool:
    granted = _matrix().get(user.role, set())
    return "*" in granted or permission in granted


def get_current_user(db: Session = Depends(get_db)) -> User:
    email = os.getenv("POC_USER_EMAIL", "alex.mwangi@example.com")
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(500, "Mock user not found. Run `python init_db.py` first.")
    return user


def require_permission(permission: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user, permission):
            raise HTTPException(403, f"Missing permission: {permission}")
        return user
    return dependency
