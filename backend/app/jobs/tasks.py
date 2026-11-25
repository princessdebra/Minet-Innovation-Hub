"""The work a generation job actually does.

Deliberately written as plain functions over a Session so they can be driven by
the bundled polling worker now and by Celery/Dramatiq later without change.

The flow:
    queued -> processing (upload materials, start the run, poll)
           -> generated  (OpenMAIC finished)
           -> importing  -> imported          when structured content is readable
           -> generated  (awaiting export)    when it is not

That last branch is not a failure. OpenMAIC builds its export files in the
browser, so there is no server route to download them; the administrator
uploads the export to /api/lms/admin/courses/{id}/import and the job completes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .. import config
from ..importer.maic import MaicFormatError, import_document
from ..importer.media import Fetched, MediaFetchError
from ..importer.report import ImportReport
from ..integrations.openmaic import (OpenMAICAuthError, OpenMAICBusy, OpenMAICClient,
                                     OpenMAICError, OpenMAICNotConfigured)
from ..lms_models import Course, GenerationJob, MediaAsset, SourceMaterial
from ..lms_services import recalculate_course_duration
from ..storage import get_storage

log = logging.getLogger("minet.lms.jobs")

MANUAL_EXPORT_MESSAGE = (
    "Generation finished in OpenMAIC. Minet could not read the structured content "
    "automatically, which is expected for this OpenMAIC build: exports are produced "
    "in the browser. Open the classroom, export it, then upload the export file to "
    "this course to finish the import.")


def _fail(db: Session, job: GenerationJob, message: str, *, retryable: bool) -> None:
    job.attempt_count += 1
    job.last_error = message[:2000]
    if retryable and job.attempt_count < job.max_attempts:
        job.status = "queued"
        job.claimed_at = None
        job.next_poll_at = datetime.now() + timedelta(seconds=30 * job.attempt_count)
        job.message = f"Retrying after an error (attempt {job.attempt_count + 1} of {job.max_attempts})."
        log.warning("Job %s will retry: %s", job.id, message)
    else:
        job.status = "failed"
        job.finished_at = datetime.now()
        job.message = "Generation failed."
        course = db.get(Course, job.course_id)
        if course and course.status == "generating":
            course.status = "draft"
        log.error("Job %s failed: %s", job.id, message)
    db.commit()


def _upload_materials(db: Session, job: GenerationJob, client: OpenMAICClient) -> list[str]:
    """Push each source document to OpenMAIC, remembering its material id."""
    storage = get_storage()
    material_ids: list[str] = []
    materials = [db.get(SourceMaterial, mid) for mid in (job.material_ids or [])]

    for material in [m for m in materials if m and not m.deleted_at]:
        if material.openmaic_material_id:
            material_ids.append(material.openmaic_material_id)
            continue
        asset = db.get(MediaAsset, material.asset_id)
        if not asset or not storage.exists(asset.storage_key):
            raise OpenMAICError(
                f"Source material {material.id} is missing from storage.", retryable=False)
        payload = storage.read_bytes(asset.storage_key)
        uploaded = client.upload_material(
            filename=asset.original_filename, mime_type=asset.mime_type, payload=payload)
        material.openmaic_material_id = uploaded.material_id
        material.extraction_status = str(uploaded.extraction)[:40] if uploaded.extraction else None
        material_ids.append(uploaded.material_id)
        db.commit()
        log.info("Job %s uploaded material %s as %s", job.id, material.id, uploaded.material_id)
    return material_ids


def _build_requirement(db: Session, job: GenerationJob) -> str:
    """Turn the course brief plus the admin's instructions into one prompt."""
    course = db.get(Course, job.course_id)
    parts = [job.instructions.strip()]
    if course:
        parts.append(f"Course title: {course.title}.")
        if course.target_audience:
            parts.append(f"Audience: {course.target_audience}.")
        if course.difficulty:
            parts.append(f"Level: {course.difficulty}.")
        objectives = course.objectives or []
        if objectives:
            parts.append("Learning objectives: " + "; ".join(objectives[:10]) + ".")
    return "\n\n".join(p for p in parts if p)[:6000]


def start_job(db: Session, job: GenerationJob, client: OpenMAICClient) -> None:
    """Upload materials and ask OpenMAIC to start generating."""
    job.status = "processing"
    job.started_at = job.started_at or datetime.now()
    job.step = "uploading"
    job.progress = 5
    job.message = "Uploading source material to OpenMAIC."
    db.commit()

    material_ids = _upload_materials(db, job, client)

    job.step = "submitting"
    job.progress = 15
    job.message = "Asking OpenMAIC to generate the classroom."
    db.commit()

    view = client.start_generation(requirement=_build_requirement(db, job),
                                   material_ids=material_ids)
    job.openmaic_job_id = view.job_id
    job.progress = max(job.progress, view.progress or 0)
    job.step = view.step or "generating"
    job.message = view.message or "Generating."
    job.next_poll_at = datetime.now() + timedelta(seconds=config.OPENMAIC_POLL_SECONDS)
    db.commit()
    log.info("Job %s started OpenMAIC run %s", job.id, view.job_id)


