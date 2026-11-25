"""Realistic OpenMAIC documents, written from the real `@openmaic/dsl` types.

Field names and shapes follow packages/@openmaic/dsl/src/{stage,slides,action,
interactive,storage}.ts as read from OpenMAIC v1.5.0 -- not from Minet's own
earlier assumptions. Where the real shape is NOT verified (QuizOption, the PBL
project schema, the discussion payload) the fixture picks one plausible shape
and the corresponding test says so.
"""
from __future__ import annotations

import json
import zipfile
import io

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
       b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
       b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
PNG_2 = PNG + b"\x00second-image"
MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64
MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" * 16

IMG = "ast_img00000001AAAA"
IMG2 = "ast_img00000002BBBB"
VID = "ast_vid00000001CCCC"
AUD = "ast_aud00000001DDDD"
AUD2 = "ast_aud00000002EEEE"
MISSING = "ast_gone0000009ZZZZ"

ASSETS: dict[str, bytes] = {IMG: PNG, IMG2: PNG_2, VID: MP4, AUD: MP3, AUD2: MP3 + b"\x01"}


def base(**extra) -> dict:
    return {"left": 0, "top": 0, "width": 100, "height": 40, "rotate": 0, **extra}


def text(el_id: str, html: str, *, top: int, text_type: str = "content", left: int = 40) -> dict:
    return base(id=el_id, type="text", content=html, defaultFontName="Arial",
                defaultColor="#333", textType=text_type, top=top, left=left)


def slide(*elements: dict) -> dict:
    return {"id": "slide-x", "viewportSize": 1000, "viewportRatio": 0.5625,
            "theme": {"backgroundColor": "#fff", "themeColors": [], "fontColor": "#333",
                      "fontName": "Arial"},
            "elements": list(elements)}


def speech(action_id: str, said: str, audio: str | None = None) -> dict:
    action = {"id": action_id, "type": "speech", "text": said}
    if audio:
        action["audioId"] = audio
    return action


