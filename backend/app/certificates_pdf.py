"""Certificate PDF rendering.

Uses reportlab if it is installed; otherwise the API says so plainly rather
than returning a broken file. Colours follow the Minet design tokens
(brand red #E21A22).

Wording is deliberately careful: a Minet certificate records completion of
internal learning. It does not claim external accreditation.
"""
from __future__ import annotations

import io
from typing import Optional

BRAND_RED = (0xE2 / 255, 0x1A / 255, 0x22 / 255)
INK = (0x11 / 255, 0x18 / 255, 0x27 / 255)
MUTED = (0x6B / 255, 0x72 / 255, 0x80 / 255)
BORDER = (0xE5 / 255, 0xE7 / 255, 0xEB / 255)

TYPE_LABEL = {
    "completion": "Certificate of Completion",
    "assessed_competency": "Certificate of Assessed Competency",
}


def reportlab_available() -> bool:
    try:
        import reportlab  # noqa: F401
        return True
    except ImportError:
        return False


def render_certificate_pdf(*, recipient_name: str, course_title: str,
                           certificate_number: str, verification_code: str,
                           verification_url: str, issued_on: str,
                           certificate_type: str = "completion",
                           organisation: str = "Minet",
                           signatory: str = "Head of Innovation",
                           signatory_title: str = "Minet Innovation Hub",
                           score_percent: Optional[int] = None) -> bytes:
    """A single landscape A4 page. Raises RuntimeError if reportlab is absent."""
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError as exc:  # pragma: no cover - guarded by the route
        raise RuntimeError(
            "PDF certificates need reportlab. Install it with: pip install reportlab"
        ) from exc

    buffer = io.BytesIO()
    width, height = landscape(A4)
    pdf = canvas.Canvas(buffer, pagesize=landscape(A4))
    pdf.setTitle(f"{course_title} - {recipient_name}")
    pdf.setAuthor(organisation)
    pdf.setSubject(TYPE_LABEL.get(certificate_type, "Certificate"))

    # Frame
    pdf.setStrokeColorRGB(*BORDER)
    pdf.setLineWidth(1)
    pdf.rect(12 * mm, 12 * mm, width - 24 * mm, height - 24 * mm)
    pdf.setFillColorRGB(*BRAND_RED)
    pdf.rect(12 * mm, height - 20 * mm, width - 24 * mm, 8 * mm, stroke=0, fill=1)

    # Organisation
    pdf.setFillColorRGB(*INK)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawCentredString(width / 2, height - 38 * mm, organisation.upper())
    pdf.setFillColorRGB(*MUTED)
    pdf.setFont("Helvetica", 9.5)
    pdf.drawCentredString(width / 2, height - 44 * mm, "INNOVATION HUB")

    # Title
    pdf.setFillColorRGB(*BRAND_RED)
    pdf.setFont("Helvetica-Bold", 25)
    pdf.drawCentredString(width / 2, height - 62 * mm,
                          TYPE_LABEL.get(certificate_type, "Certificate"))

    pdf.setFillColorRGB(*MUTED)
    pdf.setFont("Helvetica", 11)
    pdf.drawCentredString(width / 2, height - 76 * mm, "This is to certify that")

    # Recipient
    pdf.setFillColorRGB(*INK)
    pdf.setFont("Helvetica-Bold", 30)
    pdf.drawCentredString(width / 2, height - 92 * mm, recipient_name)
    pdf.setStrokeColorRGB(*BRAND_RED)
    pdf.setLineWidth(1.5)
    pdf.line(width / 2 - 85 * mm, height - 97 * mm, width / 2 + 85 * mm, height - 97 * mm)

    pdf.setFillColorRGB(*MUTED)
    pdf.setFont("Helvetica", 11)
    pdf.drawCentredString(width / 2, height - 107 * mm, "has successfully completed")

    # Course
    pdf.setFillColorRGB(*INK)
    pdf.setFont("Helvetica-Bold", 17)
    title = course_title if len(course_title) <= 72 else course_title[:69] + "..."
    pdf.drawCentredString(width / 2, height - 119 * mm, title)

    if score_percent is not None:
        pdf.setFillColorRGB(*MUTED)
        pdf.setFont("Helvetica", 10.5)
        pdf.drawCentredString(width / 2, height - 128 * mm,
                              f"Assessment result: {score_percent}%")

    # Footer: issue details, signature, verification
    base = 32 * mm
    pdf.setFillColorRGB(*MUTED)
    pdf.setFont("Helvetica", 8.5)
    pdf.drawString(24 * mm, base + 10 * mm, "DATE ISSUED")
    pdf.drawString(24 * mm, base, "CERTIFICATE ID")
    pdf.setFillColorRGB(*INK)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(24 * mm, base + 5.5 * mm, issued_on)
    pdf.drawString(24 * mm, base - 5 * mm, certificate_number)

    pdf.setStrokeColorRGB(*BORDER)
    pdf.setLineWidth(0.8)
    pdf.line(width / 2 - 35 * mm, base + 6 * mm, width / 2 + 35 * mm, base + 6 * mm)
    pdf.setFillColorRGB(*INK)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(width / 2, base, signatory)
    pdf.setFillColorRGB(*MUTED)
    pdf.setFont("Helvetica", 8.5)
    pdf.drawCentredString(width / 2, base - 5 * mm, signatory_title)

    pdf.setFillColorRGB(*MUTED)
    pdf.setFont("Helvetica", 8.5)
    pdf.drawRightString(width - 24 * mm, base + 10 * mm, "VERIFICATION CODE")
    pdf.setFillColorRGB(*INK)
    pdf.setFont("Courier-Bold", 11)
    pdf.drawRightString(width - 24 * mm, base + 5 * mm, verification_code)
    pdf.setFillColorRGB(*MUTED)
    pdf.setFont("Helvetica", 7.5)
    pdf.drawRightString(width - 24 * mm, base - 1 * mm, f"Verify at {verification_url}")

    pdf.setFont("Helvetica-Oblique", 7)
    pdf.drawCentredString(
        width / 2, 18 * mm,
        "This certificate records completion of internal learning at "
        f"{organisation}. It is not an externally accredited qualification.")

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
