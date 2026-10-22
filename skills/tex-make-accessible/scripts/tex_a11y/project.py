"""Load a LaTeX project (main file plus \\input/\\include files) and walk it in document order."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .texscan import LineIndex, find_commands, mask

INCLUDE_CMDS = ("input", "include", "subfile")


@dataclass
class SourceFile:
    path: Path
    text: str
    masked: str = ""
    lines: LineIndex | None = None

    def __post_init__(self) -> None:
        self.masked = mask(self.text)
        self.lines = LineIndex(self.text)

    def line(self, pos: int) -> int:
        assert self.lines is not None
        return self.lines.line(pos)


@dataclass
class Include:
    file: SourceFile          # file containing the \input
    start: int
    end: int
    target: str               # argument as written
    child: SourceFile | None  # None if not found


@dataclass
class Project:
    main: SourceFile
    root: Path
    files: dict[Path, SourceFile] = field(default_factory=dict)
    includes: list[Include] = field(default_factory=list)

    def rel(self, f: SourceFile) -> str:
        try:
            return str(f.path.relative_to(self.root))
        except ValueError:
            return str(f.path)


def _resolve(root: Path, name: str) -> Path | None:
    name = name.strip()
    cands = [root / name]
    if not name.endswith(".tex"):
        cands.insert(0, root / (name + ".tex"))
    for c in cands:
        if c.is_file():
            return c.resolve()
    return None


def load(main_path: str | Path) -> Project:
    main_path = Path(main_path).resolve()
    root = main_path.parent
    main = SourceFile(main_path, main_path.read_text(encoding="utf-8", errors="replace"))
    proj = Project(main=main, root=root, files={main_path: main})
    stack = [main]
    while stack:
        f = stack.pop()
        for cmd in INCLUDE_CMDS:
            for c in find_commands(f.masked, cmd, "m"):
                target = c.arg_text(f.text, 0) or ""
                if "#" in target or "\\" in target:
                    continue  # inside a macro definition
                p = _resolve(root, target)
                child = None
                if p is not None:
                    child = proj.files.get(p)
                    if child is None:
                        child = SourceFile(p, p.read_text(encoding="utf-8", errors="replace"))
                        proj.files[p] = child
                        stack.append(child)
                proj.includes.append(Include(f, c.start, c.end, target, child))
    return proj


@dataclass
class Span:
    """A piece of one file, in document order."""
    file: SourceFile
    start: int
    end: int
    in_preamble: bool


def walk(proj: Project) -> list[Span]:
    """Return the document as an ordered list of spans, expanding includes.

    Each span records whether it lies before \\begin{document}.
    """
    by_file: dict[Path, list[Include]] = {}
    for inc in proj.includes:
        by_file.setdefault(inc.file.path, []).append(inc)
    spans: list[Span] = []
    state = {"preamble": True}
    seen: set[Path] = set()

    def visit(f: SourceFile) -> None:
        if f.path in seen:
            return
        seen.add(f.path)
        pos = 0
        incs = sorted(by_file.get(f.path, []), key=lambda i: i.start)
        for inc in incs + [None]:
            end = inc.start if inc else len(f.text)
            _emit(f, pos, end)
            if inc is None:
                break
            if inc.child is not None:
                visit(inc.child)
            pos = inc.end
        seen.discard(f.path)

    def _emit(f: SourceFile, a: int, b: int) -> None:
        if state["preamble"]:
            m = re.compile(r"\\begin\s*\{document\}").search(f.masked, a, b)
            if m:
                spans.append(Span(f, a, m.start(), True))
                state["preamble"] = False
                spans.append(Span(f, m.start(), b, False))
                return
        spans.append(Span(f, a, b, state["preamble"]))

    visit(proj.main)
    return spans


def begin_document(proj: Project) -> int | None:
    m = re.search(r"\\begin\s*\{document\}", proj.main.masked)
    return m.start() if m else None
