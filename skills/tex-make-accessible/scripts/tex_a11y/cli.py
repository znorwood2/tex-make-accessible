"""Command-line interface: tex-a11y check | fix."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .checks import Options, analyze
from .fixer import fix, output_path, write
from .report import json_report, text_report


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("main", help="the main .tex file (the one with \\documentclass)")
    p.add_argument("--lang", help="document language tag for \\DocumentMetadata, e.g. en-US or de-DE")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--no-math-alt", dest="math_alt", action="store_false", default=None,
                   help="leave out math/alt/use (better for screen readers that support MathML; Ally may score lower)")
    g.add_argument("--math-alt", dest="math_alt", action="store_true",
                   help="include math/alt/use (the default; helps the Ally score)")
    p.add_argument("--texlive", type=int, metavar="YEAR", help="TeX Live year where you compile, if not detectable here")
    p.add_argument("--json", action="store_true", help="print a JSON report instead of text")
    p.add_argument("-v", "--verbose", action="store_true", help="also list information-only items")


def _options(a: argparse.Namespace) -> Options:
    return Options(lang=a.lang, math_alt=a.math_alt, texlive=a.texlive)


def cmd_check(a: argparse.Namespace) -> int:
    analysis = analyze(a.main, _options(a))
    if a.json:
        print(json_report(analysis))
    else:
        print(text_report(analysis, f"tex-a11y check: {a.main}", a.verbose))
    bad = any(f.severity in ("blocker", "error") for f in analysis.findings)
    return 1 if bad else 0


def cmd_fix(a: argparse.Namespace) -> int:
    main = Path(a.main)
    analysis = analyze(main, _options(a))
    if any(f.code == "NOT_MAIN_FILE" for f in analysis.findings):
        print(text_report(analysis, f"tex-a11y fix: {a.main}", a.verbose))
        return 2
    out = Path(a.output) if a.output else None
    res = fix(analysis, main_output=out)
    dest_main = res.outputs.get(analysis.project.main.path, (out or output_path(main.resolve()), ""))[0]
    diff_path = dest_main.with_suffix(".diff")
    if res.conflicts:
        print(f"Note: {len(res.conflicts)} automatic edit(s) overlapped another and were skipped; run fix again on the output.",
              file=sys.stderr)
    if not res.diff:
        msg = "No automatic fixes needed."
        if a.json:
            print(json_report(analysis, {"written": [], "message": msg}))
        else:
            print(text_report(analysis, f"tex-a11y fix: {a.main}", a.verbose))
            print(msg)
        return 0
    if a.dry_run:
        sys.stdout.write(res.diff)
        return 0
    write(res)
    diff_path.write_text(res.diff, encoding="utf-8")
    written = [str(d) for d, _ in res.outputs.values()]
    if a.json:
        print(json_report(analysis, {"written": written, "diff": str(diff_path)}))
    else:
        print(text_report(analysis, f"tex-a11y fix: {a.main}", a.verbose))
        print("Wrote:")
        for w in written:
            print(f"  {w}")
        print(f"  {diff_path} (all changes)")
        print("Your original files are unchanged. Next: compile the -accessible file with LuaLaTeX (twice).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tex-a11y", description="Check and fix LaTeX source for accessible (tagged) PDFs.")
    ap.add_argument("--version", action="version", version=f"tex-a11y {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)
    pc = sub.add_parser("check", help="report problems; changes nothing")
    _common(pc)
    pc.set_defaults(func=cmd_check)
    pf = sub.add_parser("fix", help="apply automatic fixes to a copy of the source")
    _common(pf)
    pf.add_argument("-o", "--output", help="path for the fixed main file (default: NAME-accessible.tex)")
    pf.add_argument("--dry-run", action="store_true", help="print the changes as a diff without writing files")
    pf.set_defaults(func=cmd_fix)
    a = ap.parse_args(argv)
    if not Path(a.main).is_file():
        ap.error(f"file not found: {a.main}")
    return a.func(a)
