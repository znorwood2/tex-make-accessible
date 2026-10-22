"""Human-readable and JSON reports."""

from __future__ import annotations

import json
import textwrap

from .checks import Analysis
from .findings import SEVERITIES, Finding

GROUPS = [
    ("blocker", "Stop and decide first", lambda f: f.severity == "blocker"),
    ("auto", "Automatic fixes (applied by `tex-a11y fix`)", lambda f: f.action == "auto"),
    ("judgment", "Needs judgment (the AI or you)", lambda f: f.action in ("judgment", "confirm") and f.severity != "info"),
    ("manual", "Needs a manual change", lambda f: f.action == "manual" and f.severity in ("error", "warning")),
    ("info", "For information", lambda f: True),
]


def _sorted(fs: list[Finding]) -> list[Finding]:
    return sorted(fs, key=lambda f: (f.rank, SEVERITIES.index(f.severity), f.file or "", f.line or 0))


def group(findings: list[Finding]) -> list[tuple[str, str, list[Finding]]]:
    remaining = list(findings)
    out = []
    for key, title, pred in GROUPS:
        mine = [f for f in remaining if pred(f)]
        remaining = [f for f in remaining if f not in mine]
        out.append((key, title, _sorted(mine)))
    return out


def _fmt(f: Finding, width: int = 100) -> str:
    where = f"{f.file}:{f.line}" if f.file else "-"
    head = f"  [{f.severity}] {where}  {f.message}"
    lines = textwrap.wrap(head, width=width, subsequent_indent="      ")
    if f.hint:
        lines += textwrap.wrap("-> " + f.hint, width=width, initial_indent="      ", subsequent_indent="         ")
    return "\n".join(lines)


def text_report(analysis: Analysis, title: str, verbose: bool = False) -> str:
    out = [title, ""]
    groups = group(analysis.findings)
    for key, heading, fs in groups:
        if not fs:
            continue
        if key == "info" and not verbose:
            out.append(f"{heading}: {len(fs)} item(s) (use --verbose to list them)")
            continue
        out.append(f"{heading} ({len(fs)}):")
        out.extend(_fmt(f) for f in fs)
        out.append("")
    counts = {k: len(fs) for k, _, fs in groups}
    out.append(
        f"Summary: {counts['blocker']} to decide first, {counts['auto']} automatic, "
        f"{counts['judgment']} need judgment, {counts['manual']} manual."
    )
    return "\n".join(out).rstrip() + "\n"


def json_report(analysis: Analysis, extra: dict | None = None) -> str:
    groups = group(analysis.findings)
    d = {
        "main": analysis.project.rel(analysis.project.main),
        "summary": {k: len(fs) for k, _, fs in groups},
        "findings": [f.to_json() for _, _, fs in groups for f in fs],
    }
    if extra:
        d.update(extra)
    return json.dumps(d, indent=2, ensure_ascii=False)
