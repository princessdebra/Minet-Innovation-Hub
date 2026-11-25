"""Turn an exported HTML lesson into Minet content blocks.

The rule from the brief: HTML must not become the only representation of a
lesson. So we pull out headings, prose, images, audio, video and takeaway
lists as individual blocks, and only fall back to a single `html_fallback`
block when a document cannot be decomposed at all -- and even then the block is
flagged for review rather than quietly accepted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from . import dom
from .sanitize import sanitize_html, strip_to_text

SLIDE_HINTS = {"slide", "scene", "page", "step", "section", "card", "stage"}
NOTE_HINTS = {"note", "notes", "speaker-notes", "narration", "transcript"}
TAKEAWAY_PATTERN = re.compile(
    r"key\s*(take\s*aways?|points?|learnings?)|summary|in\s*short|remember", re.IGNORECASE)
QUESTION_HINTS = {"quiz", "question", "knowledge-check", "assessment", "mcq"}
MEDIA_TAGS = {"img": "image", "audio": "audio", "video": "video", "source": "media"}


@dataclass
class ExtractedBlock:
    block_type: str
    title: Optional[str] = None
    data: dict = field(default_factory=dict)
    media_ref: Optional[str] = None     # path as written in the export
    needs_review: bool = False
    import_note: Optional[str] = None


@dataclass
class ExtractedLesson:
    title: str
    blocks: list[ExtractedBlock] = field(default_factory=list)
    notes: Optional[str] = None


def _is_slide(node: dom.Node) -> bool:
    if node.tag in ("section", "article"):
        return True
    classes = node.classes()
    identifier = (node.attrs.get("id") or "").lower()
    return any(hint in cls for cls in classes for hint in SLIDE_HINTS) or \
        any(hint in identifier for hint in SLIDE_HINTS)


def _media_src(node: dom.Node) -> Optional[str]:
    src = node.attrs.get("src") or node.attrs.get("data-src")
    if not src and node.tag in ("audio", "video"):
        for source in node.find_all("source"):
            src = source.attrs.get("src")
            if src:
                break
    if not src:
        return None
    src = src.strip()
    if src.lower().startswith(("javascript:", "vbscript:")):
        return None
    return src


def _collect_sections(root: dom.Node) -> list[dom.Node]:
    """Slide-like containers, or the whole body if there are none."""
    body = next((n for n in root.find_all("body")), root)
    candidates = [n for n in body.walk() if n is not body and _is_slide(n)]
    # Drop nested candidates: keep only the outermost of any chain.
    outermost: list[dom.Node] = []
    for node in candidates:
        parent = node.parent
        nested = False
        while parent is not None:
            if parent in candidates:
                nested = True
                break
            parent = parent.parent
        if not nested:
            outermost.append(node)
    return outermost or [body]


def _split_on_headings(section: dom.Node) -> list[tuple[Optional[str], list[dom.Node]]]:
    """Group a section's children into (heading, nodes) runs."""
    groups: list[tuple[Optional[str], list[dom.Node]]] = []
    heading: Optional[str] = None
    current: list[dom.Node] = []
    for child in section.children:
        if child.tag in dom.HEADINGS:
            if current or heading:
                groups.append((heading, current))
            heading = child.inner_text().strip() or None
            current = []
        else:
            current.append(child)
    if current or heading:
        groups.append((heading, current))
    return groups or [(None, list(section.children))]


