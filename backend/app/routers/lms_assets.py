"""Authenticated delivery of learning media.

Rules:
  * `private` assets (source documents, raw exports) are admin-only.
  * `course` assets are served only while their course is published, except to
    an administrator previewing a draft.
  * Content-Disposition is always `inline`/`attachment` with a safe filename,
    and a restrictive CSP is attached so a stored HTML artefact cannot act on
    Minet's origin even if one is ever served directly.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..lms_models import Course, MediaAsset
from ..security import get_current_user, has_permission
from ..storage import get_storage

router = APIRouter(prefix="/api/lms", tags=["lms-assets"])

INLINE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml",
                "audio/mpeg", "audio/wav", "audio/mp4", "audio/aac", "audio/ogg",
                "video/mp4", "video/webm", "application/pdf"}

SAFE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; img-src 'self'; media-src 'self'; "
                               "style-src 'unsafe-inline'; sandbox",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "private, max-age=300, must-revalidate",
}


@router.get("/assets/{asset_id}")
def get_asset(asset_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    asset = db.get(MediaAsset, asset_id)
    if not asset or asset.deleted_at:
        raise HTTPException(404, "Asset not found")

    is_admin = has_permission(user, "course:edit")
    if asset.visibility == "private" and not is_admin:
        raise HTTPException(404, "Asset not found")

    if asset.visibility == "course" and not is_admin:
        course = db.get(Course, asset.course_id) if asset.course_id else None
        if not course or course.status != "published":
            raise HTTPException(404, "Asset not found")

    storage = get_storage()
    if not storage.exists(asset.storage_key):
        raise HTTPException(410, "The stored file is no longer available.")

    disposition = "inline" if asset.mime_type in INLINE_TYPES else "attachment"
    safe_name = asset.original_filename.replace('"', "'")
    headers = {
        **SAFE_HEADERS,
        "Content-Disposition": f'{disposition}; filename="{safe_name}"',
        "Content-Length": str(asset.size_bytes),
    }
    return StreamingResponse(storage.stream(asset.storage_key),
                             media_type=asset.mime_type or "application/octet-stream",
                             headers=headers)
