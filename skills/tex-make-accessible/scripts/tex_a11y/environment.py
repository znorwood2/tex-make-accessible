"""Find out which TeX Live release the user has."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

REQUIRED_YEAR = 2026


def texlive_year(main: Path, override: int | None = None) -> tuple[int | None, str]:
    """Return (year or None, where the answer came from)."""
    if override:
        return override, "--texlive option"
    exe = shutil.which("lualatex")
    if exe:
        try:
            out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=20).stdout
        except (OSError, subprocess.SubprocessError):
            out = ""
        m = re.search(r"TeX Live (\d{4})", out)
        if m:
            return int(m.group(1)), "lualatex --version"
        if "MiKTeX" in out:
            return None, "MiKTeX (version not checked)"
    log = main.with_suffix(".log")
    if log.is_file():
        try:
            first = log.read_text(encoding="utf-8", errors="replace").splitlines()[0]
        except (OSError, IndexError):
            first = ""
        m = re.search(r"TeX Live (\d{4})", first)
        if m:
            return int(m.group(1)), f"{log.name}"
    return None, "not found"
