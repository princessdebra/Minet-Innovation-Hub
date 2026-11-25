"""Typed mapping from an OpenMAIC document onto Minet's course structure.

Built against the real `@openmaic/dsl` types (stage.ts, slides.ts, action.ts,
interactive.ts, storage.ts), not guessed keys:

    document = { stage, scenes[], outline }
    scene    = { id, title, order, type: slide|quiz|interactive|pbl, content,
                 actions[], whiteboards[] }
    slide    = content.canvas.elements[]   text | image | shape | line | chart |
                 table | latex | video | audio | code
    narration= actions[type=speech].text   (+ audioId -> asset)
    media    = AssetRef strings ("ast_..." ids), resolved by media.MediaImporter

Anything that cannot be represented faithfully is kept (original data in
`meta`), reported, and the lesson is flagged for review. `extract_document` is
pure (no database), so it can be tested against fixtures directly.

Not verified against source (handled defensively, see docs/openmaic-source-
findings.md): the exact `QuizOption` shape, the outline item fields, the PBL
project schema (pbl.ts / project.json) and the discussion action payload.
"""
from __future__ import annotations

import html as html_lib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..lms_models import (Assessment, AssessmentQuestion, ContentBlock, Course, CourseModule,
                          Lesson)
from .html_blocks import ExtractedBlock
from .media import MediaImporter, Source
from .report import ImportReport
from .sanitize import sanitize_html, strip_to_text

log = logging.getLogger("minet.importer.maic")

MAX_SOURCE_BYTES = 200_000          # raw interactive/PBL source kept for review
MAX_LESSONS_PER_MODULE = 12
SKIP_TEXT_TYPES = {"header", "footer", "partNumber", "itemNumber"}
MEDIA_KINDS = {"image": "image", "video": "video", "audio": "audio"}


class MaicFormatError(ValueError):
    """The payload is not an OpenMAIC document."""


@dataclass
class ExtractedQuestion:
    prompt: str
    kind: str
    options: list[dict]
    correct: list[str]
    marks: int
    explanation: Optional[str]
    scene_title: str


@dataclass
class ExtractedScene:
    title: str
    description: Optional[str]
    blocks: list[ExtractedBlock] = field(default_factory=list)
    needs_review: bool = False


