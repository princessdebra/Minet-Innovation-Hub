"""Background worker for AI generation jobs.

Run it beside the API:

    cd backend
    .venv\\Scripts\\python -m app.jobs.worker        (Windows)
    .venv/bin/python -m app.jobs.worker             (macOS / Linux)

Jobs are claimed from MySQL with `SELECT ... FOR UPDATE SKIP LOCKED`, so
several workers can run safely without Redis or a broker. The same task
functions move to Celery or Dramatiq unchanged when the deployment justifies
it -- see docs/openmaic-integration-design.md 3.6.
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from .. import config
from ..db import SessionLocal
from ..lms_models import JOB_ACTIVE_STATUSES, GenerationJob
from . import tasks

log = logging.getLogger("minet.lms.worker")

CLAIMABLE = ("queued", "processing", "generated")
STALE_CLAIM_MINUTES = 10

_running = True
_skip_locked_supported = True


def _stop(signum, _frame):  # pragma: no cover - signal path
    global _running
    log.info("Signal %s received; finishing the current job then stopping.", signum)
    _running = False


def claim_job(db: Session) -> GenerationJob | None:
    """Take one job, skipping rows another worker holds."""
    now = datetime.now()
    stale = now - timedelta(minutes=STALE_CLAIM_MINUTES)
    query = (select(GenerationJob)
             .where(GenerationJob.status.in_(CLAIMABLE),
                    GenerationJob.step.is_distinct_from("awaiting_export"),
                    (GenerationJob.next_poll_at.is_(None))
                    | (GenerationJob.next_poll_at <= now),
                    (GenerationJob.claimed_at.is_(None))
                    | (GenerationJob.claimed_at <= stale))
             .order_by(GenerationJob.claimed_at.is_(None).desc(), GenerationJob.id)
             .limit(1))
    global _skip_locked_supported
    job = None
    if _skip_locked_supported:
        try:
            job = db.scalar(query.with_for_update(skip_locked=True))
        except (OperationalError, ProgrammingError):
            # MariaDB (the XAMPP default) and MySQL before 8.0 have no
            # SKIP LOCKED. Fall back to a plain read, which is correct for the
            # single-worker deployment this ships with. Run more than one
            # worker only on MySQL 8+.
            db.rollback()
            _skip_locked_supported = False
            log.warning("This database does not support SELECT ... SKIP LOCKED. "
                        "Falling back to unlocked claims -- run only one worker "
                        "process against it.")
    if job is None and not _skip_locked_supported:
        job = db.scalar(query)
    if job is None:
        db.rollback()
        return None

    running = db.scalar(
        select(GenerationJob)
        .where(GenerationJob.status == "processing",
               GenerationJob.openmaic_job_id.is_not(None),
               GenerationJob.id != job.id)
        .limit(config.OPENMAIC_MAX_ACTIVE_RUNS))
    if job.status == "queued" and not job.openmaic_job_id and running is not None:
        active = db.query(GenerationJob).filter(
            GenerationJob.status == "processing",
            GenerationJob.openmaic_job_id.is_not(None)).count()
        if active >= config.OPENMAIC_MAX_ACTIVE_RUNS:
            job.message = (f"Queued. OpenMAIC allows {config.OPENMAIC_MAX_ACTIVE_RUNS} "
                           "concurrent generations.")
            job.next_poll_at = datetime.now() + timedelta(seconds=30)
            db.commit()
            return None

    job.claimed_at = now
    db.commit()
    return job


def tick() -> bool:
    """One iteration. Returns True when a job was handled."""
    with SessionLocal() as db:
        job = claim_job(db)
        if job is None:
            return False
        log.info("Working job %s (course %s, status %s)", job.id, job.course_id, job.status)
        tasks.advance(db, job)
        if job.status not in JOB_ACTIVE_STATUSES or job.step == "awaiting_export":
            job.claimed_at = None
            db.commit()
        return True


def run() -> None:  # pragma: no cover - the loop itself
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)-7s %(name)s  %(message)s")
    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)

    if not config.openmaic_configured():
        log.warning("OPENMAIC_BASE_URL is not set. The worker will run, but every job "
                    "will fail until the integration is configured.")
    log.info("Worker started. Polling every %ss.", config.WORKER_IDLE_SECONDS)

    while _running:
        try:
            if not tick():
                time.sleep(config.WORKER_IDLE_SECONDS)
        except KeyboardInterrupt:
            break
        except Exception:
            log.exception("Worker iteration failed; continuing.")
            time.sleep(config.WORKER_IDLE_SECONDS)
    log.info("Worker stopped.")


if __name__ == "__main__":  # pragma: no cover
    run()
    sys.exit(0)