def poll_job(db: Session, job: GenerationJob, client: OpenMAICClient) -> None:
    """Check an in-flight run and act on the result."""
    if job.started_at and (datetime.now() - job.started_at).total_seconds() > \
            config.OPENMAIC_JOB_TIMEOUT_SECONDS:
        _fail(db, job,
              f"The run exceeded the {config.OPENMAIC_JOB_TIMEOUT_SECONDS // 60} minute "
              "timeout and was abandoned.", retryable=False)
        return

    view = client.get_job(job.openmaic_job_id)
    job.step = view.step or job.step
    job.progress = max(job.progress, min(95, view.progress or 0))
    job.message = view.message or job.message
    job.next_poll_at = datetime.now() + timedelta(seconds=config.OPENMAIC_POLL_SECONDS)

    if view.status == "failed":
        db.commit()
        _fail(db, job, view.error or "OpenMAIC reported the run as failed.",
              retryable=bool(view.retryable))
        return

    if not view.done:
        db.commit()
        return

    job.status = "generated"
    job.openmaic_classroom_id = view.classroom_id
    job.openmaic_url = view.classroom_url
    job.progress = 70
    job.message = "Generation finished. Importing content."
    if view.warning:
        job.last_error = f"OpenMAIC warning: {view.warning}"
    db.commit()
    log.info("Job %s generated classroom %s", job.id, view.classroom_id)
    import_job(db, job, client)


def import_job(db: Session, job: GenerationJob, client: OpenMAICClient) -> None:
    """Try to pull structured content; fall back to asking for the export file."""
    course = db.get(Course, job.course_id)
    if course is None:
        _fail(db, job, "The course was deleted while the job was running.", retryable=False)
        return

    job.status = "importing"
    job.step = "importing"
    job.message = "Reading the generated classroom."
    db.commit()

    document = None
    if job.openmaic_classroom_id:
        try:
            document = client.fetch_classroom_document(job.openmaic_classroom_id)
        except OpenMAICError as exc:
            log.info("Job %s could not read a classroom document: %s", job.id, exc)

    if not document:
        job.status = "generated"
        job.step = "awaiting_export"
        job.progress = 70
        job.message = MANUAL_EXPORT_MESSAGE
        job.import_report = {"source": "none", "needs_review": True,
                             "warnings": [MANUAL_EXPORT_MESSAGE]}
        course.status = "awaiting_review"
        db.commit()
        log.info("Job %s needs a manual export upload", job.id)
        return

    report = ImportReport()

    def asset_source(ref: str) -> Fetched:
        """Download one `ast_...` asset through OpenMAIC's verified asset route."""
        try:
            payload, content_type = client.fetch_asset(ref)
        except OpenMAICAuthError:
            raise                      # credentials are wrong: fail the whole import
        except OpenMAICError as exc:
            raise MediaFetchError(str(exc)) from exc
        return Fetched(payload=payload, content_type=content_type)

    try:
        import_document(db, course, document, source=asset_source,
                        uploaded_by_id=job.requested_by_id, report=report,
                        origin="openmaic_api")
    except MaicFormatError as exc:
        db.rollback()
        log.warning("Job %s: the document was not in a recognised shape: %s", job.id, exc)
        job.status = "generated"
        job.step = "awaiting_export"
        job.message = MANUAL_EXPORT_MESSAGE
        job.import_report = {"source": "none", "needs_review": True,
                             "warnings": [f"Document not recognised: {exc}"]}
        course.status = "awaiting_review"
        db.commit()
        return
    except OpenMAICAuthError as exc:
        db.rollback()
        _fail(db, job, str(exc), retryable=False)
        return
    except Exception as exc:  # noqa: BLE001 - never leave a job in limbo
        db.rollback()
        log.exception("Job %s import failed", job.id)
        _fail(db, job, f"The generated content could not be imported: {exc}", retryable=False)
        return

    if report.already_imported:
        job.status = "imported"
        job.step = "completed"
        job.progress = 100
        job.message = "This classroom was already imported into the course; nothing was added."
        job.import_report = report.to_dict()
        job.finished_at = datetime.now()
        db.commit()
        return

    if report.lessons == 0:
        job.status = "generated"
        job.step = "awaiting_export"
        job.message = MANUAL_EXPORT_MESSAGE
        job.import_report = report.to_dict()
        course.status = "awaiting_review"
        db.commit()
        return

    recalculate_course_duration(db, course)
    course.status = "awaiting_review"
    course.origin = "ai_generated"
    job.status = "imported"
    job.step = "completed"
    job.progress = 100
    job.message = (f"Imported {report.lessons} lessons and {report.blocks} content blocks."
                   + (" Some content needs review." if report.needs_review else ""))
    job.import_report = report.to_dict()
    job.finished_at = datetime.now()
    db.commit()
    log.info("Job %s imported: %s", job.id, job.message)


def advance(db: Session, job: GenerationJob) -> None:
    """Move one job forward by one step. Never raises."""
    try:
        client = OpenMAICClient()
        if job.status == "queued":
            start_job(db, job, client)
        elif job.status == "processing" and job.openmaic_job_id:
            poll_job(db, job, client)
        elif job.status == "processing":
            start_job(db, job, client)
        elif job.status == "generated" and job.step != "awaiting_export":
            import_job(db, job, client)
    except OpenMAICBusy as exc:
        # Not the job's fault: wait and try again without burning an attempt.
        job.status = "queued"
        job.claimed_at = None
        job.message = "Waiting for a free generation slot in OpenMAIC."
        job.next_poll_at = datetime.now() + timedelta(seconds=60)
        db.commit()
        log.info("Job %s deferred: %s", job.id, exc)
    except OpenMAICNotConfigured as exc:
        _fail(db, job, str(exc), retryable=False)
    except OpenMAICError as exc:
        _fail(db, job, str(exc), retryable=exc.retryable)
    except Exception as exc:  # noqa: BLE001
        log.exception("Unexpected error advancing job %s", job.id)
        _fail(db, job, f"Unexpected error: {exc}", retryable=False)
