"""Certificates: issue, list, download and public verification."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..certificates_pdf import render_certificate_pdf, reportlab_available
from ..db import get_db
from ..lms_models import Certificate, Course, Enrollment
from ..lms_serializers import certificate_payload
from ..lms_services import (completion_blockers, issue_certificate_if_earned,
                            recalculate_progress, verification_url)
from ..models import User
from ..security import get_current_user, has_permission, require_permission

router = APIRouter(prefix="/api/lms", tags=["lms-certificates"])


@router.get("/certificates/me")
def my_certificates(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.scalars(select(Certificate).where(Certificate.user_id == user.id)
                      .order_by(Certificate.issued_at.desc()))
    return [certificate_payload(c, verification_url=verification_url(c.verification_code))
            for c in rows]


@router.post("/courses/{course_id}/certificate", status_code=201)
def claim_certificate(course_id: int, db: Session = Depends(get_db),
                      user=Depends(require_permission("certificate:view"))):
    """Issue the certificate if -- and only if -- the requirements are met."""
    course = db.get(Course, course_id)
    if not course or course.status != "published":
        raise HTTPException(404, "Course not found")
    enrollment = db.scalar(select(Enrollment).where(
        Enrollment.user_id == user.id, Enrollment.course_id == course.id))
    if not enrollment:
        raise HTTPException(409, {"message": "You are not enrolled on this course.",
                                  "blockers": ["Start the course first."]})
    recalculate_progress(db, enrollment, course)
    certificate = issue_certificate_if_earned(db, user, course, enrollment)
    if certificate is None:
        blockers = completion_blockers(db, enrollment, course)
        db.commit()
        raise HTTPException(409, {
            "message": "The course requirements have not been met yet.",
            "blockers": blockers})
    db.commit()
    return certificate_payload(certificate,
                               verification_url=verification_url(certificate.verification_code))


@router.get("/certificates/{certificate_id}/pdf")
def download_certificate(certificate_id: int, db: Session = Depends(get_db),
                         user=Depends(get_current_user)):
    certificate = db.get(Certificate, certificate_id)
    if not certificate:
        raise HTTPException(404, "Certificate not found")
    if certificate.user_id != user.id and not has_permission(user, "certificate:issue"):
        raise HTTPException(404, "Certificate not found")
    if certificate.revoked_at:
        raise HTTPException(409, "This certificate has been revoked.")
    if not reportlab_available():
        raise HTTPException(503, (
            "PDF certificates are not available because reportlab is not installed. "
            "Install it with: pip install reportlab"))

    pdf = render_certificate_pdf(
        recipient_name=certificate.recipient_name,
        course_title=certificate.course_title,
        certificate_number=certificate.certificate_number,
        verification_code=certificate.verification_code,
        verification_url=verification_url(certificate.verification_code),
        issued_on=f"{certificate.issued_at:%d %B %Y}",
        certificate_type=certificate.certificate_type,
        organisation=config.CERTIFICATE_ORGANISATION,
        signatory=config.CERTIFICATE_SIGNATORY,
        signatory_title=config.CERTIFICATE_SIGNATORY_TITLE,
        score_percent=certificate.score_percent,
    )
    filename = f"{certificate.certificate_number}.pdf"
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Content-Type-Options": "nosniff",
    })


@router.get("/certificates/verify/{code}")
def verify_certificate(code: str, db: Session = Depends(get_db)):
    """Public. Confirms a certificate without exposing anything else."""
    certificate = db.scalar(select(Certificate).where(
        Certificate.verification_code == code.strip().upper()))
    if not certificate:
        return {"valid": False, "reason": "No certificate matches that code."}
    if certificate.revoked_at:
        return {"valid": False, "reason": "This certificate has been revoked.",
                "revoked_at": certificate.revoked_at.isoformat()}
    return {
        "valid": True,
        "recipient_name": certificate.recipient_name,
        "course_title": certificate.course_title,
        "certificate_number": certificate.certificate_number,
        "certificate_type": certificate.certificate_type,
        "issued_at": certificate.issued_at.isoformat(),
        "course_version": certificate.course_version,
        "organisation": config.CERTIFICATE_ORGANISATION,
        "note": ("This certificate records completion of internal learning at "
                 f"{config.CERTIFICATE_ORGANISATION}. It is not an externally "
                 "accredited qualification."),
    }


class RevokeIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/admin/certificates/{certificate_id}/revoke")
def revoke_certificate(certificate_id: int, payload: RevokeIn, db: Session = Depends(get_db),
                       _=Depends(require_permission("certificate:revoke"))):
    certificate = db.get(Certificate, certificate_id)
    if not certificate:
        raise HTTPException(404, "Certificate not found")
    certificate.revoked_at = datetime.now()
    certificate.revoke_reason = payload.reason.strip()
    db.commit()
    return certificate_payload(certificate,
                               verification_url=verification_url(certificate.verification_code))


@router.post("/admin/certificates/{certificate_id}/reissue")
def reissue_certificate(certificate_id: int, db: Session = Depends(get_db),
                        user=Depends(require_permission("certificate:issue"))):
    """Revoke and re-issue, e.g. after a name correction."""
    old = db.get(Certificate, certificate_id)
    if not old:
        raise HTTPException(404, "Certificate not found")
    course = db.get(Course, old.course_id)
    recipient = db.get(User, old.user_id)
    enrollment = db.scalar(select(Enrollment).where(
        Enrollment.user_id == old.user_id, Enrollment.course_id == old.course_id))
    if not course or not recipient or not enrollment:
        raise HTTPException(409, "The original enrolment no longer exists.")

    old.revoked_at = datetime.now()
    old.revoke_reason = f"Reissued by {user.name}."
    db.flush()
    fresh = issue_certificate_if_earned(db, recipient, course, enrollment)
    if fresh is None:
        db.rollback()
        raise HTTPException(409, "The learner no longer meets the course requirements.")
    fresh.issued_by_id = user.id
    db.commit()
    return certificate_payload(fresh,
                               verification_url=verification_url(fresh.verification_code))


@router.get("/admin/certificates")
def list_certificates(course_id: Optional[int] = None, db: Session = Depends(get_db),
                      _=Depends(require_permission("analytics:view"))):
    query = select(Certificate)
    if course_id:
        query = query.where(Certificate.course_id == course_id)
    rows = list(db.scalars(query.order_by(Certificate.issued_at.desc()).limit(500)))
    return {
        "total": db.scalar(select(func.count()).select_from(query.subquery())) or 0,
        "certificates": [certificate_payload(
            c, verification_url=verification_url(c.verification_code)) for c in rows],
    }
