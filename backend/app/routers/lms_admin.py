"""AI Course Studio -- administrator endpoints.

Permissions are enforced on every route. Separately from roles, these routes
are the only way to reach unpublished content and source material; nothing
here is exposed through the learner API.
"""
from __future__ import annotations

import logging
import mimetypes
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..importer.archive import ArchiveError, validate_upload_size
from ..importer.mapper import import_archive
from ..importer.report import ImportReport
from ..importer.sanitize import sanitize_html, sanitizer_available
from ..integrations.openmaic import (OpenMAICClient, material_extension_supported)
from ..lms_models import (JOB_ACTIVE_STATUSES, Assessment, AssessmentQuestion, ContentBlock,
                          Course, CourseModule, GenerationJob, Lesson, MediaAsset,
                          SourceMaterial)
from ..lms_serializers import (asset_brief, course_admin_payload, job_payload,
                               material_payload, module_payload, lesson_payload,
                               assessment_payload)
from ..lms_services import (job_fingerprint, recalculate_course_duration, unique_slug)
from ..security import require_permission
from ..storage import get_storage, sanitize_filename

log = logging.getLogger("minet.lms.admin")
router = APIRouter(prefix="/api/lms/admin", tags=["lms-admin"])

DIFFICULTIES = ["Foundation", "Intermediate", "Advanced"]
SENSITIVITIES = ["public", "internal", "confidential"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _course(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    return course


def _module(db: Session, module_id: int) -> CourseModule:
    module = db.get(CourseModule, module_id)
    if not module:
        raise HTTPException(404, "Module not found")
    return module


def _lesson(db: Session, lesson_id: int) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    return lesson


def _thumbnail(db: Session, course: Course) -> Optional[MediaAsset]:
    return db.get(MediaAsset, course.thumbnail_asset_id) if course.thumbnail_asset_id else None


def _invalid(errors: dict) -> HTTPException:
    return HTTPException(422, {"errors": errors})


def _reorder(items, ordered_ids: list[int]) -> None:
    position = {item_id: index for index, item_id in enumerate(ordered_ids)}
    for item in items:
        if item.id in position:
            item.position = position[item.id]


# ---------------------------------------------------------------------------
# Settings and integration health
# ---------------------------------------------------------------------------

@router.get("/settings")
def settings(_=Depends(require_permission("course:edit"))):
    health = OpenMAICClient().health() if config.openmaic_configured() else {
        "reachable": False, "detail": "OPENMAIC_BASE_URL is not set."}
    return {
        **config.public_settings(),
        "openmaic": health,
        "html_sanitizer": "bleach" if sanitizer_available() else "plain-text fallback",
        "difficulties": DIFFICULTIES,
        "sensitivities": SENSITIVITIES,
        # Honest statement of what this OpenMAIC build can and cannot do.
        "capabilities": {
            "material_upload": True,
            "classroom_generation": True,
            "job_polling": True,
            "automatic_export_download": False,
            "structured_content_api": "unverified",
            "notes": [
                "OpenMAIC builds its .maic.zip / HTML / PPTX exports in the browser. "
                "There is no server route to download them, so an administrator must "
                "upload the export file to Minet after generation finishes.",
                "Run OpenMAIC with OWNER_SINGLE_USER=true so Minet needs no cookie. "
                "Without it OpenMAIC has no server-to-server API key and Minet falls "
                "back to the session cookie in OPENMAIC_COOKIE.",
            ],
        },
    }


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------

class CourseIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    summary: Optional[str] = Field(None, max_length=400)
    description: Optional[str] = None
    objectives: list[str] = Field(default_factory=list)
    category: Optional[str] = Field(None, max_length=80)
    tags: list[str] = Field(default_factory=list)
    difficulty: str = "Foundation"
    target_audience: Optional[str] = Field(None, max_length=300)
    estimated_minutes: int = 0
    pass_requires_assessments: bool = True


class CoursePatch(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    summary: Optional[str] = Field(None, max_length=400)
    description: Optional[str] = None
    objectives: Optional[list[str]] = None
    category: Optional[str] = Field(None, max_length=80)
    tags: Optional[list[str]] = None
    difficulty: Optional[str] = None
    target_audience: Optional[str] = Field(None, max_length=300)
    estimated_minutes: Optional[int] = None
    pass_requires_assessments: Optional[bool] = None
    ai_disclosure: Optional[str] = None


@router.get("/courses")
def list_courses(status: Optional[str] = None, category: Optional[str] = None,
                 search: Optional[str] = None, page: int = Query(1, ge=1),
                 per_page: int = Query(20, ge=1, le=100),
                 db: Session = Depends(get_db),
                 _=Depends(require_permission("course:edit"))):
    query = select(Course)
    if status:
        query = query.where(Course.status == status)
    if category:
        query = query.where(Course.category == category)
    if search and search.strip():
        like = f"%{search.strip()}%"
        query = query.where(or_(Course.title.like(like), Course.summary.like(like),
                                Course.description.like(like)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(db.scalars(query.order_by(Course.updated_at.desc())
                           .offset((page - 1) * per_page).limit(per_page)))

    lesson_counts = dict(db.execute(
        select(CourseModule.course_id, func.count(Lesson.id))
        .join(Lesson, Lesson.module_id == CourseModule.id)
        .group_by(CourseModule.course_id)).all())
    active_jobs = {row[0] for row in db.execute(
        select(GenerationJob.course_id).where(
            GenerationJob.status.in_(JOB_ACTIVE_STATUSES))).all()}

    return {
        "total": total, "page": page, "per_page": per_page,
        "courses": [{
            **course_admin_payload(course, thumbnail=_thumbnail(db, course)),
            "lesson_count": lesson_counts.get(course.id, 0),
            "has_active_job": course.id in active_jobs,
        } for course in rows],
        "categories": [c for (c,) in db.execute(
            select(Course.category).where(Course.category.is_not(None)).distinct()).all()],
    }


@router.post("/courses", status_code=201)
def create_course(payload: CourseIn, db: Session = Depends(get_db),
                  user=Depends(require_permission("course:create"))):
    if payload.difficulty not in DIFFICULTIES:
        raise _invalid({"difficulty": f"Choose one of: {', '.join(DIFFICULTIES)}."})
    course = Course(
        slug=unique_slug(db, payload.title),
        title=payload.title.strip(),
        summary=(payload.summary or "").strip() or None,
        description=payload.description,
        objectives=[o.strip() for o in payload.objectives if o.strip()],
        category=(payload.category or "").strip() or None,
        tags=[t.strip() for t in payload.tags if t.strip()],
        difficulty=payload.difficulty,
        target_audience=payload.target_audience,
        estimated_minutes=max(0, payload.estimated_minutes),
        pass_requires_assessments=payload.pass_requires_assessments,
        owner_id=user.id,
        status="draft",
        origin="manual",
    )
    db.add(course)
    db.commit()
    return course_admin_payload(course)


@router.get("/courses/{course_id}")
def get_course(course_id: int, db: Session = Depends(get_db),
               _=Depends(require_permission("course:edit"))):
    course = _course(db, course_id)
    payload = course_admin_payload(course, thumbnail=_thumbnail(db, course), modules=True)
    payload["materials"] = [material_payload(m) for m in db.scalars(
        select(SourceMaterial).where(SourceMaterial.course_id == course.id,
                                     SourceMaterial.deleted_at.is_(None))
        .order_by(SourceMaterial.id))]
    payload["jobs"] = [job_payload(j) for j in db.scalars(
        select(GenerationJob).where(GenerationJob.course_id == course.id)
        .order_by(GenerationJob.id.desc()).limit(20))]
    payload["assessments"] = [assessment_payload(a, for_admin=True) for a in db.scalars(
        select(Assessment).where(Assessment.course_id == course.id).order_by(Assessment.id))]
    payload["review"] = {
        "lessons_needing_review": db.scalar(
            select(func.count()).select_from(Lesson)
            .join(CourseModule, Lesson.module_id == CourseModule.id)
            .where(CourseModule.course_id == course.id, Lesson.needs_review.is_(True))) or 0,
        "blocks_needing_review": db.scalar(
            select(func.count()).select_from(ContentBlock)
            .join(Lesson, ContentBlock.lesson_id == Lesson.id)
            .join(CourseModule, Lesson.module_id == CourseModule.id)
            .where(CourseModule.course_id == course.id, ContentBlock.needs_review.is_(True))) or 0,
    }
    return payload


@router.patch("/courses/{course_id}")
def update_course(course_id: int, payload: CoursePatch, db: Session = Depends(get_db),
                  _=Depends(require_permission("course:edit"))):
    course = _course(db, course_id)
    data = payload.model_dump(exclude_unset=True)
    if "difficulty" in data and data["difficulty"] not in DIFFICULTIES:
        raise _invalid({"difficulty": f"Choose one of: {', '.join(DIFFICULTIES)}."})
    if "title" in data and data["title"]:
        course.title = data.pop("title").strip()
        course.slug = unique_slug(db, course.title, exclude_id=course.id)
    for field, value in data.items():
        if field in ("objectives", "tags") and value is not None:
            value = [v.strip() for v in value if v and v.strip()]
        setattr(course, field, value)
    db.commit()
    return course_admin_payload(course, thumbnail=_thumbnail(db, course))


@router.post("/courses/{course_id}/thumbnail")
def upload_thumbnail(course_id: int, file: UploadFile = File(...),
                     db: Session = Depends(get_db),
                     user=Depends(require_permission("course:edit"))):
    course = _course(db, course_id)
    filename = sanitize_filename(file.filename or "thumbnail")
    mime = file.content_type or mimetypes.guess_type(filename)[0] or ""
    if not mime.startswith("image/"):
        raise _invalid({"file": "The thumbnail must be an image."})
    storage = get_storage()
    try:
        stored = storage.save_stream(f"courses/{course.id}/thumbnail", filename, file.file,
                                     max_bytes=10 * 1024 * 1024)
    except ValueError as exc:
        raise _invalid({"file": str(exc)})
    asset = MediaAsset(
        original_filename=filename, stored_filename=stored.stored_filename,
        storage_key=stored.storage_key, mime_type=mime, size_bytes=stored.size_bytes,
        checksum=stored.checksum, kind="image", visibility="course",
        course_id=course.id, uploaded_by_id=user.id)
    db.add(asset)
    db.flush()
    course.thumbnail_asset_id = asset.id
    db.commit()
    return asset_brief(asset)


class PublishIn(BaseModel):
    approval_note: Optional[str] = Field(None, max_length=1000)
    acknowledged_ai_review: bool = False


@router.post("/courses/{course_id}/publish")
def publish_course(course_id: int, payload: PublishIn, db: Session = Depends(get_db),
                   user=Depends(require_permission("course:publish"))):
    course = _course(db, course_id)
    errors: dict[str, str] = {}
    lessons = db.scalar(
        select(func.count()).select_from(Lesson)
        .join(CourseModule, Lesson.module_id == CourseModule.id)
        .where(CourseModule.course_id == course.id, Lesson.is_published.is_(True))) or 0
    if lessons == 0:
        errors["modules"] = "Add at least one published lesson before publishing."
    if not (course.summary or course.description):
        errors["summary"] = "Add a summary so employees know what the course covers."
    if course.origin == "ai_generated" and not payload.acknowledged_ai_review:
        errors["acknowledged_ai_review"] = (
            "Confirm you have reviewed the AI-generated content for accuracy and "
            "that it contains no confidential material.")
    if db.scalar(select(func.count()).select_from(GenerationJob)
                 .where(GenerationJob.course_id == course.id,
                        GenerationJob.status.in_(JOB_ACTIVE_STATUSES))):
        errors["generation"] = "A generation job is still running for this course."
    broken = [b for b in db.scalars(
        select(ContentBlock).join(Lesson, ContentBlock.lesson_id == Lesson.id)
        .join(CourseModule, Lesson.module_id == CourseModule.id)
        .where(CourseModule.course_id == course.id, Lesson.is_published.is_(True)))
        if (b.meta or {}).get("broken_media") or (b.data or {}).get("broken_media")]
    if broken:
        errors["media"] = (
            f"{len(broken)} content block(s) reference media that failed to import. "
            "Replace or delete them in the Content tab before publishing.")
    if errors:
        raise _invalid(errors)

    recalculate_course_duration(db, course)
    if course.published_at is not None:
        course.version += 1
    course.status = "published"
    course.published_at = datetime.now()
    course.published_by_id = user.id
    course.archived_at = None
    if course.origin == "ai_generated" and not course.ai_disclosure:
        course.ai_disclosure = (
            f"Parts of this course were generated with AI and reviewed by "
            f"{user.name} on {datetime.now():%d %B %Y}.")
    db.commit()
    log.info("Course %s published by user %s (version %s)", course.id, user.id, course.version)
    return course_admin_payload(course, thumbnail=_thumbnail(db, course))


@router.post("/courses/{course_id}/unpublish")
def unpublish_course(course_id: int, db: Session = Depends(get_db),
                     _=Depends(require_permission("course:publish"))):
    course = _course(db, course_id)
    course.status = "awaiting_review" if course.published_at else "draft"
    db.commit()
    return course_admin_payload(course)


@router.post("/courses/{course_id}/archive")
def archive_course(course_id: int, db: Session = Depends(get_db),
                   _=Depends(require_permission("course:archive"))):
    course = _course(db, course_id)
    course.status = "archived"
    course.archived_at = datetime.now()
    db.commit()
    return course_admin_payload(course)


# ---------------------------------------------------------------------------
# Structure: modules, lessons, blocks
# ---------------------------------------------------------------------------

class ModuleIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    estimated_minutes: int = 0
    is_published: bool = True


@router.post("/courses/{course_id}/modules", status_code=201)
def create_module(course_id: int, payload: ModuleIn, db: Session = Depends(get_db),
                  _=Depends(require_permission("course:edit"))):
    course = _course(db, course_id)
    module = CourseModule(course_id=course.id, title=payload.title.strip(),
                          description=payload.description,
                          estimated_minutes=max(0, payload.estimated_minutes),
                          is_published=payload.is_published,
                          position=len(course.modules))
    db.add(module)
    db.commit()
    return module_payload(module, for_admin=True)


@router.patch("/modules/{module_id}")
def update_module(module_id: int, payload: ModuleIn, db: Session = Depends(get_db),
                  _=Depends(require_permission("course:edit"))):
    module = _module(db, module_id)
    module.title = payload.title.strip()
    module.description = payload.description
    module.estimated_minutes = max(0, payload.estimated_minutes)
    module.is_published = payload.is_published
    db.commit()
    return module_payload(module, for_admin=True)


@router.delete("/modules/{module_id}", status_code=204)
def delete_module(module_id: int, db: Session = Depends(get_db),
                  _=Depends(require_permission("course:edit"))):
    module = _module(db, module_id)
    db.delete(module)
    db.commit()


class ReorderIn(BaseModel):
    ordered_ids: list[int]


@router.post("/courses/{course_id}/modules/reorder")
def reorder_modules(course_id: int, payload: ReorderIn, db: Session = Depends(get_db),
                    _=Depends(require_permission("course:edit"))):
    course = _course(db, course_id)
    _reorder(course.modules, payload.ordered_ids)
    db.commit()
    db.refresh(course)
    return [module_payload(m, lessons=False, for_admin=True) for m in course.modules]


class LessonIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    lesson_type: str = "standard"
    estimated_minutes: int = 5
    objectives: list[str] = Field(default_factory=list)
    is_published: bool = True
    completion_rule: Literal["view", "assessment"] = "view"
    needs_review: Optional[bool] = None


@router.post("/modules/{module_id}/lessons", status_code=201)
def create_lesson(module_id: int, payload: LessonIn, db: Session = Depends(get_db),
                  _=Depends(require_permission("course:edit"))):
    module = _module(db, module_id)
    lesson = Lesson(module_id=module.id, title=payload.title.strip(),
                    description=payload.description, lesson_type=payload.lesson_type,
                    estimated_minutes=max(1, payload.estimated_minutes),
                    objectives=[o.strip() for o in payload.objectives if o.strip()],
                    is_published=payload.is_published,
                    completion_rule=payload.completion_rule,
                    position=len(module.lessons))
    db.add(lesson)
    db.commit()
    return lesson_payload(lesson, blocks=True, for_admin=True)


@router.get("/lessons/{lesson_id}")
def get_lesson(lesson_id: int, db: Session = Depends(get_db),
               _=Depends(require_permission("course:edit"))):
    """A lesson with its blocks, regardless of publication state."""
    lesson = _lesson(db, lesson_id)
    module = _module(db, lesson.module_id)
    return {"lesson": lesson_payload(lesson, blocks=True, for_admin=True),
            "module": {"id": module.id, "title": module.title},
            "course_id": module.course_id}


@router.patch("/lessons/{lesson_id}")
def update_lesson(lesson_id: int, payload: LessonIn, db: Session = Depends(get_db),
                  _=Depends(require_permission("course:edit"))):
    lesson = _lesson(db, lesson_id)
    lesson.title = payload.title.strip()
    lesson.description = payload.description
    lesson.lesson_type = payload.lesson_type
    lesson.estimated_minutes = max(1, payload.estimated_minutes)
    lesson.objectives = [o.strip() for o in payload.objectives if o.strip()]
    lesson.is_published = payload.is_published
    lesson.completion_rule = payload.completion_rule
    if payload.needs_review is not None:
        lesson.needs_review = payload.needs_review
    db.commit()
    return lesson_payload(lesson, blocks=True, for_admin=True)


@router.delete("/lessons/{lesson_id}", status_code=204)
def delete_lesson(lesson_id: int, db: Session = Depends(get_db),
                  _=Depends(require_permission("course:edit"))):
    db.delete(_lesson(db, lesson_id))
    db.commit()


@router.post("/modules/{module_id}/lessons/reorder")
def reorder_lessons(module_id: int, payload: ReorderIn, db: Session = Depends(get_db),
                    _=Depends(require_permission("course:edit"))):
    module = _module(db, module_id)
    _reorder(module.lessons, payload.ordered_ids)
    db.commit()
    db.refresh(module)
    return module_payload(module, for_admin=True)


class BlockIn(BaseModel):
    block_type: str
    title: Optional[str] = Field(None, max_length=300)
    data: dict = Field(default_factory=dict)
    asset_id: Optional[int] = None
    needs_review: Optional[bool] = None


def _clean_block_data(block_type: str, data: dict) -> dict:
    """Sanitise anything that will be rendered as HTML."""
    cleaned = dict(data or {})
    if "html" in cleaned and isinstance(cleaned["html"], str):
        cleaned["html"] = sanitize_html(cleaned["html"])
    if block_type == "key_takeaways":
        items = cleaned.get("items") or []
        cleaned["items"] = [str(i)[:500] for i in items if str(i).strip()][:20]
    return cleaned


@router.post("/lessons/{lesson_id}/blocks", status_code=201)
def create_block(lesson_id: int, payload: BlockIn, db: Session = Depends(get_db),
                 _=Depends(require_permission("course:edit"))):
    lesson = _lesson(db, lesson_id)
    block = ContentBlock(lesson_id=lesson.id, block_type=payload.block_type,
                         title=payload.title, data=_clean_block_data(payload.block_type,
                                                                     payload.data),
                         asset_id=payload.asset_id, position=len(lesson.blocks),
                         needs_review=bool(payload.needs_review))
    db.add(block)
    db.commit()
    return {"id": block.id}


@router.patch("/blocks/{block_id}")
def update_block(block_id: int, payload: BlockIn, db: Session = Depends(get_db),
                 _=Depends(require_permission("course:edit"))):
    block = db.get(ContentBlock, block_id)
    if not block:
        raise HTTPException(404, "Content block not found")
    block.block_type = payload.block_type
    block.title = payload.title
    block.data = _clean_block_data(payload.block_type, payload.data)
    block.asset_id = payload.asset_id
    if payload.needs_review is not None:
        block.needs_review = payload.needs_review
        if not payload.needs_review:
            block.import_note = None
    db.commit()
    return {"id": block.id}


@router.delete("/blocks/{block_id}", status_code=204)
def delete_block(block_id: int, db: Session = Depends(get_db),
                 _=Depends(require_permission("course:edit"))):
    block = db.get(ContentBlock, block_id)
    if not block:
        raise HTTPException(404, "Content block not found")
    db.delete(block)
    db.commit()


@router.post("/lessons/{lesson_id}/blocks/reorder")
def reorder_blocks(lesson_id: int, payload: ReorderIn, db: Session = Depends(get_db),
                   _=Depends(require_permission("course:edit"))):
    lesson = _lesson(db, lesson_id)
    _reorder(lesson.blocks, payload.ordered_ids)
    db.commit()
    db.refresh(lesson)
    return lesson_payload(lesson, blocks=True, for_admin=True)


# ---------------------------------------------------------------------------
# Source materials
# ---------------------------------------------------------------------------

@router.post("/courses/{course_id}/materials", status_code=201)
def upload_material(course_id: int, file: UploadFile = File(...),
                    sensitivity: str = Form("internal"),
                    db: Session = Depends(get_db),
                    user=Depends(require_permission("course:material:upload"))):
    course = _course(db, course_id)
    if sensitivity not in SENSITIVITIES:
        raise _invalid({"sensitivity": f"Choose one of: {', '.join(SENSITIVITIES)}."})
    filename = sanitize_filename(file.filename or "material")
    if not material_extension_supported(filename):
        raise _invalid({"file": (
            "OpenMAIC does not accept this file type. Supported: PDF, PPTX, DOCX, XLSX, "
            "PNG, JPEG, WEBP, TXT, MD, CSV, MP4, MOV, WEBM, MP3, WAV, M4A, AAC.")})
    storage = get_storage()
    try:
        stored = storage.save_stream(f"courses/{course.id}/materials", filename, file.file)
    except ValueError as exc:
        raise _invalid({"file": str(exc)})

    asset = MediaAsset(
        original_filename=filename, stored_filename=stored.stored_filename,
        storage_key=stored.storage_key,
        mime_type=file.content_type or mimetypes.guess_type(filename)[0]
        or "application/octet-stream",
        size_bytes=stored.size_bytes, checksum=stored.checksum, kind="source",
        visibility="private", course_id=course.id, uploaded_by_id=user.id)
    db.add(asset)
    db.flush()
    material = SourceMaterial(course_id=course.id, asset_id=asset.id,
                              uploaded_by_id=user.id, sensitivity=sensitivity)
    db.add(material)
    db.commit()
    return material_payload(material)


@router.get("/courses/{course_id}/materials")
def list_materials(course_id: int, db: Session = Depends(get_db),
                   _=Depends(require_permission("course:material:upload"))):
    _course(db, course_id)
    return [material_payload(m) for m in db.scalars(
        select(SourceMaterial).where(SourceMaterial.course_id == course_id,
                                     SourceMaterial.deleted_at.is_(None))
        .order_by(SourceMaterial.id))]


@router.delete("/materials/{material_id}", status_code=204)
def delete_material(material_id: int, db: Session = Depends(get_db),
                    _=Depends(require_permission("course:material:upload"))):
    material = db.get(SourceMaterial, material_id)
    if not material or material.deleted_at:
        raise HTTPException(404, "Material not found")
    material.deleted_at = datetime.now()
    asset = db.get(MediaAsset, material.asset_id)
    if asset:
        asset.deleted_at = datetime.now()
        get_storage().delete(asset.storage_key)
    db.commit()


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

class GenerateIn(BaseModel):
    instructions: str = Field(min_length=10, max_length=4000)
    material_ids: list[int] = Field(default_factory=list)


@router.post("/courses/{course_id}/generate", status_code=202)
def start_generation(course_id: int, payload: GenerateIn, db: Session = Depends(get_db),
                     user=Depends(require_permission("course:generate"))):
    course = _course(db, course_id)
    if not config.openmaic_configured():
        raise HTTPException(503, (
            "OpenMAIC is not configured. Set OPENMAIC_BASE_URL (and OPENMAIC_COOKIE) in "
            "backend/.env, then try again."))

    materials = list(db.scalars(select(SourceMaterial).where(
        SourceMaterial.id.in_(payload.material_ids or [-1]),
        SourceMaterial.course_id == course.id,
        SourceMaterial.deleted_at.is_(None))))
    if len(materials) != len(set(payload.material_ids)):
        raise _invalid({"material_ids": "One or more materials do not belong to this course."})

    blocked = [m for m in materials if m.sensitivity in config.BLOCK_GENERATION_FOR_SENSITIVITY]
    if blocked:
        raise _invalid({"material_ids": (
            f"{len(blocked)} material(s) are classified confidential. Confidential "
            "documents are not sent to an external AI provider. Reclassify them or "
            "configure a self-hosted model in OpenMAIC.")})

    fingerprint = job_fingerprint(course_id=course.id, instructions=payload.instructions,
                                  material_ids=[m.id for m in materials])
    duplicate = db.scalar(select(GenerationJob).where(
        GenerationJob.fingerprint == fingerprint,
        GenerationJob.status.in_(JOB_ACTIVE_STATUSES)))
    if duplicate:
        raise HTTPException(409, {
            "message": "An identical generation is already running for this course.",
            "job_id": duplicate.id})

    active = db.scalar(select(func.count()).select_from(GenerationJob)
                       .where(GenerationJob.status.in_(JOB_ACTIVE_STATUSES))) or 0

    job = GenerationJob(
        course_id=course.id, requested_by_id=user.id,
        instructions=payload.instructions.strip(),
        material_ids=[m.id for m in materials],
        fingerprint=fingerprint, status="queued",
        message="Queued. Waiting for a generation slot."
        if active >= config.OPENMAIC_MAX_ACTIVE_RUNS else "Queued.")
    db.add(job)
    course.status = "generating"
    course.origin = "ai_generated"
    db.commit()
    log.info("Queued generation job %s for course %s", job.id, course.id)
    return job_payload(job)


@router.get("/generation-jobs")
def list_jobs(course_id: Optional[int] = None, status: Optional[str] = None,
              page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=100),
              db: Session = Depends(get_db),
              _=Depends(require_permission("course:generate"))):
    query = select(GenerationJob)
    if course_id:
        query = query.where(GenerationJob.course_id == course_id)
    if status:
        query = query.where(GenerationJob.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(GenerationJob.id.desc())
                      .offset((page - 1) * per_page).limit(per_page))
    return {"total": total, "page": page, "per_page": per_page,
            "jobs": [job_payload(j) for j in rows]}


@router.get("/generation-jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db),
            _=Depends(require_permission("course:generate"))):
    job = db.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(404, "Generation job not found")
    return job_payload(job)


@router.post("/generation-jobs/{job_id}/retry")
def retry_job(job_id: int, db: Session = Depends(get_db),
              _=Depends(require_permission("course:generate"))):
    job = db.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(404, "Generation job not found")
    if job.status not in ("failed", "cancelled"):
        raise HTTPException(409, "Only a failed or cancelled job can be retried.")
    job.status = "queued"
    job.attempt_count = 0
    job.last_error = None
    job.message = "Re-queued."
    job.progress = 0
    job.claimed_at = None
    job.finished_at = None
    db.commit()
    return job_payload(job)


@router.post("/generation-jobs/{job_id}/cancel")
def cancel_job(job_id: int, db: Session = Depends(get_db),
               _=Depends(require_permission("course:generate"))):
    job = db.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(404, "Generation job not found")
    if job.status not in JOB_ACTIVE_STATUSES:
        raise HTTPException(409, "This job is no longer running.")
    job.status = "cancelled"
    job.message = "Cancelled by an administrator."
    job.finished_at = datetime.now()
    course = db.get(Course, job.course_id)
    if course and course.status == "generating":
        course.status = "draft"
    db.commit()
    return job_payload(job)


# ---------------------------------------------------------------------------
# Import (manual export upload -- the reliable path)
# ---------------------------------------------------------------------------

@router.post("/courses/{course_id}/import", status_code=201)
def import_export_archive(course_id: int, file: UploadFile = File(...),
                          job_id: Optional[int] = Form(None),
                          replace: bool = Form(False),
                          db: Session = Depends(get_db),
                          user=Depends(require_permission("course:import"))):
    """Import an OpenMAIC export archive (.maic.zip or any classroom ZIP).

    OpenMAIC builds exports in the browser, so this upload -- not an automated
    download -- is how generated content reaches Minet.
    """
    course = _course(db, course_id)
    filename = sanitize_filename(file.filename or "export.zip")
    storage = get_storage()
    try:
        stored = storage.save_stream(f"courses/{course.id}/exports", filename, file.file,
                                     max_bytes=config.MAX_ARCHIVE_BYTES)
        validate_upload_size(stored.size_bytes)
    except (ValueError, ArchiveError) as exc:
        raise _invalid({"file": str(exc)})

    # The original export is preserved for recovery, reprocessing and audit.
    export_asset = MediaAsset(
        original_filename=filename, stored_filename=stored.stored_filename,
        storage_key=stored.storage_key, mime_type="application/zip",
        size_bytes=stored.size_bytes, checksum=stored.checksum, kind="export",
        visibility="private", course_id=course.id, uploaded_by_id=user.id)
    db.add(export_asset)
    db.flush()

    report = ImportReport()
    try:
        import_archive(db, course, storage.path(stored.storage_key),
                       uploaded_by_id=user.id, report=report, replace=replace)
    except ArchiveError as exc:
        db.rollback()
        raise _invalid({"file": str(exc)})
    except Exception as exc:  # noqa: BLE001 - surface the real reason to the admin
        db.rollback()
        log.exception("Import failed for course %s", course.id)
        raise HTTPException(500, f"The export could not be imported: {exc}")

    course.status = "awaiting_review"
    course.origin = "ai_generated"
    recalculate_course_duration(db, course)

    if job_id:
        job = db.get(GenerationJob, job_id)
        if job and job.course_id == course.id:
            job.status = "imported"
            job.import_report = report.to_dict()
            job.export_asset_id = export_asset.id
            job.finished_at = datetime.now()
            job.progress = 100
            job.message = "Export imported."
    db.commit()
    log.info("Imported export into course %s: %s", course.id, report.to_dict())
    return {"course": course_admin_payload(course, modules=True),
            "report": report.to_dict(),
            "export_asset": asset_brief(export_asset)}


@router.get("/courses/{course_id}/preview")
def preview_course(course_id: int, db: Session = Depends(get_db),
                   _=Depends(require_permission("course:edit"))):
    """Exactly what a learner would see, without publishing."""
    course = _course(db, course_id)
    return {
        "course": course_admin_payload(course, thumbnail=_thumbnail(db, course)),
        "modules": [module_payload(m, for_admin=False) for m in course.modules
                    if m.is_published],
        "preview": True,
    }


# ---------------------------------------------------------------------------
# Assessments
# ---------------------------------------------------------------------------

class QuestionIn(BaseModel):
    id: Optional[int] = None
    prompt: str = Field(min_length=1)
    kind: Literal["single", "multiple", "truefalse", "short_answer"] = "single"
    options: list[dict] = Field(default_factory=list)
    correct: list[str] = Field(default_factory=list)
    marks: int = 1
    explanation: Optional[str] = None


class AssessmentIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    instructions: Optional[str] = None
    module_id: Optional[int] = None
    lesson_id: Optional[int] = None
    pass_percent: int = Field(70, ge=1, le=100)
    max_attempts: int = Field(3, ge=1, le=20)
    time_limit_minutes: Optional[int] = Field(None, ge=1, le=600)
    is_required_for_completion: bool = True
    is_published: bool = False
    questions: list[QuestionIn] = Field(default_factory=list)


def _apply_assessment(db: Session, assessment: Assessment, payload: AssessmentIn,
                      user_id: int) -> None:
    assessment.title = payload.title.strip()
    assessment.instructions = payload.instructions
    assessment.module_id = payload.module_id
    assessment.lesson_id = payload.lesson_id
    assessment.pass_percent = payload.pass_percent
    assessment.max_attempts = payload.max_attempts
    assessment.time_limit_minutes = payload.time_limit_minutes
    assessment.is_required_for_completion = payload.is_required_for_completion
    assessment.is_published = payload.is_published

    errors: dict[str, str] = {}
    for index, question in enumerate(payload.questions):
        if question.kind in ("single", "multiple", "truefalse") and not question.correct:
            errors[f"questions.{index}.correct"] = "Mark at least one correct option."
        if question.kind in ("single", "truefalse") and len(question.correct) > 1:
            errors[f"questions.{index}.correct"] = "This question type takes one answer."
        if question.kind in ("single", "multiple") and len(question.options) < 2:
            errors[f"questions.{index}.options"] = "Add at least two options."
    if errors:
        raise _invalid(errors)

    assessment.questions.clear()
    db.flush()
    for position, question in enumerate(payload.questions):
        assessment.questions.append(AssessmentQuestion(
            prompt=question.prompt.strip(), kind=question.kind,
            options=[{"id": str(o.get("id") or chr(97 + i)), "text": str(o.get("text") or "")}
                     for i, o in enumerate(question.options)],
            correct=[str(c) for c in question.correct],
            marks=max(1, question.marks), explanation=question.explanation,
            position=position, is_ai_generated=False, reviewed_by_id=user_id))
    assessment.needs_review = False


@router.post("/courses/{course_id}/assessments", status_code=201)
def create_assessment(course_id: int, payload: AssessmentIn, db: Session = Depends(get_db),
                      user=Depends(require_permission("assessment:manage"))):
    course = _course(db, course_id)
    assessment = Assessment(course_id=course.id, title=payload.title)
    db.add(assessment)
    db.flush()
    _apply_assessment(db, assessment, payload, user.id)
    db.commit()
    return assessment_payload(assessment, for_admin=True)


@router.put("/assessments/{assessment_id}")
def update_assessment(assessment_id: int, payload: AssessmentIn,
                      db: Session = Depends(get_db),
                      user=Depends(require_permission("assessment:manage"))):
    assessment = db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    _apply_assessment(db, assessment, payload, user.id)
    db.commit()
    return assessment_payload(assessment, for_admin=True)


@router.delete("/assessments/{assessment_id}", status_code=204)
def delete_assessment(assessment_id: int, db: Session = Depends(get_db),
                      _=Depends(require_permission("assessment:manage"))):
    assessment = db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    db.delete(assessment)
    db.commit()