def document() -> dict:
    scene1 = {
        "id": "scene-1", "stageId": "stage-abc123", "title": "Why triage matters",
        "order": 0, "type": "slide",
        "content": {"type": "slide", "canvas": slide(
            text("t0", "<p>Why triage matters</p>", top=20, text_type="title"),
            text("t-foot", "<p>3</p>", top=500, text_type="partNumber"),
            # deliberately listed out of reading order
            text("t2", "<p>Second paragraph.</p>", top=200),
            text("t1", "<p>Triage decides <strong>what happens next</strong>.</p>", top=120),
            base(id="sh1", type="shape", viewBox=[100, 100], path="M0 0", fill="#eee",
                 fixedRatio=False, top=260,
                 text={"content": "<p>Callout inside a shape</p>", "defaultFontName": "A",
                       "defaultColor": "#000", "align": "middle"}),
            base(id="sh2", type="shape", viewBox=[10, 10], path="M0 0", fill="#fff",
                 fixedRatio=False, top=300),
            base(id="ln1", type="line", start=[0, 0], end=[10, 10], style="solid",
                 color="#000", points=["", ""]),
            base(id="im0", type="image", src=IMG2, fixedRatio=True, imageType="background"),
            base(id="im1", type="image", src=IMG, fixedRatio=True, imageType="pageFigure",
                 top=340, name="Claims journey"),
            base(id="v1", type="video", src=VID, autoplay=False, top=400),
            base(id="tb1", type="table", outline={}, colWidths=[1, 1], cellMinHeight=20, top=440,
                 data=[[{"id": "c1", "colspan": 1, "rowspan": 1, "text": "Stage"},
                        {"id": "c2", "colspan": 1, "rowspan": 1, "text": "Owner"}],
                       [{"id": "c3", "colspan": 1, "rowspan": 1, "text": "Assess"},
                        {"id": "c4", "colspan": 1, "rowspan": 1, "text": "Claims team"}]]),
            base(id="ch1", type="chart", chartType="column", top=460, themeColors=[],
                 data={"labels": ["Q1", "Q2"], "legends": ["Claims"], "series": [[10, 20]]}),
            base(id="lx", type="latex", latex="x^2 + y^2", top=480),
            base(id="cd", type="code", language="python", top=500,
                 lines=[{"id": "l1", "content": "print('triage')"}]),
        )},
        "actions": [
            speech("a1", "Triage decides what happens next.", AUD),
            {"id": "a2", "type": "spotlight", "elementId": "t1"},
            speech("a3", "Let us look at the journey.", AUD2),
            {"id": "a4", "type": "discussion", "topic": "Why does it matter?"},
        ],
    }
    scene2 = {
        "id": "scene-2", "stageId": "stage-abc123", "title": "The three checks", "order": 1,
        "type": "slide",
        "content": {"type": "slide", "canvas": slide(
            text("u1", "<ul><li>Cover</li><li>Evidence</li><li>Value</li></ul>", top=100),
            # the SAME asset again: must be downloaded once
            base(id="im2", type="image", src=IMG, fixedRatio=True, imageType="itemFigure", top=200),
            base(id="im3", type="image", src=MISSING, fixedRatio=True, top=260, name="Lost image"),
            base(id="im4", type="image", src="gen_img_legacy_4", fixedRatio=True, top=320),
            base(id="im5", type="image", src="https://example.com/tracker.png",
                 fixedRatio=True, top=380),
        )},
        "actions": [speech("b1", "Three checks, every time.")],
    }
    scene3 = {
        "id": "scene-3", "stageId": "stage-abc123", "title": "Check your understanding",
        "order": 2, "type": "quiz",
        "content": {"type": "quiz", "questions": [
            {"id": "q1", "type": "single", "question": "What comes first?",
             "options": [{"value": "A", "label": "Triage"}, {"value": "B", "label": "Payment"}],
             "answer": ["A"], "analysis": "Triage always comes first.", "points": 2},
            {"id": "q2", "type": "multiple", "question": "Which are valid channels?",
             "options": [{"value": "A", "label": "Portal"}, {"value": "B", "label": "Email"},
                         {"value": "C", "label": "Carrier pigeon"}],
             "answer": ["A", "B"], "analysis": "Portal and email.", "points": 1},
            {"id": "q3", "type": "short_answer", "question": "Name the first step.",
             "answer": ["triage", "triaging"], "hasAnswer": True, "points": 1},
            {"id": "q4", "type": "short_answer", "question": "Reflect on a claim you handled.",
             "hasAnswer": False, "commentPrompt": "Grade for reflection."},
        ]},
    }
    scene4 = {
        "id": "scene-4", "stageId": "stage-abc123", "title": "Claims simulator", "order": 3,
        "type": "interactive",
        "content": {"type": "interactive", "widgetType": "simulation",
                    "html": "<div><script>steal()</script>Simulate a claim here.</div>"},
    }
    scene5 = {
        "id": "scene-5", "stageId": "stage-abc123", "title": "Redesign the journey", "order": 4,
        "type": "pbl",
        "content": {"type": "pbl", "project": {
            "title": "Redesign a claims journey",
            "description": "Work in a team to remove one handoff.",
            "tasks": [{"title": "Map the current journey"}, {"title": "Propose one change"}]}},
    }
    return {
        "stage": {"id": "stage-abc123", "name": "Claims triage",
                  "description": "How claims are triaged.", "createdAt": 1, "updatedAt": 2},
        # deliberately out of order: the mapper must sort by `order`
        "scenes": [scene3, scene1, scene5, scene2, scene4],
        "outline": {"outlines": [], "requirement": "triage", "generationComplete": True},
    }


def manifest() -> dict:
    """The same course as a `.maic.zip` manifest (classroom-zip-types.ts)."""
    doc = document()
    scenes = []
    for scene in sorted(doc["scenes"], key=lambda s: s["order"]):
        entry = {"type": scene["type"], "title": scene["title"], "order": scene["order"],
                 "content": scene["content"]}
        actions = []
        for action in scene.get("actions") or []:
            action = dict(action)
            if action.get("audioId"):
                action["audioRef"] = ("audio/audio-1.mp3" if action["audioId"] == AUD
                                      else "audio/audio-2.mp3")
                del action["audioId"]
            actions.append(action)
        if actions:
            entry["actions"] = actions
        scenes.append(entry)
    return {
        "formatVersion": 1, "exportedAt": "2026-11-25T00:00:00Z", "appVersion": "1.5.0",
        "stage": {"name": doc["stage"]["name"], "description": doc["stage"]["description"],
                  "createdAt": 1, "updatedAt": 2},
        "agents": [], "scenes": scenes,
        "mediaIndex": {
            "audio/audio-1.mp3": {"type": "audio", "sourceRef": AUD},
            "audio/audio-2.mp3": {"type": "audio", "sourceRef": AUD2},
            "media/asset-1.png": {"type": "image", "sourceRef": IMG},
            "media/asset-2.png": {"type": "image", "sourceRef": IMG2},
            "media/asset-3.mp4": {"type": "generated", "sourceRef": VID},
        },
    }


def maic_zip(manifest_obj: dict | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest_obj or manifest()))
        archive.writestr("audio/audio-1.mp3", MP3)
        archive.writestr("audio/audio-2.mp3", MP3 + b"\x01")
        archive.writestr("media/asset-1.png", PNG)
        archive.writestr("media/asset-2.png", PNG_2)
        archive.writestr("media/asset-3.mp4", MP4)
    return buffer.getvalue()