def _blocks_from_nodes(nodes: list[dom.Node], heading: Optional[str]) -> list[ExtractedBlock]:
    blocks: list[ExtractedBlock] = []
    prose: list[dom.Node] = []

    def flush_prose() -> None:
        if not prose:
            return
        markup = "".join(n.to_html() for n in prose)
        text = strip_to_text(markup)
        if text:
            cleaned = sanitize_html(markup)
            if cleaned.strip():
                blocks.append(ExtractedBlock(
                    block_type="rich_text",
                    title=heading if not blocks else None,
                    data={"html": cleaned, "text": text[:4000]},
                ))
        prose.clear()

    for node in nodes:
        if node.is_text:
            prose.append(node)
            continue

        media_nodes = [node] if node.tag in MEDIA_TAGS else node.find_all("img", "audio", "video")
        if media_nodes and node.tag in MEDIA_TAGS:
            flush_prose()
            src = _media_src(node)
            kind = MEDIA_TAGS.get(node.tag, "image")
            blocks.append(ExtractedBlock(
                block_type=kind if kind != "media" else "image",
                title=node.attrs.get("alt") or node.attrs.get("title") or heading,
                data={"alt": node.attrs.get("alt") or "", "original_src": src or ""},
                media_ref=src,
                needs_review=src is None,
                import_note=None if src else "Media element had no usable source.",
            ))
            continue
        if media_nodes:
            # A wrapper (figure/div) around media: emit the media, keep the caption.
            flush_prose()
            for media in media_nodes:
                src = _media_src(media)
                kind = MEDIA_TAGS.get(media.tag, "image")
                caption = ""
                if media.parent is not None:
                    for figcaption in media.parent.find_all("figcaption"):
                        caption = figcaption.inner_text()
                        break
                blocks.append(ExtractedBlock(
                    block_type=kind if kind != "media" else "image",
                    title=media.attrs.get("alt") or caption or heading,
                    data={"alt": media.attrs.get("alt") or "", "caption": caption,
                          "original_src": src or ""},
                    media_ref=src,
                    needs_review=src is None,
                    import_note=None if src else "Media element had no usable source.",
                ))
            continue

        classes = " ".join(node.classes())
        if node.tag in ("ul", "ol") and heading and TAKEAWAY_PATTERN.search(heading):
            flush_prose()
            items = [li.inner_text() for li in node.find_all("li") if li.inner_text()]
            if items:
                blocks.append(ExtractedBlock(
                    block_type="key_takeaways", title=heading, data={"items": items[:20]}))
                continue
        if any(hint in classes for hint in NOTE_HINTS):
            flush_prose()
            text = node.inner_text()
            if text:
                blocks.append(ExtractedBlock(
                    block_type="notes", title=heading, data={"text": text[:4000]}))
                continue
        if any(hint in classes for hint in QUESTION_HINTS):
            flush_prose()
            text = node.inner_text()
            blocks.append(ExtractedBlock(
                block_type="unsupported", title=heading or "Knowledge check",
                data={"text": text[:2000], "html": sanitize_html(node.inner_html())},
                needs_review=True,
                import_note="An interactive knowledge check was found. Rebuild it as a "
                            "Minet assessment question so results can be graded and recorded."))
            continue

        prose.append(node)

    flush_prose()
    return blocks


def extract_lessons(markup: str, *, fallback_title: str = "Imported lesson") -> list[ExtractedLesson]:
    """One lesson per slide-like section, in document order."""
    root = dom.parse(markup)
    document_title = dom.title_of(root) or fallback_title
    sections = _collect_sections(root)
    lessons: list[ExtractedLesson] = []

    for index, section in enumerate(sections, start=1):
        blocks: list[ExtractedBlock] = []
        section_title: Optional[str] = None
        for heading, nodes in _split_on_headings(section):
            if section_title is None and heading:
                section_title = heading
            blocks.extend(_blocks_from_nodes(nodes, heading))
        if not blocks:
            continue
        title = section_title or (document_title if len(sections) == 1
                                  else f"{document_title} — part {index}")
        lessons.append(ExtractedLesson(title=title[:200], blocks=blocks))

    if not lessons:
        # Nothing decomposable: keep the whole document, flagged for review.
        cleaned = sanitize_html(markup)
        text = strip_to_text(markup)
        if cleaned.strip() or text:
            lessons.append(ExtractedLesson(
                title=document_title,
                blocks=[ExtractedBlock(
                    block_type="html_fallback",
                    title=document_title,
                    data={"html": cleaned, "text": text[:8000]},
                    needs_review=True,
                    import_note="This lesson could not be split into content blocks. "
                                "The sanitised document is preserved as a fallback.")]))
    return lessons


def media_references(lessons: list[ExtractedLesson]) -> list[str]:
    refs = []
    for lesson in lessons:
        for block in lesson.blocks:
            if block.media_ref and block.media_ref not in refs:
                refs.append(block.media_ref)
    return refs
