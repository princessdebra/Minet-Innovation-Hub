"""What an import did, and what it could not do.

Nothing is ever discarded silently: anything the mapper could not place lands
in `unsupported` and is surfaced to the administrator for review.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImportReport:
    source: str = ""
    modules: int = 0
    lessons: int = 0
    blocks: int = 0
    media_files: int = 0
    media_bytes: int = 0
    questions: int = 0
    unsupported: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped_files: list[dict] = field(default_factory=list)
    already_imported: bool = False
    assets_reused: int = 0
    decorative_skipped: int = 0

    def unsupported_item(self, kind: str, detail: str, where: str = "") -> None:
        self.unsupported.append({"kind": kind, "detail": detail[:500], "where": where[:200]})

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message[:500])

    def skip_file(self, name: str, reason: str) -> None:
        self.skipped_files.append({"name": name[:255], "reason": reason[:200]})

    @property
    def needs_review(self) -> bool:
        return bool(self.unsupported or self.skipped_files)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "modules": self.modules,
            "lessons": self.lessons,
            "blocks": self.blocks,
            "media_files": self.media_files,
            "media_bytes": self.media_bytes,
            "questions": self.questions,
            "unsupported": self.unsupported[:200],
            "warnings": self.warnings[:50],
            "skipped_files": self.skipped_files[:200],
            "already_imported": self.already_imported,
            "assets_reused": self.assets_reused,
            "decorative_skipped": self.decorative_skipped,
            "needs_review": self.needs_review,
        }
