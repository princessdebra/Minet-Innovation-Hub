"""Learning Management System tables.

Kept in a separate module from `models.py` so the original POC schema stays
readable, but they share the same `Base` and therefore the same metadata and
migrations. Anything that imports `app.models` for table registration must also
import this module -- `app.models_all` does that in one place.

Naming: every table is prefixed `lms_` so the LMS is easy to tell apart from the
innovation-portfolio tables it lives beside.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# ---------------------------------------------------------------------------
# Vocabularies. Stored as short strings rather than native ENUMs so that adding
# a value is a code change, not a migration.
# ---------------------------------------------------------------------------

COURSE_STATUSES = ("draft", "generating", "awaiting_review", "published", "archived")
JOB_STATUSES = ("draft", "queued", "processing", "generated", "importing", "imported",
                "failed", "cancelled")
JOB_ACTIVE_STATUSES = ("queued", "processing", "generated", "importing")
BLOCK_TYPES = ("rich_text", "slide", "image", "audio", "video", "document", "diagram",
               "key_takeaways", "notes", "knowledge_check", "external_reference",
               "html_fallback", "unsupported")
LESSON_TYPES = ("standard", "slides", "video", "reading", "assessment")
QUESTION_KINDS = ("single", "multiple", "truefalse", "short_answer")
PROGRESS_STATUSES = ("not_started", "in_progress", "completed")
CERTIFICATE_TYPES = ("completion", "assessed_competency")
SENSITIVITIES = ("public", "internal", "confidential")


class MediaAsset(Base):
    """Every file Minet owns: uploads, imported media, thumbnails, raw exports.

    Binary content lives on disk (or object storage later) via `storage_key`;
    only metadata is stored here.
    """
    __tablename__ = "lms_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(512))
    stored_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    mime_type: Mapped[str] = mapped_column(String(160))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(40), default="other")
    # "private"  -> admins only (source material, raw exports)
    # "course"   -> any user enrolled on / able to see the published course
    visibility: Mapped[str] = mapped_column(String(20), default="private")

    course_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("lms_courses.id", ondelete="SET NULL", use_alter=True,
                   name="fk_lms_assets_course"))
    lesson_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("lms_lessons.id", ondelete="SET NULL", use_alter=True,
                   name="fk_lms_assets_lesson"))
    content_block_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("lms_content_blocks.id", ondelete="SET NULL", use_alter=True,
                   name="fk_lms_assets_block"))
    uploaded_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Course(Base):
    __tablename__ = "lms_courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(String(400))
    objectives: Mapped[Optional[list]] = mapped_column(JSON)
    category: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON)
    difficulty: Mapped[str] = mapped_column(String(20), default="Foundation")
    target_audience: Mapped[Optional[str]] = mapped_column(String(300))
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=0)
    thumbnail_asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lms_assets.id", ondelete="SET NULL"))

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    origin: Mapped[str] = mapped_column(String(20), default="manual")  # manual | ai_generated
    ai_disclosure: Mapped[Optional[str]] = mapped_column(Text)
    pass_requires_assessments: Mapped[bool] = mapped_column(Boolean, default=True)

    version: Mapped[int] = mapped_column(Integer, default=1)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    published_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    modules: Mapped[list["CourseModule"]] = relationship(
        back_populates="course", order_by="CourseModule.position",
        cascade="all, delete-orphan")

    @property
    def is_visible_to_learners(self) -> bool:
        return self.status == "published"


class CourseModule(Base):
    __tablename__ = "lms_modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("lms_courses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    # "maic:<stageId>" for content imported from OpenMAIC. Lets a re-import
    # recognise what it already created instead of duplicating it.
    import_key: Mapped[Optional[str]] = mapped_column(String(190), index=True)

    course: Mapped[Course] = relationship(back_populates="modules")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="module", order_by="Lesson.position", cascade="all, delete-orphan")


class Lesson(Base):
    __tablename__ = "lms_lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("lms_modules.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)
    lesson_type: Mapped[str] = mapped_column(String(24), default="standard")
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=5)
    objectives: Mapped[Optional[list]] = mapped_column(JSON)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    # "view"       -> learner marks it complete
    # "assessment" -> the lesson's required assessment must be passed as well
    completion_rule: Mapped[str] = mapped_column(String(20), default="view")
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)

    module: Mapped[CourseModule] = relationship(back_populates="lessons")
    blocks: Mapped[list["ContentBlock"]] = relationship(
        back_populates="lesson", order_by="ContentBlock.position", cascade="all, delete-orphan")


class ContentBlock(Base):
    """One piece of a lesson. `data` carries the type-specific payload.

    Keeping the payload in JSON means new block types need no migration, while
    the columns beside it stay queryable.
    """
    __tablename__ = "lms_content_blocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lms_lessons.id", ondelete="CASCADE"), index=True)
    block_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[Optional[str]] = mapped_column(String(300))
    data: Mapped[Optional[dict]] = mapped_column(JSON)
    asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lms_assets.id", ondelete="SET NULL"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    meta: Mapped[Optional[dict]] = mapped_column(JSON)
    # Set by the importer when content could not be mapped cleanly. Never drop
    # content silently -- flag it and keep the original.
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    import_note: Mapped[Optional[str]] = mapped_column(String(400))

    lesson: Mapped[Lesson] = relationship(back_populates="blocks")


class SourceMaterial(Base):
    """An admin-uploaded document that feeds AI generation."""
    __tablename__ = "lms_source_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("lms_courses.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("lms_assets.id", ondelete="CASCADE"))
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    sensitivity: Mapped[str] = mapped_column(String(20), default="internal")
    openmaic_material_id: Mapped[Optional[str]] = mapped_column(String(190))
    extraction_status: Mapped[Optional[str]] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    asset: Mapped[MediaAsset] = relationship(foreign_keys=[asset_id])


class GenerationJob(Base):
    """One AI generation run, tracked by Minet from request to import.

    OpenMAIC prunes its own runs after 24h, so everything Minet needs is copied
    here as it happens.
    """
    __tablename__ = "lms_generation_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("lms_courses.id", ondelete="CASCADE"), index=True)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    instructions: Mapped[str] = mapped_column(Text)
    material_ids: Mapped[Optional[list]] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)

    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    step: Mapped[Optional[str]] = mapped_column(String(40))
    message: Mapped[Optional[str]] = mapped_column(String(500))

    openmaic_job_id: Mapped[Optional[str]] = mapped_column(String(190), index=True)
    openmaic_classroom_id: Mapped[Optional[str]] = mapped_column(String(190))
    openmaic_url: Mapped[Optional[str]] = mapped_column(String(500))

    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    import_report: Mapped[Optional[dict]] = mapped_column(JSON)
    export_asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lms_assets.id", ondelete="SET NULL"))

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    next_poll_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    @property
    def is_active(self) -> bool:
        return self.status in JOB_ACTIVE_STATUSES


class Enrollment(Base):
    __tablename__ = "lms_enrollments"
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_lms_enrollment"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("lms_courses.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="not_started")
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    seconds_spent: Mapped[int] = mapped_column(Integer, default=0)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    lesson_progress: Mapped[list["LessonProgress"]] = relationship(
        back_populates="enrollment", cascade="all, delete-orphan")


class LessonProgress(Base):
    __tablename__ = "lms_lesson_progress"
    __table_args__ = (UniqueConstraint("enrollment_id", "lesson_id", name="uq_lms_lesson_progress"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("lms_enrollments.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lms_lessons.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="not_started")
    seconds_spent: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    enrollment: Mapped[Enrollment] = relationship(back_populates="lesson_progress")


class Assessment(Base):
    __tablename__ = "lms_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("lms_courses.id", ondelete="CASCADE"), index=True)
    module_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lms_modules.id", ondelete="CASCADE"))
    lesson_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lms_lessons.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[Optional[str]] = mapped_column(Text)
    pass_percent: Mapped[int] = mapped_column(Integer, default=70)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    time_limit_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    is_required_for_completion: Mapped[bool] = mapped_column(Boolean, default=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    import_key: Mapped[Optional[str]] = mapped_column(String(190), index=True)

    questions: Mapped[list["AssessmentQuestion"]] = relationship(
        back_populates="assessment", order_by="AssessmentQuestion.position",
        cascade="all, delete-orphan")


class AssessmentQuestion(Base):
    __tablename__ = "lms_assessment_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("lms_assessments.id", ondelete="CASCADE"), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20), default="single")
    # [{"id": "a", "text": "..."}]
    options: Mapped[Optional[list]] = mapped_column(JSON)
    # ["a"] for choice kinds; ["accepted", "answers"] for short_answer
    correct: Mapped[Optional[list]] = mapped_column(JSON)
    marks: Mapped[int] = mapped_column(Integer, default=1)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    assessment: Mapped[Assessment] = relationship(back_populates="questions")


class AssessmentAttempt(Base):
    __tablename__ = "lms_assessment_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("lms_assessments.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    answers: Mapped[Optional[dict]] = mapped_column(JSON)
    score: Mapped[Optional[int]] = mapped_column(Integer)
    max_score: Mapped[Optional[int]] = mapped_column(Integer)
    percent: Mapped[Optional[int]] = mapped_column(Integer)
    passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Certificate(Base):
    __tablename__ = "lms_certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("lms_courses.id", ondelete="CASCADE"), index=True)
    certificate_type: Mapped[str] = mapped_column(String(30), default="completion")
    certificate_number: Mapped[str] = mapped_column(String(40), unique=True)
    verification_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    # Snapshots so a certificate still reads correctly if the course is edited.
    course_title: Mapped[str] = mapped_column(String(200))
    recipient_name: Mapped[str] = mapped_column(String(160))
    course_version: Mapped[int] = mapped_column(Integer, default=1)
    score_percent: Mapped[Optional[int]] = mapped_column(Integer)
    issued_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    issued_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    revoke_reason: Mapped[Optional[str]] = mapped_column(String(300))

    @property
    def is_valid(self) -> bool:
        return self.revoked_at is None


Index("ix_lms_course_status_category", Course.status, Course.category)
Index("ix_lms_job_status_poll", GenerationJob.status, GenerationJob.next_poll_at)
