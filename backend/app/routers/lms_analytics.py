"""Learning analytics for administrators.

Every number is computed from learning records. Nothing here is hardcoded, and
a metric with no underlying data is reported as null rather than zero, so an
empty system does not read as a real result.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..lms_models import (Assessment, AssessmentAttempt, Certificate, Course, CourseModule,
                          Enrollment, GenerationJob, Lesson, LessonProgress)
from ..models import User
from ..security import require_permission

router = APIRouter(prefix="/api/lms/admin", tags=["lms-analytics"])

LOW_COMPLETION_THRESHOLD = 40


def _completion_rate(completed: int, enrolled: int) -> Optional[int]:
    return round(100 * completed / enrolled) if enrolled else None


@router.get("/analytics")
def analytics(limit: int = Query(5, ge=1, le=25), db: Session = Depends(get_db),
              _=Depends(require_permission("analytics:view"))):
    total_courses = db.scalar(select(func.count()).select_from(Course)) or 0
    published = db.scalar(select(func.count()).select_from(Course)
                          .where(Course.status == "published")) or 0
    awaiting = db.scalar(select(func.count()).select_from(Course)
                         .where(Course.status == "awaiting_review")) or 0
    enrolments = db.scalar(select(func.count()).select_from(Enrollment)) or 0
    completions = db.scalar(select(func.count()).select_from(Enrollment)
                            .where(Enrollment.status == "completed")) or 0
    certificates = db.scalar(select(func.count()).select_from(Certificate)
                             .where(Certificate.revoked_at.is_(None))) or 0
    learners = db.scalar(select(func.count(func.distinct(Enrollment.user_id)))
                         .select_from(Enrollment)) or 0
    avg_score = db.scalar(select(func.avg(AssessmentAttempt.percent))
                          .where(AssessmentAttempt.submitted_at.is_not(None)))
    minutes = db.scalar(select(func.coalesce(func.sum(Enrollment.seconds_spent), 0))) or 0

    per_course = db.execute(
        select(Enrollment.course_id,
               func.count(Enrollment.id),
               func.sum(case((Enrollment.status == "completed", 1), else_=0)))
        .group_by(Enrollment.course_id)).all()
    titles = {c.id: c.title for c in db.scalars(select(Course))}

    rows = []
    for course_id, enrolled, completed in per_course:
        completed = int(completed or 0)
        rows.append({
            "course_id": course_id,
            "title": titles.get(course_id, "Unknown course"),
            "enrolments": int(enrolled or 0),
            "completions": completed,
            "completion_rate": _completion_rate(completed, int(enrolled or 0)),
        })

    popular = sorted(rows, key=lambda r: -r["enrolments"])[:limit]
    # "Low completion" only means something once a course has a few learners.
    low = sorted([r for r in rows
                  if r["enrolments"] >= 3 and (r["completion_rate"] or 0) < LOW_COMPLETION_THRESHOLD],
                 key=lambda r: r["completion_rate"] or 0)[:limit]

    jobs = db.execute(select(GenerationJob.status, func.count())
                      .group_by(GenerationJob.status)).all()

    return {
        "totals": {
            "courses": total_courses,
            "published_courses": published,
            "awaiting_review": awaiting,
            "enrolments": enrolments,
            "completions": completions,
            "certificates_issued": certificates,
            "active_learners": learners,
            "completion_rate": _completion_rate(completions, enrolments),
            "average_assessment_score": round(float(avg_score)) if avg_score is not None else None,
            "learning_minutes": round(int(minutes) / 60),
        },
        "most_popular": popular,
        "low_completion": low,
        "generation_jobs": {status: count for status, count in jobs},
        "notes": [
            "Completion rate is null where no one has enrolled yet.",
            "Average assessment score covers every submitted attempt, not only passes.",
            f"Low completion lists courses with at least 3 enrolments and under "
            f"{LOW_COMPLETION_THRESHOLD}% completion.",
        ],
    }


@router.get("/analytics/courses/{course_id}")
def course_analytics(course_id: int, db: Session = Depends(get_db),
                     _=Depends(require_permission("analytics:view"))):
    course = db.get(Course, course_id)
    if not course:
        from fastapi import HTTPException
        raise HTTPException(404, "Course not found")

    enrolments = list(db.scalars(select(Enrollment).where(Enrollment.course_id == course_id)))
    completed = sum(1 for e in enrolments if e.status == "completed")
    names = {u.id: u.name for u in db.scalars(select(User))}

    lessons = list(db.scalars(
        select(Lesson).join(CourseModule, Lesson.module_id == CourseModule.id)
        .where(CourseModule.course_id == course_id)
        .order_by(CourseModule.position, Lesson.position)))
    enrollment_ids = [e.id for e in enrolments] or [-1]
    done_per_lesson = dict(db.execute(
        select(LessonProgress.lesson_id, func.count())
        .where(LessonProgress.enrollment_id.in_(enrollment_ids),
               LessonProgress.status == "completed")
        .group_by(LessonProgress.lesson_id)).all())

    assessments = list(db.scalars(select(Assessment).where(Assessment.course_id == course_id)))
    assessment_rows = []
    for assessment in assessments:
        attempts = list(db.scalars(select(AssessmentAttempt).where(
            AssessmentAttempt.assessment_id == assessment.id,
            AssessmentAttempt.submitted_at.is_not(None))))
        passes = sum(1 for a in attempts if a.passed)
        scores = [a.percent for a in attempts if a.percent is not None]
        assessment_rows.append({
            "id": assessment.id, "title": assessment.title,
            "attempts": len(attempts), "passes": passes,
            "pass_rate": round(100 * passes / len(attempts)) if attempts else None,
            "average_score": round(sum(scores) / len(scores)) if scores else None,
        })

    return {
        "course": {"id": course.id, "title": course.title, "status": course.status,
                   "version": course.version},
        "totals": {
            "enrolments": len(enrolments),
            "completions": completed,
            "completion_rate": _completion_rate(completed, len(enrolments)),
            "certificates": db.scalar(select(func.count()).select_from(Certificate)
                                      .where(Certificate.course_id == course_id,
                                             Certificate.revoked_at.is_(None))) or 0,
            "average_progress": round(sum(e.progress_percent for e in enrolments) / len(enrolments))
            if enrolments else None,
        },
        "lesson_funnel": [{
            "lesson_id": lesson.id, "title": lesson.title,
            "completed_by": done_per_lesson.get(lesson.id, 0),
            "completion_rate": _completion_rate(done_per_lesson.get(lesson.id, 0),
                                                len(enrolments)),
        } for lesson in lessons],
        "assessments": assessment_rows,
        "learners": [{
            "user_id": e.user_id, "name": names.get(e.user_id, "Unknown"),
            "status": e.status, "progress_percent": e.progress_percent,
            "completed_at": e.completed_at.isoformat() if e.completed_at else None,
        } for e in sorted(enrolments, key=lambda x: -x.progress_percent)[:200]],
    }
