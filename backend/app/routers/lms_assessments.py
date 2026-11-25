"""Assessments for learners.

Two rules enforced here and nowhere else:
  * correct answers are never serialised to a learner before submission, and
  * grading happens on the server, from the stored answer key.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..lms_models import Assessment, AssessmentAttempt, Course, CourseModule, Lesson
from ..lms_serializers import assessment_payload, attempt_payload, certificate_payload
from ..lms_services import (attempts_used, get_or_create_enrollment, grade_attempt,
                            issue_certificate_if_earned, recalculate_progress,
                            verification_url)
from ..security import get_current_user, require_permission

router = APIRouter(prefix="/api/lms", tags=["lms-assessments"])


def _assessment_for_learner(db: Session, assessment_id: int) -> tuple[Assessment, Course]:
    assessment = db.get(Assessment, assessment_id)
    if not assessment or not assessment.is_published:
        raise HTTPException(404, "Assessment not found")
    course = db.get(Course, assessment.course_id)
    if not course or course.status != "published":
        raise HTTPException(404, "Assessment not found")
    return assessment, course


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: int, db: Session = Depends(get_db),
                   user=Depends(get_current_user)):
    assessment, _ = _assessment_for_learner(db, assessment_id)
    used = attempts_used(db, assessment.id, user.id)
    best = db.scalar(
        select(AssessmentAttempt)
        .where(AssessmentAttempt.assessment_id == assessment.id,
               AssessmentAttempt.user_id == user.id,
               AssessmentAttempt.submitted_at.is_not(None))
        .order_by(AssessmentAttempt.percent.desc()).limit(1))
    return assessment_payload(assessment, attempts_used=used, best=best)


@router.post("/assessments/{assessment_id}/attempts", status_code=201)
def start_attempt(assessment_id: int, db: Session = Depends(get_db),
                  user=Depends(require_permission("assessment:attempt"))):
    assessment, _ = _assessment_for_learner(db, assessment_id)
    used = attempts_used(db, assessment.id, user.id)
    if used >= assessment.max_attempts:
        raise HTTPException(409, {
            "message": f"You have used all {assessment.max_attempts} attempts.",
            "attempts_used": used})

    open_attempt = db.scalar(select(AssessmentAttempt).where(
        AssessmentAttempt.assessment_id == assessment.id,
        AssessmentAttempt.user_id == user.id,
        AssessmentAttempt.submitted_at.is_(None)))
    if open_attempt is None:
        open_attempt = AssessmentAttempt(
            assessment_id=assessment.id, user_id=user.id, attempt_number=used + 1)
        db.add(open_attempt)
        db.commit()

    deadline = None
    if assessment.time_limit_minutes:
        deadline = (open_attempt.started_at
                    + timedelta(minutes=assessment.time_limit_minutes)).isoformat()
    return {**attempt_payload(open_attempt),
            "deadline": deadline,
            "assessment": assessment_payload(assessment, attempts_used=used)}


class SubmitIn(BaseModel):
    # {"<question_id>": "a"} or {"<question_id>": ["a", "c"]}
    answers: dict[str, object] = Field(default_factory=dict)


@router.post("/attempts/{attempt_id}/submit")
def submit_attempt(attempt_id: int, payload: SubmitIn, db: Session = Depends(get_db),
                   user=Depends(require_permission("assessment:attempt"))):
    attempt = db.get(AssessmentAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        # Never reveal that another learner's attempt exists.
        raise HTTPException(404, "Attempt not found")
    if attempt.submitted_at is not None:
        raise HTTPException(409, "This attempt has already been submitted.")

    assessment, course = _assessment_for_learner(db, attempt.assessment_id)
    if assessment.time_limit_minutes:
        deadline = attempt.started_at + timedelta(minutes=assessment.time_limit_minutes)
        if datetime.now() > deadline + timedelta(seconds=30):  # small grace for latency
            attempt.submitted_at = datetime.now()
            attempt.score, attempt.max_score, attempt.percent = 0, 0, 0
            attempt.passed = False
            attempt.answers = {"_expired": True}
            db.commit()
            raise HTTPException(409, "The time limit for this attempt has passed.")

    graded = grade_attempt(list(assessment.questions), payload.answers or {})
    attempt.answers = {str(k): v for k, v in (payload.answers or {}).items()}
    attempt.score = graded["score"]
    attempt.max_score = graded["max_score"]
    attempt.percent = graded["percent"]
    attempt.passed = graded["percent"] >= assessment.pass_percent
    attempt.submitted_at = datetime.now()
    db.flush()

    enrollment = get_or_create_enrollment(db, user, course)
    recalculate_progress(db, enrollment, course)
    certificate = issue_certificate_if_earned(db, user, course, enrollment)
    db.commit()

    return {
        **attempt_payload(attempt, results=graded["results"]),
        "pass_percent": assessment.pass_percent,
        "attempts_used": attempts_used(db, assessment.id, user.id),
        "attempts_left": max(0, assessment.max_attempts
                             - attempts_used(db, assessment.id, user.id)),
        "certificate": certificate_payload(
            certificate, verification_url=verification_url(certificate.verification_code))
        if certificate else None,
    }


@router.get("/assessments/{assessment_id}/attempts")
def my_attempts(assessment_id: int, db: Session = Depends(get_db),
                user=Depends(get_current_user)):
    _assessment_for_learner(db, assessment_id)
    rows = db.scalars(select(AssessmentAttempt).where(
        AssessmentAttempt.assessment_id == assessment_id,
        AssessmentAttempt.user_id == user.id).order_by(AssessmentAttempt.id))
    return [attempt_payload(a) for a in rows]


@router.get("/courses/{course_id}/assessments")
def course_assessments(course_id: int, db: Session = Depends(get_db),
                       user=Depends(get_current_user)):
    course = db.get(Course, course_id)
    if not course or course.status != "published":
        raise HTTPException(404, "Course not found")
    rows = list(db.scalars(select(Assessment).where(
        Assessment.course_id == course_id, Assessment.is_published.is_(True))
        .order_by(Assessment.id)))
    out = []
    for assessment in rows:
        used = attempts_used(db, assessment.id, user.id)
        best = db.scalar(select(AssessmentAttempt)
                         .where(AssessmentAttempt.assessment_id == assessment.id,
                                AssessmentAttempt.user_id == user.id,
                                AssessmentAttempt.submitted_at.is_not(None))
                         .order_by(AssessmentAttempt.percent.desc()).limit(1))
        payload = assessment_payload(assessment, attempts_used=used, best=best)
        payload.pop("questions", None)   # list view does not need the questions
        out.append(payload)
    return out


def _lesson_title(db: Session, lesson_id: Optional[int]) -> Optional[str]:
    if not lesson_id:
        return None
    lesson = db.get(Lesson, lesson_id)
    return lesson.title if lesson else None


def _module_title(db: Session, module_id: Optional[int]) -> Optional[str]:
    if not module_id:
        return None
    module = db.get(CourseModule, module_id)
    return module.title if module else None
