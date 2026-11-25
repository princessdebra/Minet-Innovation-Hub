"""JSON shapes for the LMS.

One rule enforced here: `question_payload` never includes the correct answers.
Admin-facing question serialisation is a separate function with an explicit
name so it cannot be reached by accident from a learner route.
"""
from __future__ import annotations

from typing import Optional

from .lms_models import (Assessment, AssessmentAttempt, AssessmentQuestion, Certificate,
                         ContentBlock, Course, CourseModule, Enrollment, GenerationJob,
                         Lesson, MediaAsset, SourceMaterial)

ASSET_URL = "/api/lms/assets/{id}"


def _iso(value) -> Optional[str]:
    return value.isoformat() if value else None


def asset_brief(asset: Optional[MediaAsset]) -> Optional[dict]:
    if asset is None:
        return None
    return {
        "id": asset.id,
        "filename": asset.original_filename,
        "mime_type": asset.mime_type,
        "size_bytes": asset.size_bytes,
        "kind": asset.kind,
        "url": ASSET_URL.format(id=asset.id),
    }


def block_payload(block: ContentBlock, *, for_admin: bool = False) -> dict:
    data = dict(block.data or {})
    payload = {
        "id": block.id,
        "block_type": block.block_type,
        "title": block.title,
        "position": block.position,
        "data": data,
    }
    if for_admin:
        payload["needs_review"] = block.needs_review
        payload["import_note"] = block.import_note
        payload["meta"] = block.meta or {}
    return payload


def lesson_payload(lesson: Lesson, *, blocks: bool = False, for_admin: bool = False,
                   progress_status: Optional[str] = None) -> dict:
    payload = {
        "id": lesson.id,
        "module_id": lesson.module_id,
        "title": lesson.title,
        "description": lesson.description,
        "position": lesson.position,
        "lesson_type": lesson.lesson_type,
        "estimated_minutes": lesson.estimated_minutes,
        "objectives": lesson.objectives or [],
        "completion_rule": lesson.completion_rule,
    }
    if progress_status is not None:
        payload["status"] = progress_status
    if for_admin:
        payload["is_published"] = lesson.is_published
        payload["needs_review"] = lesson.needs_review
    if blocks:
        payload["blocks"] = [block_payload(b, for_admin=for_admin) for b in lesson.blocks]
    return payload


def module_payload(module: CourseModule, *, lessons: bool = True, for_admin: bool = False,
                   progress: Optional[dict[int, str]] = None) -> dict:
    payload = {
        "id": module.id,
        "course_id": module.course_id,
        "title": module.title,
        "description": module.description,
        "position": module.position,
        "estimated_minutes": module.estimated_minutes,
    }
    if for_admin:
        payload["is_published"] = module.is_published
    if lessons:
        payload["lessons"] = [
            lesson_payload(lsn, for_admin=for_admin,
                           progress_status=(progress or {}).get(lsn.id))
            for lsn in module.lessons
            if for_admin or lsn.is_published
        ]
    return payload


def course_card(course: Course, *, enrollment: Optional[Enrollment] = None,
                thumbnail: Optional[MediaAsset] = None, lesson_count: int = 0) -> dict:
    return {
        "id": course.id,
        "slug": course.slug,
        "title": course.title,
        "summary": course.summary,
        "category": course.category,
        "tags": course.tags or [],
        "difficulty": course.difficulty,
        "estimated_minutes": course.estimated_minutes,
        "origin": course.origin,
        "lesson_count": lesson_count,
        "thumbnail": asset_brief(thumbnail),
        "status": enrollment.status if enrollment else "not_started",
        "progress_percent": enrollment.progress_percent if enrollment else 0,
    }


def course_admin_payload(course: Course, *, thumbnail: Optional[MediaAsset] = None,
                         modules: bool = False) -> dict:
    payload = {
        "id": course.id,
        "slug": course.slug,
        "title": course.title,
        "summary": course.summary,
        "description": course.description,
        "objectives": course.objectives or [],
        "category": course.category,
        "tags": course.tags or [],
        "difficulty": course.difficulty,
        "target_audience": course.target_audience,
        "estimated_minutes": course.estimated_minutes,
        "status": course.status,
        "origin": course.origin,
        "ai_disclosure": course.ai_disclosure,
        "pass_requires_assessments": course.pass_requires_assessments,
        "version": course.version,
        "owner_id": course.owner_id,
        "thumbnail": asset_brief(thumbnail),
        "published_at": _iso(course.published_at),
        "created_at": _iso(course.created_at),
        "updated_at": _iso(course.updated_at),
    }
    if modules:
        payload["modules"] = [module_payload(m, for_admin=True) for m in course.modules]
    return payload