@dataclass
class ExtractedCourse:
    stage_id: str
    name: str
    description: Optional[str]
    scenes: list[ExtractedScene]
    questions: list[ExtractedQuestion]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _s(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _norm(text: str) -> str:
    return " ".join(strip_to_text(text).lower().split())


def _html_block(parts: list[str], title: Optional[str] = None) -> Optional[ExtractedBlock]:
    markup = sanitize_html("".join(parts))
    text = strip_to_text(markup)
    if not text.strip():
        return None
    return ExtractedBlock(block_type="rich_text", title=title,
                          data={"html": markup, "text": text[:4000]})


def _table_html(rows: list[list[str]], header: bool = True) -> str:
    out = ["<table>"]
    for index, row in enumerate(rows):
        tag = "th" if header and index == 0 else "td"
        out.append("<tr>" + "".join(f"<{tag}>{html_lib.escape(cell)}</{tag}>" for cell in row)
                   + "</tr>")
    out.append("</table>")
    return "".join(out)


def _bounded_json(value: Any) -> Any:
    try:
        raw = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return {"unserialisable": True}
    if len(raw) > MAX_SOURCE_BYTES:
        return {"truncated": True, "bytes": len(raw), "head": raw[:MAX_SOURCE_BYTES]}
    return value


# ---------------------------------------------------------------------------
# slides
# ---------------------------------------------------------------------------

def _slide_blocks(slide: dict, scene_title: str, report: ImportReport,
                  label: Optional[str] = None) -> list[ExtractedBlock]:
    """Readable content from canvas elements, in reading order."""
    elements = [e for e in (slide.get("elements") or []) if isinstance(e, dict)]

    def position(element: dict) -> tuple[int, float]:
        top = element.get("top")
        left = element.get("left")
        return (round((top if isinstance(top, (int, float)) else 0) / 25),
                left if isinstance(left, (int, float)) else 0)

    elements.sort(key=position)
    blocks: list[ExtractedBlock] = []
    pending: list[str] = []
    heading = label

    def flush() -> None:
        nonlocal heading
        block = _html_block(pending, title=heading)
        pending.clear()
        if block:
            blocks.append(block)
            heading = None

    for element in elements:
        kind = element.get("type")
        if kind == "text":
            text_type = element.get("textType")
            content = _s(element.get("content"))
            if text_type in SKIP_TEXT_TYPES:
                report.decorative_skipped += 1
                continue
            if text_type == "title" and _norm(content) == _norm(scene_title):
                continue  # the lesson title already says this
            if text_type in ("title", "subtitle", "itemTitle") and content:
                plain = strip_to_text(content)
                if plain:
                    pending.append(f"<h3>{html_lib.escape(plain)}</h3>")
                continue
            if content:
                pending.append(content if "<" in content else f"<p>{html_lib.escape(content)}</p>")
        elif kind == "shape":
            shape_text = element.get("text")
            content = _s(shape_text.get("content")) if isinstance(shape_text, dict) else ""
            if strip_to_text(content):
                pending.append(content if "<" in content else f"<p>{html_lib.escape(content)}</p>")
            else:
                report.decorative_skipped += 1
        elif kind == "table":
            rows = [[_s(cell.get("text")) for cell in row if isinstance(cell, dict)]
                    for row in (element.get("data") or []) if isinstance(row, list)]
            if rows:
                pending.append(_table_html(rows))
        elif kind == "chart":
            data = element.get("data") or {}
            labels = data.get("labels") or []
            legends = data.get("legends") or []
            series = data.get("series") or []
            rows = [[""] + [str(x) for x in legends]]
            for i, label_text in enumerate(labels):
                rows.append([str(label_text)] + [
                    str(s[i]) if isinstance(s, list) and i < len(s) else "" for s in series])
            pending.append(f"<p><em>Chart ({_s(element.get('chartType')) or 'chart'}):</em></p>"
                           + _table_html(rows))
        elif kind == "latex":
            source = _s(element.get("latex"))
            if source:
                pending.append(f"<pre>{html_lib.escape(source)}</pre>")
        elif kind == "code":
            lines = [_s(line.get("content")) for line in (element.get("lines") or [])
                     if isinstance(line, dict)]
            if lines:
                pending.append(f"<pre><code>{html_lib.escape(chr(10).join(lines))}</code></pre>")
        elif kind == "image":
            if element.get("imageType") == "background":
                report.decorative_skipped += 1
                continue
            flush()
            ref = _s(element.get("src"))
            blocks.append(ExtractedBlock(
                block_type="image", title=_s(element.get("name")) or None,
                data={"alt": _s(element.get("name"))}, media_ref=ref or None,
                needs_review=not ref,
                import_note=None if ref else "An image element had no source."))
        elif kind == "video":
            flush()
            ref = _s(element.get("src")) or _s(element.get("mediaRef"))
            blocks.append(ExtractedBlock(
                block_type="video", title=_s(element.get("name")) or None, data={},
                media_ref=ref or None, needs_review=not ref,
                import_note=None if ref else "A video element had no source."))
        elif kind == "audio":
            flush()
            ref = _s(element.get("src"))
            blocks.append(ExtractedBlock(
                block_type="audio", title=_s(element.get("name")) or None, data={},
                media_ref=ref or None, needs_review=not ref,
                import_note=None if ref else "An audio element had no source."))
        elif kind == "line":
            report.decorative_skipped += 1
        else:
            flush()
            blocks.append(ExtractedBlock(
                block_type="unsupported", title=f"Unsupported element: {kind}",
                data={"text": ""}, needs_review=True,
                import_note=f"A slide element of type '{kind}' is not supported.",
            ))
            blocks[-1].data["source"] = _bounded_json(element)
            report.unsupported_item("slide_element", f"type {kind}", scene_title)
    flush()
    return blocks


# ---------------------------------------------------------------------------
# narration
# ---------------------------------------------------------------------------

def _narration_blocks(scene: dict, report: ImportReport) -> list[ExtractedBlock]:
    texts: list[str] = []
    audio_refs: list[str] = []
    skipped_discussion = 0
    for action in scene.get("actions") or []:
        if not isinstance(action, dict):
            continue
        if action.get("type") == "speech":
            text = _s(action.get("text")).strip()
            if text:
                texts.append(text)
            ref = _s(action.get("audioId")) or _s(action.get("audioRef"))
            if ref:
                audio_refs.append(ref)
        elif action.get("type") == "discussion":
            skipped_discussion += 1
    if skipped_discussion:
        report.warn(f"{skipped_discussion} classroom discussion prompt(s) were not imported; "
                    "they depend on live AI agents.")
    blocks: list[ExtractedBlock] = []
    if texts:
        body = "".join(f"<p>{html_lib.escape(t)}</p>" for t in texts)
        blocks.append(ExtractedBlock(
            block_type="notes", title="Narration",
            data={"html": body, "text": "\n\n".join(texts)[:8000]}))
    for index, ref in enumerate(audio_refs, start=1):
        blocks.append(ExtractedBlock(
            block_type="audio",
            title="Narration audio" if len(audio_refs) == 1 else f"Narration audio {index}",
            data={"narration": True}, media_ref=ref))
    return blocks


# ---------------------------------------------------------------------------
# quizzes
# ---------------------------------------------------------------------------

def _option_parts(option: Any, index: int) -> tuple[str, str, set[str]]:
    """(id, text, aliases that an `answer` entry might use) for one option."""
    letter = chr(97 + index)
    if isinstance(option, str):
        return letter, option, {letter, option.strip().lower()}
    if not isinstance(option, dict):
        return letter, str(option), {letter}
    text = next((_s(option.get(k)) for k in ("label", "text", "content", "title") if option.get(k)), "")
    value = _s(option.get("value")) or _s(option.get("id")) or letter
    aliases = {letter, value.strip().lower(), text.strip().lower()}
    return value.strip().lower() if value else letter, text or value, aliases


def _questions(scene: dict, scene_title: str, report: ImportReport) -> list[ExtractedQuestion]:
    out: list[ExtractedQuestion] = []
    content = scene.get("content") or {}
    for number, raw in enumerate(content.get("questions") or [], start=1):
        if not isinstance(raw, dict):
            continue
        kind = raw.get("type")
        prompt = _s(raw.get("question")).strip()
        where = f"{scene_title} / question {number}"
        if kind not in ("single", "multiple", "short_answer") or not prompt:
            report.unsupported_item("quiz_question", f"Unsupported question type {kind!r}.", where)
            continue
        answers = [str(a).strip() for a in (raw.get("answer") or []) if str(a).strip()]
        marks = raw.get("points")
        marks = int(marks) if isinstance(marks, (int, float)) and marks >= 1 else 1
        explanation = _s(raw.get("analysis")).strip() or None

        if kind == "short_answer":
            if raw.get("hasAnswer") is False or not answers:
                report.unsupported_item(
                    "ungradable_question",
                    "Open-ended question with no answer key; Minet cannot mark it automatically.",
                    where)
                continue
            out.append(ExtractedQuestion(prompt, "short_answer", [], answers, marks,
                                         explanation, scene_title))
            continue

        parts = [_option_parts(o, i) for i, o in enumerate(raw.get("options") or [])]
        if len(parts) < 2:
            report.unsupported_item("quiz_question", "Fewer than two options.", where)
            continue
        options = [{"id": pid, "text": text} for pid, text, _ in parts]
        correct: list[str] = []
        for answer in answers:
            needle = answer.strip().lower()
            for pid, _text, aliases in parts:
                if needle in aliases and pid not in correct:
                    correct.append(pid)
                    break
        if not correct or (kind == "single" and len(correct) != 1):
            report.unsupported_item(
                "ungradable_question",
                "The correct answer could not be matched to an option.", where)
            continue
        out.append(ExtractedQuestion(prompt, kind, options, correct, marks, explanation,
                                     scene_title))
    return out


# ---------------------------------------------------------------------------
# interactive and PBL: preserved, never silently dropped
# ---------------------------------------------------------------------------

def _interactive_block(content: dict, title: str, report: ImportReport) -> ExtractedBlock:
    widget = _s(content.get("widgetType")) or "interactive"
    raw_html = _s(content.get("html"))
    text = strip_to_text(raw_html)[:2000] if raw_html else ""
    report.unsupported_item("interactive_scene", f"{widget} activity", title)
    return ExtractedBlock(
        block_type="unsupported", title=f"Interactive activity ({widget})",
        data={"text": text, "widget_type": widget, "url": _s(content.get("url")),
              "source": _bounded_json({k: v for k, v in content.items() if k != "type"})},
        needs_review=True,
        import_note=("This interactive activity cannot run inside a Minet lesson. The original "
                     "is preserved on this block; rebuild it as lesson content or an assessment."))


_PBL_KEYS = ("title", "name", "description", "goal", "objective", "objectives", "task", "tasks",
             "instruction", "instructions", "resource", "resources", "role", "roles",
             "summary", "topic", "context")


def _collect_strings(value: Any, out: list[str], depth: int = 0) -> None:
    if depth > 6 or len(out) > 80:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and key.lower() in _PBL_KEYS and item.strip():
                out.append(item.strip())
            else:
                _collect_strings(item, out, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _collect_strings(item, out, depth + 1)


def _pbl_block(content: dict, title: str, report: ImportReport) -> ExtractedBlock:
    found: list[str] = []
    _collect_strings(content, found)
    report.unsupported_item("pbl_scene", "Project-based learning activity", title)
    return ExtractedBlock(
        block_type="unsupported", title="Project-based learning activity",
        data={"text": "\n\n".join(dict.fromkeys(found))[:4000],
              "source": _bounded_json({k: v for k, v in content.items() if k != "type"})},
        needs_review=True,
        import_note=("Project-based learning activities are preserved but not interactive in "
                     "Minet. Review the extracted instructions and rebuild them as lesson content."))


# ---------------------------------------------------------------------------
# document
# ---------------------------------------------------------------------------

def _outline_descriptions(document: dict, count: int) -> list[Optional[str]]:
    outline = document.get("outline")
    items = outline.get("outlines") if isinstance(outline, dict) else None
    if isinstance(items, list) and len(items) == count:
        return [_s(i.get("description")).strip() or None if isinstance(i, dict) else None
                for i in items]
    return [None] * count


def extract_document(document: Any, report: ImportReport) -> ExtractedCourse:
    if not isinstance(document, dict) or not isinstance(document.get("scenes"), list):
        raise MaicFormatError("Not an OpenMAIC document: expected an object with a 'scenes' list.")
    stage = document.get("stage") if isinstance(document.get("stage"), dict) else {}
    stage_id = _s(stage.get("id")) or _s(document.get("id"))
    if not stage_id:
        raise MaicFormatError("The document has no stage id.")

    scenes = [s for s in document["scenes"] if isinstance(s, dict)]
    scenes.sort(key=lambda s: s.get("order") if isinstance(s.get("order"), (int, float)) else 0)
    descriptions = _outline_descriptions(document, len(scenes))

    extracted: list[ExtractedScene] = []
    questions: list[ExtractedQuestion] = []
    for index, scene in enumerate(scenes):
        title = _s(scene.get("title")).strip() or f"Scene {index + 1}"
        kind = scene.get("type")
        content = scene.get("content") if isinstance(scene.get("content"), dict) else {}
        out = ExtractedScene(title=title[:200], description=descriptions[index])

        if kind == "slide":
            canvas = content.get("canvas") if isinstance(content.get("canvas"), dict) else {}
            out.blocks.extend(_slide_blocks(canvas, title, report))
            for number, board in enumerate(scene.get("whiteboards") or [], start=1):
                if isinstance(board, dict):
                    out.blocks.extend(_slide_blocks(
                        board, title, report, label="Whiteboard" if number == 1
                        else f"Whiteboard {number}"))
        elif kind == "quiz":
            asked = _questions(scene, title, report)
            questions.extend(asked)
            dropped = len(content.get("questions") or []) - len(asked)
            note = f"This lesson's {len(asked)} question(s) are in the course assessment."
            out.blocks.append(ExtractedBlock(
                block_type="notes", title="Knowledge check",
                data={"text": note, "html": f"<p>{html_lib.escape(note)}</p>"}))
            if dropped > 0:
                out.needs_review = True
        elif kind == "interactive":
            out.blocks.append(_interactive_block(content, title, report))
        elif kind == "pbl":
            out.blocks.append(_pbl_block(content, title, report))
        else:
            report.unsupported_item("scene", f"Unknown scene type {kind!r}.", title)
            out.blocks.append(ExtractedBlock(
                block_type="unsupported", title=f"Unsupported scene: {kind}",
                data={"text": "", "source": _bounded_json(scene)}, needs_review=True,
                import_note=f"Scene type '{kind}' is not supported; the original is preserved."))

        out.blocks.extend(_narration_blocks(scene, report))
        out.needs_review = out.needs_review or any(b.needs_review for b in out.blocks)
        if not out.blocks:
            report.unsupported_item("empty_scene", "Nothing readable was found.", title)
            continue
        extracted.append(out)

    return ExtractedCourse(
        stage_id=stage_id, name=_s(stage.get("name")).strip() or "Imported course",
        description=_s(stage.get("description")).strip() or None,
        scenes=extracted, questions=questions)


# ---------------------------------------------------------------------------
# persistence
# ---------------------------------------------------------------------------

def _minutes(blocks: list[ExtractedBlock]) -> int:
    words = sum(len(str(b.data.get("text") or "").split()) for b in blocks)
    media = sum(2 for b in blocks if b.block_type in ("audio", "video"))
    return max(1, round(words / 180) + media)


def _remove_previous(db: Session, course: Course, key: str) -> None:
    for module in db.scalars(select(CourseModule).where(
            CourseModule.course_id == course.id, CourseModule.import_key == key)):
        db.delete(module)
    for assessment in db.scalars(select(Assessment).where(
            Assessment.course_id == course.id, Assessment.import_key == key)):
        db.delete(assessment)
    db.flush()


def persist_course(db: Session, course: Course, extracted: ExtractedCourse, media: MediaImporter,
                   report: ImportReport, *, replace: bool = False) -> ImportReport:
    key = f"maic:{extracted.stage_id}"
    already = db.scalar(select(CourseModule.id).where(
        CourseModule.course_id == course.id, CourseModule.import_key == key).limit(1))
    if already and not replace:
        report.already_imported = True
        report.warn("This classroom was already imported into this course, so nothing was "
                    "added. Re-import with 'replace' to overwrite it (your edits would be lost).")
        return report
    if already:
        _remove_previous(db, course, key)
        db.refresh(course)

    # Media first, so every block knows whether its file arrived.
    for scene in extracted.scenes:
        for block in scene.blocks:
            if not block.media_ref:
                continue
            asset = media.import_ref(block.media_ref, block.block_type)
            if asset is None:
                reason = media.failure_reason(block.media_ref.strip())
                block.needs_review = True
                block.import_note = f"Media could not be imported: {reason}"
                block.data["broken_media"] = True
                block.data["original_ref"] = block.media_ref[:200]
                scene.needs_review = True
            else:
                block.data["asset_id"] = asset.id
                block.data["src"] = f"/api/lms/assets/{asset.id}"
                block.data.pop("original_src", None)
            # Employee-facing content must never carry an OpenMAIC reference.
            block.media_ref = None

    base = len(course.modules)
    chunks = [extracted.scenes[i:i + MAX_LESSONS_PER_MODULE]
              for i in range(0, len(extracted.scenes), MAX_LESSONS_PER_MODULE)]
    for chunk_index, chunk in enumerate(chunks):
        title = extracted.name if len(chunks) == 1 else f"{extracted.name} — part {chunk_index + 1}"
        module = CourseModule(
            course_id=course.id, title=title[:200], position=base + chunk_index,
            estimated_minutes=sum(_minutes(s.blocks) for s in chunk), is_published=True,
            import_key=key)
        db.add(module)
        db.flush()
        report.modules += 1
        for position, scene in enumerate(chunk):
            lesson = Lesson(
                module_id=module.id, title=scene.title, description=scene.description,
                position=position, lesson_type="standard",
                estimated_minutes=_minutes(scene.blocks), is_published=True,
                needs_review=scene.needs_review)
            db.add(lesson)
            db.flush()
            report.lessons += 1
            for block_position, block in enumerate(scene.blocks):
                source = block.data.pop("source", None)
                meta: dict = {"imported": True, "source": "openmaic"}
                if source is not None:
                    meta["original"] = source
                if block.data.get("broken_media"):
                    meta["broken_media"] = True
                db.add(ContentBlock(
                    lesson_id=lesson.id, block_type=block.block_type,
                    title=(block.title or None) and block.title[:300], data=block.data,
                    asset_id=block.data.get("asset_id"), position=block_position, meta=meta,
                    needs_review=block.needs_review, import_note=block.import_note))
                report.blocks += 1

    if extracted.questions:
        assessment = Assessment(
            course_id=course.id, title="Knowledge check",
            instructions="Questions from the course's interactive classroom.",
            pass_percent=70, max_attempts=3, is_required_for_completion=True,
            is_published=True, needs_review=False, import_key=key)
        db.add(assessment)
        db.flush()
        for position, q in enumerate(extracted.questions):
            assessment.questions.append(AssessmentQuestion(
                prompt=q.prompt, kind=q.kind, options=q.options, correct=q.correct,
                marks=q.marks, explanation=q.explanation, position=position,
                is_ai_generated=True))
        report.questions += len(extracted.questions)

    if extracted.description and not course.description:
        course.description = extracted.description
    return report


def import_document(db: Session, course: Course, document: Any, *, source: Source,
                    uploaded_by_id: Optional[int], report: Optional[ImportReport] = None,
                    replace: bool = False, resolve_path: Optional[Callable[[str], Optional[str]]] = None,
                    origin: str = "openmaic_document") -> ImportReport:
    report = report or ImportReport()
    report.source = origin
    extracted = extract_document(document, report)
    media = MediaImporter(db, course, report, source=source, uploaded_by_id=uploaded_by_id,
                          resolve_path=resolve_path)
    return persist_course(db, course, extracted, media, report, replace=replace)
