"""Employee learning experience: catalogue, course, lesson player, progress.

Only published courses are reachable here, whatever the caller's role.
Progress is written from lesson rows the server controls -- a client cannot
post a progress percentage or a completion date.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..lms_models import (Assessment, AssessmentAttempt, Certificate, Course, CourseModule,
                          Enrollment, Lesson, LessonProgress, MediaAsset)
from ..lms_serializers import (asset_brief, certificate_payload, course_card,
                               enrollment_payload, lesson_payload, module_payload)
from ..lms_services import (completion_blockers, course_lessons, get_or_create_enrollment,
                            issue_certificate_if_earned, mark_lesson_complete,
                            mark_lesson_started, recalculate_progress, verification_url)
from ..security import get_current_user, require_permission

router = APIRouter(prefix="/api/lms", tags=["lms-learning"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _published_course(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if not course or course.status != "published":
        raise HTTPException(404, "Course not found")
    return course


def _lesson_in_published_course(db: Session, lesson_id: int) -> tuple[Lesson, Course]:
    lesson = db.get(Lesson, lesson_id)
    if not lesson or not lesson.is_published:
        raise HTTPException(404, "Lesson not found")
    module = db.get(CourseModule, lesson.module_id)
    if not module or not module.is_published:
        raise HTTPException(404, "Lesson not found")
    course = db.get(Course, module.course_id)
    if not course or course.status != "published":
        raise HTTPException(404, "Lesson not found")
    return lesson, course


def _progress_map(db: Session, enrollment: Optional[Enrollment]) -> dict[int, str]:
    if enrollment is None:
        return {}
    rows = db.execute(select(LessonProgress.lesson_id, LessonProgress.status)
                      .where(LessonProgress.enrollment_id == enrollment.id)).all()
    return {lesson_id: status for lesson_id, status in rows}


def _lesson_counts(db: Session, course_ids: list[int]) -> dict[int, int]:
    if not course_ids:
        return {}
    rows = db.execute(
        select(CourseModule.course_id, func.count(Lesson.id))
        .join(Lesson, Lesson.module_id == CourseModule.id)
        .where(CourseModule.course_id.in_(course_ids),
               CourseModule.is_published.is_(True), Lesson.is_published.is_(True))
        .group_by(CourseModule.course_id)).all()
    return {course_id: count for course_id, count in rows}


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

@router.get("/catalog")
def catalog(search: Optional[str] = None, category: Optional[str] = None,
            status: Optional[str] = Query(None, description="not_started|in_progress|completed"),
            page: int = Query(1, ge=1), per_page: int = Query(24, ge=1, le=60),
            db: Session = Depends(get_db), user=Depends(get_current_user)):
    query = select(Course).where(Course.status == "published")
    if category:
        query = query.where(Course.category == category)
    if search and search.strip():
        like = f"%{search.strip()}%"
        query = query.where(or_(Course.title.like(like), Course.summary.like(like),
                                Course.description.like(like)))

    courses = list(db.scalars(query.order_by(Course.published_at.desc(), Course.id.desc())))
    enrollments = {e.course_id: e for e in db.scalars(
        select(Enrollment).where(Enrollment.user_id == user.id))}
    if status:
        courses = [c for c in courses
                   if (enrollments[c.id].status if c.id in enrollments else "not_started") == status]

    total = len(courses)
    window = courses[(page - 1) * per_page: page * per_page]
    counts = _lesson_counts(db, [c.id for c in window])
    thumbnails = {a.id: a for a in db.scalars(select(MediaAsset).where(
        MediaAsset.id.in_([c.thumbnail_asset_id for c in window if c.thumbnail_asset_id] or [-1])))}

    return {
        "total": total, "page": page, "per_page": per_page,
        "courses": [course_card(c, enrollment=enrollments.get(c.id),
                                thumbnail=thumbnails.get(c.thumbnail_asset_id),
                                lesson_count=counts.get(c.id, 0)) for c in window],
        "categories": sorted({c.category for c in courses if c.category}),
    }


@router.get("/courses/{course_id}")
def course_detail(course_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    course = _published_course(db, course_id)
    enrollment = db.scalar(select(Enrollment).where(
        Enrollment.user_id == user.id, Enrollment.course_id == course.id))
    progress = _progress_map(db, enrollment)

    assessments = list(db.scalars(select(Assessment).where(
        Assessment.course_id == course.id, Assessment.is_published.is_(True))))
    certificate = db.scalar(select(Certificate).where(
        Certificate.user_id == user.id, Certificate.course_id == course.id,
        Certificate.revoked_at.is_(None)))

    lessons = course_lessons(db, course.id)
    next_lesson = next((lsn for lsn in lessons if progress.get(lsn.id) != "completed"), None)

    return {
        "course": {
            "id": course.id, "slug": course.slug, "title": course.title,
            "summary": course.summary, "description": course.description,
            "objectives": course.objectives or [], "category": course.category,
            "tags": course.tags or [], "difficulty": course.difficulty,
            "estimated_minutes": course.estimated_minutes,
            "origin": course.origin, "ai_disclosure": course.ai_disclosure,
            "version": course.version,
            "thumbnail": asset_brief(db.get(MediaAsset, course.thumbnail_asset_id)
                                     if course.thumbnail_asset_id else None),
        },
        "modules": [module_payload(m, for_admin=False, progress=progress)
                    for m in course.modules if m.is_published],
        "enrollment": enrollment_payload(enrollment) if enrollment else None,
        "lesson_count": len(lessons),
        "resume_lesson_id": next_lesson.id if next_lesson else None,
        "requirements": {
            "lessons": len(lessons),
            "assessments": [{"id": a.id, "title": a.title,
                             "pass_percent": a.pass_percent,
                             "required": a.is_required_for_completion} for a in assessments],
            "blockers": completion_blockers(db, enrollment, course) if enrollment else [],
        },
        "certificate": certificate_payload(
            certificate, verification_url=verification_url(certificate.verification_code))
        if certificate else None,
    }


@router.post("/courses/{course_id}/enrol", status_code=201)
def enrol(course_id: int, db: Session = Depends(get_db),
          user=Depends(require_permission("course:enrol"))):
    course = _published_course(db, course_id)
    enrollment = get_or_create_enrollment(db, user, course)
    recalculate_progress(db, enrollment, course)
    db.commit()
    return enrollment_payload(enrollment)


# ---------------------------------------------------------------------------
# Lesson player
# ---------------------------------------------------------------------------

@router.get("/lessons/{lesson_id}")
def get_lesson(lesson_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    lesson, course = _lesson_in_published_course(db, lesson_id)
    enrollment = get_or_create_enrollment(db, user, course)
    mark_lesson_started(db, enrollment, lesson)
    db.commit()

    lessons = course_lessons(db, course.id)
    index = next((i for i, item in enumerate(lessons) if item.id == lesson.id), 0)
    progress = _progress_map(db, enrollment)
    assessments = list(db.scalars(select(Assessment).where(
        Assessment.lesson_id == lesson.id, Assessment.is_published.is_(True))))

    return {
        "lesson": lesson_payload(lesson, blocks=True,
                                 progress_status=progress.get(lesson.id, "in_progress")),
        "course": {"id": course.id, "title": course.title, "slug": course.slug,
                   "ai_disclosure": course.ai_disclosure},
        "module": {"id": lesson.module_id,
                   "title": db.get(CourseModule, lesson.module_id).title},
        "navigation": {
            "position": index + 1,
            "total": len(lessons),
            "previous_id": lessons[index - 1].id if index > 0 else None,
            "next_id": lessons[index + 1].id if index + 1 < len(lessons) else None,
        },
        "assessments": [{"id": a.id, "title": a.title, "required": a.is_required_for_completion}
                        for a in assessments],
        "enrollment": enrollment_payload(enrollment),
    }


class CompleteIn(BaseModel):
    seconds_spent: int = Field(0, ge=0, le=4 * 60 * 60)


@router.post("/lessons/{lesson_id}/complete")
def complete_lesson(lesson_id: int, payload: CompleteIn, db: Session = Depends(get_db),
                    user=Depends(require_permission("learning:progress"))):
    lesson, course = _lesson_in_published_course(db, lesson_id)
    enrollment = get_or_create_enrollment(db, user, course)
    row, unmet = mark_lesson_complete(db, user, enrollment, lesson,
                                      seconds_spent=payload.seconds_spent)
    recalculate_progress(db, enrollment, course)
    certificate = issue_certificate_if_earned(db, user, course, enrollment)
    db.commit()
    return {
        "lesson_id": lesson.id,
        "status": row.status,
        "unmet_requirements": unmet,
        "enrollment": enrollment_payload(enrollment),
        "certificate": certificate_payload(
            certificate, verification_url=verification_url(certificate.verification_code))
        if certificate else None,
    }


class HeartbeatIn(BaseModel):
    seconds_spent: int = Field(..., ge=1, le=600)


@router.post("/lessons/{lesson_id}/heartbeat")
def lesson_heartbeat(lesson_id: int, payload: HeartbeatIn, db: Session = Depends(get_db),
                     user=Depends(require_permission("learning:progress"))):
    """Time spent, capped per call. Never completes a lesson on its own."""
    lesson, course = _lesson_in_published_course(db, lesson_id)
    enrollment = get_or_create_enrollment(db, user, course)
    row = mark_lesson_started(db, enrollment, lesson)
    row.seconds_spent = (row.seconds_spent or 0) + payload.seconds_spent
    recalculate_progress(db, enrollment, course)
    db.commit()
    return {"lesson_id": lesson.id, "seconds_spent": row.seconds_spent}


# ---------------------------------------------------------------------------
# Personal dashboard
# ---------------------------------------------------------------------------

@router.get("/me/learning")
def my_learning(db: Session = Depends(get_db), user=Depends(get_current_user)):
    enrollments = list(db.scalars(select(Enrollment)
                                  .where(Enrollment.user_id == user.id)
                                  .order_by(Enrollment.last_accessed_at.is_(None),
                                           Enrollment.last_accessed_at.desc())))
    course_ids = [e.course_id for e in enrollments]
    courses = {c.id: c for c in db.scalars(
        select(Course).where(Course.id.in_(course_ids or [-1])))}
    counts = _lesson_counts(db, course_ids)

    def entry(enrollment: Enrollment) -> Optional[dict]:
        course = courses.get(enrollment.course_id)
        if not course or course.status != "published":
            return None
        return {**course_card(course, enrollment=enrollment,
                              lesson_count=counts.get(course.id, 0)),
                "last_accessed_at": enrollment.last_accessed_at.isoformat()
                if enrollment.last_accessed_at else None}

    entries = [e for e in (entry(x) for x in enrollments) if e]
    certificates = list(db.scalars(select(Certificate).where(
        Certificate.user_id == user.id).order_by(Certificate.issued_at.desc())))
    attempts = list(db.scalars(
        select(AssessmentAttempt).where(AssessmentAttempt.user_id == user.id,
                                        AssessmentAttempt.submitted_at.is_not(None))
        .order_by(AssessmentAttempt.submitted_at.desc()).limit(10)))
    assessment_titles = {a.id: a.title for a in db.scalars(
        select(Assessment).where(Assessment.id.in_([x.assessment_id for x in attempts] or [-1])))}

    recommended = [course_card(c, lesson_count=0) for c in db.scalars(
        select(Course).where(Course.status == "published",
                             Course.id.not_in(course_ids or [-1]))
        .order_by(Course.published_at.desc()).limit(4))]

    return {
        "in_progress": [e for e in entries if e["status"] == "in_progress"],
        "completed": [e for e in entries if e["status"] == "completed"],
        "not_started": [e for e in entries if e["status"] == "not_started"],
        "recommended": recommended,
        "certificates": [certificate_payload(
            c, verification_url=verification_url(c.verification_code)) for c in certificates],
        "recent_results": [{
            "assessment_id": a.assessment_id,
            "assessment_title": assessment_titles.get(a.assessment_id, "Assessment"),
            "percent": a.percent, "passed": a.passed,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
        } for a in attempts],
        "totals": {
            "enrolled": len(entries),
            "completed": sum(1 for e in entries if e["status"] == "completed"),
            "certificates": sum(1 for c in certificates if c.is_valid),
            "minutes_spent": round(sum(e.seconds_spent or 0 for e in enrollments) / 60),
        },
    }
