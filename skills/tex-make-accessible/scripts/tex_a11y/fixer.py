"""Apply automatic edits to copies of the source files."""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path

from .checks import Analysis
from .findings import Edit, Finding
from .texscan import read_group

SUFFIX = "-accessible"


def output_path(p: Path, suffix: str = SUFFIX) -> Path:
    return p.with_name(p.stem + suffix + p.suffix)


@dataclass
class FixResult:
    outputs: dict[Path, tuple[Path, str]] = field(default_factory=dict)   # original -> (new path, new text)
    applied: list[Finding] = field(default_factory=list)
    conflicts: list[Edit] = field(default_factory=list)
    diff: str = ""


def _apply(text: str, edits: list[Edit]) -> tuple[str, list[Edit]]:
    edits = sorted(edits, key=lambda e: (e.start, 0 if e.start == e.end else 1, e.order))
    out, cursor, skipped = [], 0, []
    for e in edits:
        if e.start < cursor:
            skipped.append(e)
            continue
        out.append(text[cursor:e.start])
        out.append(e.text)
        cursor = e.end
    out.append(text[cursor:])
    return "".join(out), skipped


def fix(analysis: Analysis, main_output: Path | None = None, suffix: str = SUFFIX) -> FixResult:
    proj = analysis.project
    res = FixResult()
    by_file: dict[Path, list[Edit]] = {}
    for f in analysis.findings:
        if f.action == "auto" and f.edits:
            res.applied.append(f)
            for e in f.edits:
                by_file.setdefault(e.path, []).append(e)
        elif f.action == "auto":
            res.applied.append(f)

    # Any file whose included child changes must point at the child's new copy.
    changed = set(by_file)
    grew = True
    while grew:
        grew = False
        for inc in proj.includes:
            if inc.child is not None and inc.child.path in changed and inc.child.path != proj.main.path:
                parent = inc.file
                b = parent.masked.find("{", inc.start, inc.end)
                e = read_group(parent.masked, b) if b != -1 else None
                if e is None:
                    continue
                target = inc.target.strip()
                if target.endswith(".tex"):
                    new_target = target[:-4] + suffix + ".tex"
                else:
                    new_target = target + suffix
                edit = Edit(parent.path, b + 1, e - 1, new_target)
                lst = by_file.setdefault(parent.path, [])
                if not any(x.start == edit.start and x.end == edit.end for x in lst):
                    lst.append(edit)
                    if parent.path not in changed:
                        changed.add(parent.path)
                        grew = True

    diffs = []
    for path, edits in by_file.items():
        src = proj.files[path]
        new_text, skipped = _apply(src.text, edits)
        res.conflicts.extend(skipped)
        if path == proj.main.path:
            dest = main_output or output_path(path, suffix)
        else:
            dest = output_path(path, suffix)
        if new_text == src.text and path != proj.main.path:
            continue
        res.outputs[path] = (dest, new_text)
        diffs.extend(difflib.unified_diff(
            src.text.splitlines(keepends=True), new_text.splitlines(keepends=True),
            fromfile=proj.rel(src), tofile=_rel(dest, proj.root)))
    res.diff = "".join(d if d.endswith("\n") else d + "\n" for d in diffs)
    return res


def _rel(p: Path, root: Path) -> str:
    try:
        return str(p.resolve().relative_to(root))
    except ValueError:
        return str(p)


def write(res: FixResult) -> None:
    for _, (dest, text) in res.outputs.items():
        dest.write_text(text, encoding="utf-8")
