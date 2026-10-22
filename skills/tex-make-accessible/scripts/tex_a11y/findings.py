"""Data types shared by the checks, the fixer and the report."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Order of Ally score impact (docs/ally-findings.md), used to rank findings.
RANK_TAGGING = 1
RANK_CONTRAST = 2
RANK_FIGURES = 3
RANK_HEADINGS = 4
RANK_TABLES = 5
RANK_MATH_ALT = 6
RANK_LANG = 7
RANK_HEADING_START = 8
RANK_TITLE = 9
RANK_HEADING_SKIP = 10
RANK_OTHER = 20

SEVERITIES = ("blocker", "error", "warning", "info")

# What happens to a finding:
#   auto      `tex-a11y fix` changes the source
#   confirm   the script has a proposal; a person or the AI confirms it
#   judgment  needs a person or the AI (alt text, table headers, ...)
#   manual    needs a person to edit the source (no proposal)
#   none      information only
ACTIONS = ("auto", "confirm", "judgment", "manual", "none")


@dataclass
class Edit:
    path: Path
    start: int
    end: int
    text: str
    order: int = 50  # for insertions at the same position: lower goes first


@dataclass
class Finding:
    code: str
    severity: str
    action: str
    rank: int
    message: str
    file: str | None = None
    line: int | None = None
    hint: str | None = None
    edits: list[Edit] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        d = {
            "code": self.code,
            "severity": self.severity,
            "action": self.action,
            "rank": self.rank,
            "message": self.message,
        }
        for k in ("file", "line", "hint"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        if self.data:
            d["data"] = self.data
        return d