def material_payload(material: SourceMaterial) -> dict:
    return {
        "id": material.id,
        "course_id": material.course_id,
        "sensitivity": material.sensitivity,
        "openmaic_material_id": material.openmaic_material_id,
        "extraction_status": material.extraction_status,
        "created_at": _iso(material.created_at),
        "asset": asset_brief(material.asset),
    }


def job_payload(job: GenerationJob) -> dict:
    return {
        "id": job.id,
        "course_id": job.course_id,
        "status": job.status,
        "progress": job.progress,
        "step": job.step,
        "message": job.message,
        "instructions": job.instructions,
        "material_ids": job.material_ids or [],
        "attempt_count": job.attempt_count,
        "max_attempts": job.max_attempts,
        "last_error": job.last_error,
        "import_report": job.import_report,
        "openmaic_job_id": job.openmaic_job_id,
        "openmaic_classroom_id": job.openmaic_classroom_id,
        "requested_by_id": job.requested_by_id,
        "created_at": _iso(job.created_at),
        "started_at": _iso(job.started_at),
        "finished_at": _iso(job.finished_at),
    }


def question_payload(question: AssessmentQuestion) -> dict:
    """Learner-facing. Deliberately omits `correct` and `explanation`."""
    return {
        "id": question.id,
        "prompt": question.prompt,
        "kind": question.kind,
        "options": [{"id": o.get("id"), "text": o.get("text")}
                    for o in (question.options or [])],
        "marks": question.marks,
        "position": question.position,
    }


def question_admin_payload(question: AssessmentQuestion) -> dict:
    return {
        **question_payload(question),
        "correct": question.correct or [],
        "explanation": question.explanation,
        "is_ai_generated": question.is_ai_generated,
        "reviewed_by_id": question.reviewed_by_id,
    }


def assessment_payload(assessment: Assessment, *, for_admin: bool = False,
                       attempts_used: int = 0, best: Optional[AssessmentAttempt] = None) -> dict:
    payload = {
        "id": assessment.id,
        "course_id": assessment.course_id,
        "module_id": assessment.module_id,
        "lesson_id": assessment.lesson_id,
        "title": assessment.title,
        "instructions": assessment.instructions,
        "pass_percent": assessment.pass_percent,
        "max_attempts": assessment.max_attempts,
        "time_limit_minutes": assessment.time_limit_minutes,
        "is_required_for_completion": assessment.is_required_for_completion,
        "question_count": len(assessment.questions),
    }
    if for_admin:
        payload["is_published"] = assessment.is_published
        payload["needs_review"] = assessment.needs_review
        payload["questions"] = [question_admin_payload(q) for q in assessment.questions]
    else:
        payload["questions"] = [question_payload(q) for q in assessment.questions]
        payload["attempts_used"] = attempts_used
        payload["attempts_left"] = max(0, assessment.max_attempts - attempts_used)
        payload["best"] = attempt_payload(best) if best else None
    return payload


def attempt_payload(attempt: AssessmentAttempt, *, results: Optional[list] = None) -> dict:
    payload = {
        "id": attempt.id,
        "assessment_id": attempt.assessment_id,
        "attempt_number": attempt.attempt_number,
        "score": attempt.score,
        "max_score": attempt.max_score,
        "percent": attempt.percent,
        "passed": attempt.passed,
        "started_at": _iso(attempt.started_at),
        "submitted_at": _iso(attempt.submitted_at),
    }
    if results is not None:
        payload["results"] = results
    return payload


def certificate_payload(certificate: Certificate, *, verification_url: str = "") -> dict:
    return {
        "id": certificate.id,
        "course_id": certificate.course_id,
        "certificate_number": certificate.certificate_number,
        "certificate_type": certificate.certificate_type,
        "verification_code": certificate.verification_code,
        "verification_url": verification_url,
        "course_title": certificate.course_title,
        "recipient_name": certificate.recipient_name,
        "course_version": certificate.course_version,
        "score_percent": certificate.score_percent,
        "issued_at": _iso(certificate.issued_at),
        "revoked_at": _iso(certificate.revoked_at),
        "is_valid": certificate.is_valid,
        "download_url": f"/api/lms/certificates/{certificate.id}/pdf",
    }


def enrollment_payload(enrollment: Enrollment) -> dict:
    return {
        "id": enrollment.id,
        "course_id": enrollment.course_id,
        "status": enrollment.status,
        "progress_percent": enrollment.progress_percent,
        "seconds_spent": enrollment.seconds_spent,
        "enrolled_at": _iso(enrollment.enrolled_at),
        "started_at": _iso(enrollment.started_at),
        "last_accessed_at": _iso(enrollment.last_accessed_at),
        "completed_at": _iso(enrollment.completed_at),
    }
