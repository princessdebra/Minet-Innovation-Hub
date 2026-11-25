"""HTML sanitisation for imported content.

Imported HTML is untrusted. It is sanitised at *import* time (so the database
never holds a script tag) and rendered in the frontend inside a sandboxed frame
with a restrictive CSP -- defence in depth, not either/or.

If `bleach` is unavailable the module degrades to stripping every tag and
keeping the text. Degrading to plain text is safe; degrading to raw HTML
would not be, so there is no "pass it through" path.
"""
from __future__ import annotations

import html
import logging
import re
from html.parser import HTMLParser

log = logging.getLogger("minet.importer.sanitize")

ALLOWED_TAGS = [
    "p", "br", "hr", "strong", "b", "em", "i", "u", "s", "sub", "sup",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "dl", "dt", "dd",
    "blockquote", "pre", "code", "span", "div",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
    "a", "img", "figure", "figcaption",
]
# Images in rich text may only point at Minet-hosted assets. Any other src (an
# external URL, a tracking pixel, a relative path that cannot resolve) is dropped,
# so a lesson can never make an employee's browser call out to another host.
MINET_ASSET_SRC = re.compile(r"^/api/lms/assets/\d+$")


def _img_attr(tag: str, name: str, value: str) -> bool:
    if name in ("alt", "title", "width", "height"):
        return True
    return name == "src" and bool(MINET_ASSET_SRC.match(value or ""))


ALLOWED_ATTRS = {
    "*": ["class"],
    "a": ["href", "title", "rel", "target"],
    "img": _img_attr,
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan", "scope"],
}
# No javascript:, no data: (except images handled separately), no external http
# by default -- imported media is rewritten to Minet asset URLs by the mapper.
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

_SRCLESS_IMG = re.compile(r"<img(?![^>]*\ssrc=)[^>]*>", re.IGNORECASE)
_SCRIPTISH = re.compile(r"<\s*(script|style|iframe|object|embed|link|meta)\b[^>]*>.*?"
                        r"<\s*/\s*\1\s*>", re.IGNORECASE | re.DOTALL)
_SELF_CLOSING_SCRIPTISH = re.compile(
    r"<\s*(script|style|iframe|object|embed|link|meta)\b[^>]*/?>", re.IGNORECASE)


class _TextOnly(HTMLParser):
    """Fallback: keep the text, drop every tag."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        joined = "".join(self.parts)
        lines = [" ".join(line.split()) for line in joined.split("\n")]
        return "\n".join(line for line in lines if line).strip()


def strip_to_text(raw: str) -> str:
    """Every tag removed, entities decoded. Always safe."""
    if not raw:
        return ""
    cleaned = _SCRIPTISH.sub(" ", raw)
    cleaned = _SELF_CLOSING_SCRIPTISH.sub(" ", cleaned)
    parser = _TextOnly()
    try:
        parser.feed(cleaned)
        parser.close()
    except Exception:  # malformed markup -- fall back to a blunt strip
        return html.unescape(re.sub(r"<[^>]*>", " ", cleaned)).strip()
    return parser.text()


def sanitize_html(raw: str) -> str:
    """Allowlist-sanitised HTML, or escaped plain text if bleach is missing."""
    if not raw:
        return ""
    try:
        import bleach
    except ImportError:
        log.warning("bleach is not installed; imported HTML degraded to plain text. "
                    "Install it with: pip install bleach")
        text = strip_to_text(raw)
        return "".join(f"<p>{html.escape(line)}</p>"
                       for line in text.split("\n") if line.strip())

    cleaned = _SCRIPTISH.sub("", raw)
    cleaned = _SELF_CLOSING_SCRIPTISH.sub("", cleaned)
    result = bleach.clean(
        cleaned,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )
    # An <img> whose src was refused has nothing left to show: remove it entirely.
    return _SRCLESS_IMG.sub("", result)


def sanitizer_available() -> bool:
    try:
        import bleach  # noqa: F401
        return True
    except ImportError:
        return False
