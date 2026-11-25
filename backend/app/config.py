"""Runtime configuration for the LMS module.

Everything here is read from the environment (backend/.env). No secret is ever
sent to the frontend; `public_settings()` is the only thing the UI sees.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


# --- File storage ----------------------------------------------------------

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")  # local | s3 (s3 not yet implemented)
STORAGE_ROOT = Path(os.getenv("STORAGE_ROOT") or (BACKEND_ROOT / "var" / "storage"))

MAX_UPLOAD_BYTES = _int("MAX_UPLOAD_BYTES", 200 * 1024 * 1024)        # 200 MiB per file
MAX_ARCHIVE_BYTES = _int("MAX_ARCHIVE_BYTES", 500 * 1024 * 1024)      # 500 MiB per export
MAX_EXTRACTED_BYTES = _int("MAX_EXTRACTED_BYTES", 1024 * 1024 * 1024)  # 1 GiB unpacked
MAX_ARCHIVE_ENTRIES = _int("MAX_ARCHIVE_ENTRIES", 5000)

# --- OpenMAIC --------------------------------------------------------------
#
# OpenMAIC identifies callers by an owner cookie; there is no documented
# server-to-server API key (see docs/openmaic-integration-design.md 1.8).
# OPENMAIC_COOKIE therefore holds a session cookie captured from an
# administrator's browser against a single-owner instance, and
# OPENMAIC_ACCESS_CODE the site-wide gate. Both are secrets.

OPENMAIC_BASE_URL = (os.getenv("OPENMAIC_BASE_URL") or "").rstrip("/")
OPENMAIC_COOKIE = os.getenv("OPENMAIC_COOKIE", "")
OPENMAIC_ACCESS_CODE = os.getenv("OPENMAIC_ACCESS_CODE", "")
OPENMAIC_TIMEOUT_SECONDS = _int("OPENMAIC_TIMEOUT_SECONDS", 60)
OPENMAIC_UPLOAD_TIMEOUT_SECONDS = _int("OPENMAIC_UPLOAD_TIMEOUT_SECONDS", 300)
# OpenMAIC's own default is 2 active runs per owner.
OPENMAIC_MAX_ACTIVE_RUNS = _int("OPENMAIC_MAX_ACTIVE_RUNS", 2)
OPENMAIC_JOB_TIMEOUT_SECONDS = _int("OPENMAIC_JOB_TIMEOUT_SECONDS", 45 * 60)
OPENMAIC_POLL_SECONDS = _int("OPENMAIC_POLL_SECONDS", 15)

# --- Worker ----------------------------------------------------------------

WORKER_IDLE_SECONDS = _int("WORKER_IDLE_SECONDS", 5)

# --- Certificates ----------------------------------------------------------

CERTIFICATE_ORGANISATION = os.getenv("CERTIFICATE_ORGANISATION", "Minet")
CERTIFICATE_SIGNATORY = os.getenv("CERTIFICATE_SIGNATORY", "Head of Innovation")
CERTIFICATE_SIGNATORY_TITLE = os.getenv("CERTIFICATE_SIGNATORY_TITLE", "Minet Innovation Hub")
PUBLIC_BASE_URL = (os.getenv("PUBLIC_BASE_URL") or "http://localhost:5173").rstrip("/")

# --- Content policy --------------------------------------------------------

# Blocks generation from material classified at or above this level.
BLOCK_GENERATION_FOR_SENSITIVITY = {"confidential"}


def openmaic_configured() -> bool:
    """True when the integration has at least a base URL to talk to."""
    return bool(OPENMAIC_BASE_URL)


def public_settings() -> dict:
    """Non-secret configuration the admin UI may read."""
    return {
        "openmaic_configured": openmaic_configured(),
        "openmaic_base_url_set": bool(OPENMAIC_BASE_URL),
        "openmaic_credentials_set": bool(OPENMAIC_COOKIE or OPENMAIC_ACCESS_CODE),
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "max_archive_bytes": MAX_ARCHIVE_BYTES,
        "storage_backend": STORAGE_BACKEND,
        "certificate_organisation": CERTIFICATE_ORGANISATION,
    }
