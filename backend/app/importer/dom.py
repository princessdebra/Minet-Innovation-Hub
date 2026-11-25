"""A deliberately small HTML tree, built on the standard library.

Enough to walk an imported lesson, find its sections, headings and media, and
serialise fragments back out. Not a browser-grade parser -- it does not need to
be, because everything it emits is sanitised before it is stored.
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Iterator, Optional

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
             "meta", "param", "source", "track", "wbr"}
DROP_TAGS = {"script", "style", "noscript", "template"}
HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")


@dataclass
class Node:
    tag: str                                   # "" for a text node
    attrs: dict = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)
    text: str = ""
    parent: Optional["Node"] = None

    # -- queries ------------------------------------------------------------

    @property
    def is_text(self) -> bool:
        return self.tag == ""

    def walk(self) -> Iterator["Node"]:
        yield self
        for child in self.children:
            yield from child.walk()

    def find_all(self, *tags: str) -> list["Node"]:
        wanted = {t.lower() for t in tags}
        return [n for n in self.walk() if n.tag in wanted]

    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").lower().split())

    def inner_text(self) -> str:
        parts = []
        for node in self.walk():
            if node.is_text:
                parts.append(node.text)
            elif node.tag in ("br", "p", "div", "li") and parts:
                parts.append(" ")
        return " ".join("".join(parts).split())

    # -- serialisation ------------------------------------------------------

    def to_html(self) -> str:
        if self.is_text:
            return html.escape(self.text, quote=False)
        if self.tag in DROP_TAGS:
            return ""
        attrs = "".join(
            f' {k}="{html.escape(str(v), quote=True)}"' for k, v in self.attrs.items()
            if v is not None)
        if self.tag in VOID_TAGS:
            return f"<{self.tag}{attrs}>"
        inner = "".join(child.to_html() for child in self.children)
        if not self.tag:
            return inner
        return f"<{self.tag}{attrs}>{inner}</{self.tag}>"

    def inner_html(self) -> str:
        return "".join(child.to_html() for child in self.children)


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node(tag="#root")
        self._stack = [self.root]
        self._dropping = 0

    def _current(self) -> Node:
        return self._stack[-1]

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in DROP_TAGS:
            self._dropping += 1
            return
        if self._dropping:
            return
        node = Node(tag=tag, attrs={k.lower(): v for k, v in attrs if k}, parent=self._current())
        self._current().children.append(node)
        if tag not in VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if tag in DROP_TAGS or self._dropping:
            return
        node = Node(tag=tag, attrs={k.lower(): v for k, v in attrs if k}, parent=self._current())
        self._current().children.append(node)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in DROP_TAGS:
            self._dropping = max(0, self._dropping - 1)
            return
        if self._dropping or tag in VOID_TAGS:
            return
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data):
        if self._dropping or not data.strip():
            # Keep inter-word spacing but drop pure layout whitespace.
            if data and not data.strip() and not self._dropping:
                self._current().children.append(Node(tag="", text=" "))
            return
        self._current().children.append(Node(tag="", text=data, parent=self._current()))


def parse(markup: str) -> Node:
    builder = _Builder()
    try:
        builder.feed(markup)
        builder.close()
    except Exception:
        # A malformed document still yields whatever was built before the error.
        pass
    return builder.root


def title_of(root: Node) -> Optional[str]:
    for node in root.find_all("title"):
        text = node.inner_text().strip()
        if text:
            return text[:200]
    for tag in HEADINGS:
        for node in root.find_all(tag):
            text = node.inner_text().strip()
            if text:
                return text[:200]
    return None
