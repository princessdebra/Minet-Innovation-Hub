"""Business logic for the LMS: progress, scoring, completion and certificates.

Route handlers stay thin; everything that decides whether an employee has
actually completed something lives here, on the server, where a learner cannot
reach it.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config
from .lms_models import (Assessment, AssessmentAttempt, AssessmentQuestion, Certificate,
                         ContentBlock, Course, CourseModule, Enrollment, Lesson,
                         LessonProgress)
from .models import User

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I/O/0/1


# ---------------------------------------------------------------------------
# Slugs and fingerprints
# ---------------------------------------------------------------------------

def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:150] or "course"


def unique_slug(db: Session, title: str, *, exclude_id: Optional[int] = None) -> str:
    base = slugify(title)
    candidate = base
    suffix = 2
    while True:
        query = select(Course.id).where(Course.slug == candidate)
        if exclude_id is not None:
            query = query.where(Course.id != exclude_id)
        if db.scalar(query) is None:
            return candidate
        candidate = f"{base}-{suffix}"[:150]
        suffix += 1


def job_fingerprint(*, course_id: int, instructions: str, material_ids: Iterable[int]) -> str:
    payload = "|".join([str(course_id), (instructions or "").strip(),
                        ",".join(str(m) for m in sorted(material_ids))])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Course shape
# ---------------------------------------------------------------------------

def course_lessons(db: Session, course_id: int, *, published_only: bool = True) -> list[Lesson]:
    query = (select(Lesson).join(CourseModule, Lesson.module_id == CourseModule.id)
             .where(CourseModule.course_id == course_id)
             .order_by(CourseModule.position, Lesson.position))
    if published_only:
        query = query.where(Lesson.is_published.is_(True), CourseModule.is_published.is_(True))
    return list(db.scalars(query))


def course_required_assessments(db: Session, course_id: int) -> list[Assessment]:
    return list(db.scalars(
        select(Assessment).where(
            Assessment.course_id == course_id,
            Assessment.is_required_for_completion.is_(True),
            Assessment.is_published.is_(True))))


def recalculate_course_duration(db: Session, course: Course) -> None:
    total = db.scalar(
        select(func.coalesce(func.sum(Lesson.estimated_minutes), 0))
        .join(CourseModule, Lesson.module_id == CourseModule.id)
        .where(CourseModule.course_id == course.id)) or 0
    course.estimated_minutes = int(total)


# ---------------------------------------------------------------------------
# Enrolment and progress
# ---------------------------------------------------------------------------

def get_or_create_enrollment(db: Session, user: User, course: Course) -> Enrollment:
    enrollment = db.scalar(select(Enrollment).where(
        Enrollment.user_id == user.id, Enrollment.course_id == course.id))
    if enrollment is None:
        enrollment = Enrollment(user_id=user.id, course_id=course.id, status="not_started")
        db.add(enrollment)
        db.flush()
    enrollment.last_accessed_at = datetime.now()
    return enrollment


def _lesson_progress(db: Session, enrollment: Enrollment, lesson_id: int) -> LessonProgress:
    row = db.scalar(select(LessonProgress).where(
        LessonProgress.enrollment_id == enrollment.id,
        LessonProgress.lesson_id == lesson_id))
    if row is None:
        row = LessonProgress(enrollment_id=enrollment.id, lesson_id=lesson_id,
                             status="not_started")
        db.add(row)
        db.flush()
    return row


def has_passed(db: Session, user_id: int, assessment_id: int) -> bool:
    return db.scalar(
        select(func.count()).select_from(AssessmentAttempt).where(
            AssessmentAttempt.assessment_id == assessment_id,
            AssessmentAttempt.user_id == user_id,
            AssessmentAttempt.passed.is_(True))) > 0


def lesson_requirements_met(db: Session, user_id: int, lesson: Lesson) -> tuple[bool, list[str]]:
    """Server-side gate. A learner marking a lesson done is not sufficient when
    the lesson carries a required assessment."""
    unmet: list[str] = []
    if lesson.completion_rule == "assessment":
        required = list(db.scalars(select(Assessment).where(
            Assessment.lesson_id == lesson.id,
            Assessment.is_required_for_completion.is_(True),
            Assessment.is_published.is_(True))))
        for assessment in required:
            if not has_passed(db, user_id, assessment.id):
                unmet.append(f"Pass the assessment '{assessment.title}'.")
    return (not unmet), unmet


def mark_lesson_started(db: Session, enrollment: Enrollment, lesson: Lesson) -> LessonProgress:
    row = _lesson_progress(db, enrollment, lesson.id)
    now = datetime.now()
    if row.started_at is None:
        row.started_at = now
    if row.status == "not_started":
        row.status = "in_progress"
    row.last_accessed_at = now
    if enrollment.started_at is None:
        enrollment.started_at = now
    if enrollment.status == "not_started":
        enrollment.status = "in_progress"
    return row


def mark_lesson_complete(db: Session, user: User, enrollment: Enrollment, lesson: Lesson,
                         *, seconds_spent: int = 0) -> tuple[LessonProgress, list[str]]:
    met, unmet = lesson_requirements_met(db, user.id, lesson)
    row = mark_lesson_started(db, enrollment, lesson)
    if seconds_spent > 0:
        row.seconds_spent = (row.seconds_spent or 0) + min(seconds_spent, 4 * 60 * 60)
    if met:
        row.status = "completed"
        row.completed_at = row.completed_at or datetime.now()
    return row, unmet


def recalculate_progress(db: Session, enrollment: Enrollment, course: Course) -> Enrollment:
    """Derived from real lesson rows -- never incremented by a client."""
    # The session is autoflush=False, so pending lesson rows must be written
    # before we count them.
    db.flush()
    lessons = course_lessons(db, course.id)
    total = len(lessons)
    lesson_ids = {lsn.id for lsn in lessons}
    completed_ids = set(db.scalars(
        select(LessonProgress.lesson_id).where(
            LessonProgress.enrollment_id == enrollment.id,
            LessonProgress.status == "completed")))
    completed = len(lesson_ids & completed_ids)

    enrollment.seconds_spent = int(db.scalar(
        select(func.coalesce(func.sum(LessonProgress.seconds_spent), 0))
        .where(LessonProgress.enrollment_id == enrollment.id)) or 0)

    assessments_ok = True
    if course.pass_requires_assessments:
        for assessment in course_required_assessments(db, course.id):
            if not has_passed(db, enrollment.user_id, assessment.id):
                assessments_ok = False
                break

    lessons_done = total > 0 and completed >= total
    if total == 0:
        enrollment.progress_percent = 0
    else:
        # Assessments count as the final slice of progress when they gate completion.
        lesson_share = round(100 * completed / total)
        enrollment.progress_percent = min(
            100 if (lessons_done and assessments_ok) else 99, lesson_share)

    if lessons_done and assessments_ok:
        enrollment.status = "completed"
        enrollment.completed_at = enrollment.completed_at or datetime.now()
    elif completed > 0 or enrollment.started_at:
        enrollment.status = "in_progress"
        enrollment.completed_at = None
    else:
        enrollment.status = "not_started"
        enrollment.completed_at = None
    return enrollment


def completion_blockers(db: Session, enrollment: Enrollment, course: Course) -> list[str]:
    db.flush()
    blockers: list[str] = []
    lessons = course_lessons(db, course.id)
    completed_ids = set(db.scalars(
        select(LessonProgress.lesson_id).where(
            LessonProgress.enrollment_id == enrollment.id,
            LessonProgress.status == "completed")))
    outstanding = [lsn for lsn in lessons if lsn.id not in completed_ids]
    if outstanding:
        blockers.append(f"{len(outstanding)} of {len(lessons)} lessons still to complete.")
    if course.pass_requires_assessments:
        for assessment in course_required_assessments(db, course.id):
            if not has_passed(db, enrollment.user_id, assessment.id):
                blockers.append(f"Assessment '{assessment.title}' not yet passed.")
    return blockers


# ---------------------------------------------------------------------------
# Assessment scoring (server side only)
# ---------------------------------------------------------------------------

def _normalise_answer(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return sorted(str(v).strip().lower() for v in value if str(v).strip())
    return [str(value).strip().lower()] if str(value).strip() else []


def grade_attempt(questions: list[AssessmentQuestion], answers: dict) -> dict:
    """Score an attempt. Correct answers never leave the server before this."""
    total_marks = sum(max(1, q.marks or 1) for q in questions) or 1
    scored = 0
    per_question: list[dict] = []

    for question in questions:
        marks = max(1, question.marks or 1)
        given = _normalise_answer(answers.get(str(question.id)))
        expected = _normalise_answer(question.correct)
        if question.kind == "short_answer":
            correct = bool(given) and any(g in expected for g in given)
        elif question.kind == "multiple":
            correct = bool(given) and given == expected
        else:
            correct = bool(given) and len(given) == 1 and given[0] in expected
        if correct:
            scored += marks
        per_question.append({
            "question_id": question.id,
            "correct": correct,
            "marks_awarded": marks if correct else 0,
            "marks_possible": marks,
            "explanation": question.explanation,
        })

    percent = round(100 * scored / total_marks)
    return {"score": scored, "max_score": total_marks, "percent": percent,
            "results": per_question}


def attempts_used(db: Session, assessment_id: int, user_id: int) -> int:
    return db.scalar(select(func.count()).select_from(AssessmentAttempt).where(
        AssessmentAttempt.assessment_id == assessment_id,
        AssessmentAttempt.user_id == user_id,
        AssessmentAttempt.submitted_at.is_not(None))) or 0


# ---------------------------------------------------------------------------
# Certificates
# ---------------------------------------------------------------------------

def _verification_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(12))


def best_score(db: Session, user_id: int, course_id: int) -> Optional[int]:
    return db.scalar(
        select(func.max(AssessmentAttempt.percent))
        .join(Assessment, Assessment.id == AssessmentAttempt.assessment_id)
        .where(Assessment.course_id == course_id,
               AssessmentAttempt.user_id == user_id,
               AssessmentAttempt.passed.is_(True)))


def issue_certificate_if_earned(db: Session, user: User, course: Course,
                                enrollment: Enrollment) -> Optional[Certificate]:
    """Idempotent: returns the existing certificate if there already is one."""
    if enrollment.status != "completed":
        return None
    existing = db.scalar(select(Certificate).where(
        Certificate.user_id == user.id, Certificate.course_id == course.id,
        Certificate.revoked_at.is_(None)))
    if existing:
        return existing

    assessed = bool(course_required_assessments(db, course.id)) and course.pass_requires_assessments
    score = best_score(db, user.id, course.id) if assessed else None
    year = datetime.now().year
    sequence = (db.scalar(select(func.count()).select_from(Certificate)) or 0) + 1

    for _ in range(5):
        code = _verification_code()
        if db.scalar(select(Certificate.id).where(Certificate.verification_code == code)) is None:
            break
    else:  # pragma: no cover - astronomically unlikely
        raise RuntimeError("Could not allocate a unique verification code.")

    certificate = Certificate(
        user_id=user.id,
        course_id=course.id,
        certificate_type="assessed_competency" if assessed else "completion",
        certificate_number=f"MIH-{year}-{sequence:05d}",
        verification_code=code,
        course_title=course.title,
        recipient_name=user.name,
        course_version=course.version,
        score_percent=score,
    )
    db.add(certificate)
    db.flush()
    return certificate


def verification_url(code: str) -> str:
    return f"{config.PUBLIC_BASE_URL}/verify/{code}"


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------

def lesson_block_count(db: Session, lesson_id: int) -> int:
    return db.scalar(select(func.count()).select_from(ContentBlock)
                     .where(ContentBlock.lesson_id == lesson_id)) or 0
