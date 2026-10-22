"""All source checks. Each check adds Findings; automatic fixes carry Edits."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import colors as col
from .environment import REQUIRED_YEAR, texlive_year
from .findings import (
    RANK_CONTRAST, RANK_FIGURES, RANK_HEADING_SKIP, RANK_HEADING_START, RANK_HEADINGS,
    RANK_LANG, RANK_MATH_ALT, RANK_OTHER, RANK_TABLES, RANK_TAGGING, RANK_TITLE, Edit, Finding,
)
from .project import Project, SourceFile, Span, begin_document, walk
from .texscan import Command, find_commands, parse_args, parse_keyvals, plain_text, read_group, split_top_level

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

RESOURCE_PAGE = "https://zachnorwood.github.io/math-resources-e4d30825c35241edbce4876eb472905a/"


def page(anchor: str = "") -> str:
    """Link to a named section of the department resource page."""
    return RESOURCE_PAGE + (f"#{anchor}" if anchor else "")

# Packages that must (or may) be loaded after hyperref.
AFTER_HYPERREF = {
    "cleveref", "autonum", "hypcap", "bookmark", "glossaries", "glossaries-extra", "hyperxmp",
    "doi", "algorithm", "algorithmic", "algpseudocode", "nameref", "zref-hyperref", "uniquecounter",
}
BOOKLIKE_CLASSES = {"report", "book", "memoir", "scrreprt", "scrbook", "amsbook"}
TABLE_ENVS = ("tabular", "tabular*", "tabularx", "tabulary", "longtable", "array")
HEADING_LEVELS = {"chapter": 0, "section": 1, "subsection": 2, "subsubsection": 3, "paragraph": 4, "subparagraph": 5}
ENUMITEM_PREAMBLE_CMDS = ("setlist", "newlist", "renewlist", "setitemize", "setenumerate", "setdescription",
                          "SetEnumitemKey", "SetEnumitemValue", "AddEnumerateCounter", "SetLabelAlign")

LANG_MAP = {
    "english": "en-US", "american": "en-US", "usenglish": "en-US", "british": "en-GB", "ukenglish": "en-GB",
    "canadian": "en-CA", "australian": "en-AU", "french": "fr-FR", "francais": "fr-FR", "german": "de-DE",
    "ngerman": "de-DE", "austrian": "de-AT", "naustrian": "de-AT", "swissgerman": "de-CH", "spanish": "es-ES",
    "italian": "it-IT", "portuguese": "pt-PT", "portuges": "pt-PT", "brazilian": "pt-BR", "brazil": "pt-BR",
    "dutch": "nl-NL", "polish": "pl-PL", "russian": "ru-RU", "ukrainian": "uk-UA", "czech": "cs-CZ",
    "slovak": "sk-SK", "swedish": "sv-SE", "danish": "da-DK", "norsk": "nb-NO", "norwegian": "nb-NO",
    "finnish": "fi-FI", "greek": "el-GR", "turkish": "tr-TR", "hungarian": "hu-HU", "magyar": "hu-HU",
    "romanian": "ro-RO", "croatian": "hr-HR", "catalan": "ca-ES", "japanese": "ja-JP", "chinese": "zh-CN",
    "korean": "ko-KR", "hebrew": "he-IL", "arabic": "ar", "vietnamese": "vi-VN", "indonesian": "id-ID",
}

IMAGE_EXT_RE = re.compile(r"\.(png|jpe?g|pdf|eps|svg|gif|tiff?|bmp|webp)\s*$", re.I)
GENERIC_ALT = {"image", "figure", "picture", "graph", "diagram", "plot", "photo", "img", "chart", "drawing", "illustration"}


@dataclass
class Options:
    lang: str | None = None
    math_alt: bool | None = None     # None: keep the document's choice, default on
    texlive: int | None = None


@dataclass
class PackageLoad:
    file: SourceFile
    cmd: Command
    options: str
    names: list[str]
    name_spans: list[tuple[int, int]]   # absolute spans of each name in the file


@dataclass
class Analysis:
    project: Project
    findings: list[Finding] = field(default_factory=list)

    def add(self, f: Finding) -> Finding:
        self.findings.append(f)
        return f


def _load_json(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def _cmds_in_spans(spans: list[Span], name: str, spec: str = "") -> list[tuple[SourceFile, Command, bool]]:
    out = []
    for sp in spans:
        for c in find_commands(sp.file.masked, name, spec, sp.start, sp.end):
            out.append((sp.file, c, sp.in_preamble))
    return out


def _own_lines(f: SourceFile, start: int, end: int) -> bool:
    """True if nothing but whitespace shares the lines of text[start:end]."""
    ls = f.text.rfind("\n", 0, start) + 1
    le = f.text.find("\n", end)
    le = len(f.text) if le == -1 else le
    return not f.masked[ls:start].strip() and not f.masked[end:le].strip()


def _whole_line_span(f: SourceFile, start: int, end: int) -> tuple[int, int]:
    ls = f.text.rfind("\n", 0, start) + 1
    le = f.text.find("\n", end)
    le = len(f.text) if le == -1 else le + 1
    return ls, le


def _comment_out(f: SourceFile, start: int, end: int, reason: str) -> Edit:
    """Edit that replaces a statement with a comment saying what was removed."""
    original = " ".join(f.text[start:end].split())
    if _own_lines(f, start, end):
        return Edit(f.path, start, end, f"% tex-a11y removed: {original} ({reason})")
    return Edit(f.path, start, end, "")


class Checker:
    def __init__(self, proj: Project, opts: Options):
        self.p = proj
        self.o = opts
        self.a = Analysis(proj)
        self.spans = walk(proj)
        self.pre = [s for s in self.spans if s.in_preamble]
        self.body = [s for s in self.spans if not s.in_preamble]
        self.bd = begin_document(proj)
        self.packages_db = _load_json("packages.json")
        self.fonts_db = _load_json("fonts.json")
        self.loads: list[PackageLoad] = []
        self.doc_class: str | None = None
        self.class_options: list[str] = []
        self.class_cmd: Command | None = None
        # Text inserted just before \begin{document}, in this order.
        self.end_preamble_lines: dict[str, list[str]] = {"hyperref": [], "colors": [], "hypersetup": []}
        self.hypersetup_items: list[str] = []

    # ---------- helpers ----------
    def loc(self, f: SourceFile, pos: int) -> tuple[str, int]:
        return self.p.rel(f), f.line(pos)

    def add(self, code, severity, action, rank, message, f=None, pos=None, hint=None, edits=None, data=None):
        file, line = self.loc(f, pos) if f is not None and pos is not None else (None, None)
        return self.a.add(Finding(code, severity, action, rank, message, file, line, hint, edits or [], data or {}))

    def loaded(self, name: str) -> list[PackageLoad]:
        return [l for l in self.loads if name in l.names]

    # ---------- run ----------
    def run(self) -> Analysis:
        self.read_class_and_packages()
        if self.doc_class is None:
            self.add("NOT_MAIN_FILE", "blocker", "manual", RANK_TAGGING,
                     "No \\documentclass found. Run tex-a11y on the main .tex file of the document.",
                     hint="Pass the file that contains \\documentclass and \\begin{document}.")
            return self.a
        if self.doc_class == "standalone":
            self.add("STANDALONE_FIGURE", "info", "none", RANK_FIGURES,
                     "This is a standalone figure file. It is compiled on its own and included in another document "
                     "as an image, so it does not need tagging itself. Give it alt text where it is included "
                     "(\\includegraphics[alt={...}]{...}).", self.p.main, self.class_cmd.start if self.class_cmd else 0)
            return self.a
        self.check_texlive()
        self.check_includes()
        self.check_class()
        self.check_metadata()
        self.check_engine_comment()
        self.check_packages()
        self.check_hyperref()
        self.check_title()
        self.check_contrast()
        self.check_figures()
        self.check_tables()
        self.check_headings()
        self.check_display_math()
        self.check_links()
        self.finish_end_preamble()
        return self.a

    # ---------- class and packages ----------
    def read_class_and_packages(self) -> None:
        cls = find_commands(self.p.main.masked, "documentclass", "om")
        if cls:
            c = cls[0]
            self.class_cmd = c
            self.doc_class = (c.arg_text(self.p.main.masked, 1) or "").strip()
            opt = c.arg_text(self.p.main.masked, 0) or ""
            self.class_options = [o.strip() for o in split_top_level_str(opt)]
        for name in ("usepackage", "RequirePackage"):
            for f, c, pre in _cmds_in_spans(self.pre, name, "om"):
                inner_s, inner_e = c.args[1].inner
                raw = f.masked[inner_s:inner_e]
                names, spans = [], []
                for a, b in split_top_level(raw):
                    nm = raw[a:b].strip()
                    if nm:
                        lead = len(raw[a:b]) - len(raw[a:b].lstrip())
                        names.append(nm)
                        spans.append((inner_s + a + lead, inner_s + a + lead + len(nm)))
                self.loads.append(PackageLoad(f, c, c.arg_text(f.masked, 0) or "", names, spans))
        self.loads.sort(key=lambda l: (self._order(l.file, l.cmd.start)))

    def _order(self, f: SourceFile, pos: int) -> int:
        """Global document-order index for a position."""
        total = 0
        for sp in self.spans:
            if sp.file is f and sp.start <= pos <= sp.end:
                return total + (pos - sp.start)
            total += sp.end - sp.start
        return total

    def check_texlive(self) -> None:
        year, source = texlive_year(self.p.main.path, self.o.texlive)
        if year is None:
            self.add("TEXLIVE_UNKNOWN", "warning", "manual", RANK_TAGGING,
                     f"Could not determine the TeX Live version ({source}). Tagging needs TeX Live {REQUIRED_YEAR} or later.",
                     hint="Run `lualatex --version` where you compile, or pass --texlive YEAR.")
        elif year < REQUIRED_YEAR:
            self.add("TEXLIVE_OLD", "blocker", "manual", RANK_TAGGING,
                     f"TeX Live {year} is too old (found via {source}). Install TeX Live {REQUIRED_YEAR}.",
                     hint="`tlmgr update --self --all` does not move to a new year; install the new release. "
                          f"See {page('latex-setup-details')}")

    def check_includes(self) -> None:
        for inc in self.p.includes:
            if inc.child is None:
                self.add("INCLUDE_MISSING", "warning", "manual", RANK_OTHER,
                         f"Included file '{inc.target}' was not found, so it was not checked.",
                         inc.file, inc.start)

    def check_class(self) -> None:
        name = self.doc_class or ""
        f, pos = self.p.main, self.class_cmd.start if self.class_cmd else 0
        rec = self.packages_db["class"].get(name)
        status = rec.get("status") if rec else None
        comment = (rec or {}).get("comments")
        if name == "beamer":
            self.add("CLASS_BEAMER", "blocker", "manual", RANK_TAGGING,
                     "Beamer is not supported by LaTeX tagging and will not be. Tagged slides need the ltx-talk class, "
                     "which is still changing quickly.",
                     f, pos, hint="Ask the user whether to convert to ltx-talk at their own risk, or to make an "
                                  f"accessible handout or notes version instead. See {page('latex')} (Beamer and slides).")
        elif name == "exam":
            self.add("CLASS_EXAM", "blocker", "manual", RANK_TAGGING,
                     "The exam class is incompatible with LaTeX tagging. The document needs converting to article.",
                     f, pos, hint="Ask the user how much of the exam layout must be kept: content only, some layout, "
                                  "or exact appearance (keep the original for printing and make a separate accessible version).")
        elif status in ("currently-incompatible", "no-support"):
            self.add("CLASS_UNSUPPORTED", "blocker", "manual", RANK_TAGGING,
                     f"Document class '{name}' is {status} with LaTeX tagging." + (f" Note: {comment}" if comment else ""),
                     f, pos, hint="Consider switching to article (or report/book) and recreating the needed layout.")
        elif status == "partially-compatible":
            extra = " With amsart, the PDF title is known to go missing (Ally: 'does not have a title')." if name in ("amsart", "amsproc") else ""
            self.add("CLASS_PARTIAL", "warning", "confirm", RANK_TAGGING,
                     f"Document class '{name}' is only partially compatible with tagging.{extra}" + (f" Note: {comment}" if comment else ""),
                     f, pos, hint="Switching to article usually works for short documents; confirm with the user.")
        elif status is None:
            self.add("CLASS_UNKNOWN", "warning", "manual", RANK_TAGGING,
                     f"Document class '{name}' is not in the LaTeX tagging status list, so its tagging support is unknown.",
                     f, pos)

    # ---------- \DocumentMetadata ----------
    def guess_lang(self) -> tuple[str | None, str | None]:
        """Language from babel/polyglossia, as (BCP 47 tag, babel name)."""
        for l in self.loaded("babel"):
            opts = [o.strip() for o in split_top_level_str(l.options)]
            main = None
            for o in opts:
                if o.startswith("main="):
                    main = o.split("=", 1)[1].strip()
            langs = [o for o in opts if o and "=" not in o and o.lower() in LANG_MAP]
            if not langs and not main:
                langs = [o for o in self.class_options if o.lower() in LANG_MAP]
            name = main or (langs[-1] if langs else None)
            if name:
                return LANG_MAP.get(name.lower()), name
        for cmdname in ("setmainlanguage", "setdefaultlanguage"):
            for f, c, _ in _cmds_in_spans(self.pre, cmdname, "om"):
                name = (c.arg_text(f.masked, 1) or "").strip()
                return LANG_MAP.get(name.lower()), name
        return None, None

    def check_metadata(self) -> None:
        f = self.p.main
        text, masked = f.text, f.masked
        first_code = len(masked) - len(masked.lstrip())
        dm = find_commands(masked, "DocumentMetadata", "m")
        cls_pos = self.class_cmd.start if self.class_cmd else len(text)
        guess, babel_name = self.guess_lang()

        existing: dict[str, str | None] = {}
        extra_items: list[str] = []
        setup_extra: list[str] = []
        has_mathml = False
        has_alt = False
        if dm:
            c = dm[0]
            raw = c.arg_text(masked, 0) or ""
            for k, v, (a, b) in parse_keyvals(raw):
                existing[k] = v
                if k == "tagging-setup" and v is not None:
                    for k2, v2, (a2, b2) in parse_keyvals(v):
                        if k2 == "math/setup":
                            has_mathml = (v2 or "").strip() == "mathml-SE"
                        elif k2 == "math/alt/use":
                            has_alt = True
                        else:
                            setup_extra.append(v[a2:b2].strip())
                elif k not in ("lang", "pdfversion", "tagging", "pdfstandard", "testphase", "tagging-setup"):
                    extra_items.append(raw[a:b].strip())

        lang = self.o.lang or existing.get("lang") or guess or "en-US"
        if self.o.math_alt is not None:
            math_alt = self.o.math_alt
        elif dm and has_mathml:
            math_alt = has_alt  # respect a deliberate choice
        else:
            math_alt = True
        setup = ["math/setup=mathml-SE"] + (["math/alt/use"] if math_alt else []) + setup_extra
        block_lines = [
            "\\DocumentMetadata{",
            f"  lang = {lang},",
            "  pdfversion = 2.0,",
            "  tagging = on,",
            "  pdfstandard = ua-2,",
        ]
        for item in extra_items:
            block_lines.append(f"  {item},")
        block_lines.append("  tagging-setup = {" + ", ".join(setup) + "}")
        block_lines.append("}")
        block = "\n".join(block_lines)

        # Language reports.
        if existing.get("lang") and guess and existing["lang"].split("-")[0].lower() != guess.split("-")[0].lower():
            self.add("LANG_MISMATCH", "warning", "confirm", RANK_LANG,
                     f"\\DocumentMetadata says lang={existing['lang']} but babel/polyglossia main language is "
                     f"'{babel_name}' ({guess}). Ally checks that the language matches the text.",
                     f, dm[0].start if dm else 0, hint="Confirm the document's main language; rerun with --lang TAG.")
        elif existing.get("lang") and not re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*", existing["lang"] or ""):
            self.add("LANG_MALFORMED", "error", "manual", RANK_LANG,
                     f"lang={existing['lang']} is not a valid language tag (use e.g. en-US).", f, dm[0].start)
        elif not self.o.lang and not existing.get("lang") and not guess:
            self.add("LANG_ASSUMED", "info", "confirm", RANK_LANG,
                     "No language found in the source; the fix assumes English (en-US).",
                     hint="If the document is not in English, rerun with --lang TAG (e.g. --lang de-DE).")

        if not dm:
            self.add("METADATA_MISSING", "error", "auto", RANK_TAGGING,
                     "No \\DocumentMetadata, so the PDF will be untagged (Ally score 12 at most).",
                     f, first_code,
                     edits=[Edit(f.path, first_code, first_code, block + "\n", order=10)])
            self._math_alt_note(math_alt)
            return

        c = dm[0]
        changes = []
        def norm(v): return (v or "").replace(" ", "").lower()
        if existing.get("lang") != lang:
            changes.append(f"lang {existing.get('lang') or '(none)'} → {lang}")
        if norm(existing.get("pdfversion")) != "2.0":
            changes.append(f"pdfversion {existing.get('pdfversion') or '(none)'} → 2.0")
        if norm(existing.get("tagging")) != "on":
            changes.append(f"tagging {existing.get('tagging') or '(none)'} → on")
        if "testphase" in existing:
            changes.append(f"removed testphase={existing.get('testphase')} (replaced by tagging=on)")
        if norm(existing.get("pdfstandard")) != "ua-2":
            changes.append(f"pdfstandard {existing.get('pdfstandard') or '(none)'} → ua-2")
        if not has_mathml:
            changes.append("tagging-setup: math/setup=mathml-SE added")
        if has_alt != math_alt:
            changes.append("math/alt/use " + ("added" if math_alt else "removed"))
        misplaced = c.start != first_code or c.start > cls_pos

        if changes or misplaced:
            edits = []
            if misplaced:
                ls, le = _whole_line_span(f, c.start, c.end) if _own_lines(f, c.start, c.end) else (c.start, c.end)
                edits.append(Edit(f.path, ls, le, ""))
                edits.append(Edit(f.path, first_code, first_code, block + "\n", order=10))
            else:
                edits.append(Edit(f.path, c.start, c.end, block))
            msg = "\\DocumentMetadata needs updating: " + "; ".join(changes) if changes else ""
            if misplaced:
                msg = (msg + ". " if msg else "") + "\\DocumentMetadata must come first, before \\documentclass and any other code."
            serious = misplaced or norm(existing.get("tagging")) != "on"
            self.add("METADATA_UPDATE", "error" if serious else "warning",
                     "auto", RANK_TAGGING, msg, f, c.start, edits=edits)
        self._math_alt_note(math_alt)

    def _math_alt_note(self, math_alt: bool) -> None:
        if math_alt:
            self.add("MATH_ALT_COMPROMISE", "info", "confirm", RANK_MATH_ALT,
                     "The preamble uses math/alt/use: every formula also gets a flat alt-text string. "
                     "This is a compromise for Ally, which does not yet recognize embedded MathML.",
                     hint="If a student who uses a screen reader will read this document, rerun with --no-math-alt "
                          f"(MathML stays on). See {page('math-alt-use')}")
        else:
            self.add("MATH_ALT_OFF", "info", "none", RANK_MATH_ALT,
                     "math/alt/use is off: formulas are tagged as MathML only. Better for screen readers that "
                     "support MathML, but Ally may lower the score.")

    def check_engine_comment(self) -> None:
        f = self.p.main
        m = re.search(r"^%\s*!\s*TEX\s+(?:TS-)?program\s*=\s*(\S+)[^\n]*$", f.text, re.I | re.M)
        if m:
            if m.group(1).lower() != "lualatex":
                self.add("ENGINE_COMMENT", "warning", "auto", RANK_TAGGING,
                         f"The magic comment selects {m.group(1)}; tagging needs LuaLaTeX.", f, m.start(),
                         edits=[Edit(f.path, m.start(1), m.end(1), "lualatex")])
        else:
            self.add("ENGINE_COMMENT", "info", "auto", RANK_TAGGING,
                     "Added `% !TEX TS-program = lualatex` so editors that read it compile with LuaLaTeX. "
                     "Check your editor or latexmk settings too.", f, 0,
                     edits=[Edit(f.path, 0, 0, "% !TEX TS-program = lualatex\n", order=0)])

    # ---------- packages ----------
    def check_packages(self) -> None:
        remove = self.fonts_db["remove"]
        suggest = self.fonts_db["suggest"]
        handled = set(remove) | set(suggest) | {"enumitem", "hyperref"}
        all_masked = "\n".join(sf.masked for sf in self.p.files.values())
        for l in self.loads:
            f, c = l.file, l.cmd
            to_remove = [n for n in l.names if n in remove]
            if to_remove:
                reasons = "; ".join(remove[n] for n in to_remove)
                if len(to_remove) == len(l.names):
                    edit = _comment_out(f, c.start, c.end, "not needed with LuaLaTeX")
                else:
                    keep = [n for n in l.names if n not in to_remove]
                    a, b = c.args[1].inner
                    edit = Edit(f.path, a, b, ",".join(keep))
                self.add("FONT_PDFTEX", "warning", "auto", RANK_OTHER,
                         f"Removed {', '.join(to_remove)}: {reasons}", f, c.start, edits=[edit])
            for n in l.names:
                if n in suggest:
                    self.add("FONT_SUGGEST", "warning", "manual", RANK_OTHER,
                             f"Font package '{n}' is written for pdfLaTeX. Under LuaLaTeX use OpenType fonts instead.",
                             f, c.start, hint=f"Suggested replacement: {suggest[n]}")
            if "enumitem" in l.names:
                uses = [cmd for cmd in ENUMITEM_PREAMBLE_CMDS if re.search(r"\\" + cmd + r"(?![A-Za-z])", all_masked)]
                inline = "inline" in l.options or re.search(r"\\begin\{(enumerate|itemize|description)\*\}", all_masked)
                msg = ("enumitem cannot currently be loaded with tagging, but the tagging code supports most of its "
                       "document-level syntax (e.g. \\begin{enumerate}[label=(\\alph*)]).")
                if uses or inline or len(l.names) > 1:
                    if uses:
                        why = "uses " + ", ".join("\\" + u for u in uses)
                    elif inline:
                        why = "uses inline lists"
                    else:
                        why = "loads it together with other packages"
                    self.add("ENUMITEM", "warning", "manual", RANK_OTHER,
                             msg + f" The document {why}, so it needs a manual change.", f, c.start,
                             hint="Remove \\usepackage{enumitem} and move list settings into each list's options.")
                else:
                    self.add("ENUMITEM", "warning", "auto", RANK_OTHER,
                             msg + " Removed \\usepackage{enumitem}; list options in the body are kept.", f, c.start,
                             edits=[_comment_out(f, c.start, c.end, "tagging supports its list syntax without the package")])
            for n in l.names:
                if n in handled:
                    continue
                rec = self.packages_db["package"].get(n)
                status = rec.get("status") if rec else None
                comment = (rec or {}).get("comments")
                note = f" Note: {comment}" if comment else ""
                if status == "no-support":
                    self.add("PACKAGE_NO_SUPPORT", "error", "manual", RANK_TAGGING,
                             f"Package '{n}' is not supported by LaTeX tagging and is not expected to be.{note}", f, c.start,
                             hint="Remove it or replace it; check the tagging status list for alternatives.")
                elif status == "currently-incompatible":
                    self.add("PACKAGE_INCOMPATIBLE", "warning", "manual", RANK_TAGGING,
                             f"Package '{n}' is currently incompatible with tagging: it may cause compile errors or "
                             f"wrong or missing tags.{note}", f, c.start,
                             hint="Check whether the document really needs it; if it does, check the compiled PDF carefully.")
                elif status == "partially-compatible":
                    self.add("PACKAGE_PARTIAL", "info", "none", RANK_OTHER,
                             f"Package '{n}' is partially compatible with tagging.{note}", f, c.start)
                elif status == "unchecked" or status is None:
                    self.add("PACKAGE_UNKNOWN", "info", "none", RANK_OTHER,
                             f"Package '{n}' has not been checked by the tagging project"
                             + (" (not in the status list)." if status is None else "."), f, c.start)

    # ---------- hyperref ----------
    def check_hyperref(self) -> None:
        hl = self.loaded("hyperref")
        main = self.p.main
        if not hl:
            after = [l for l in self.loads if set(l.names) & AFTER_HYPERREF]
            if after and after[0].file is main and _own_lines(main, after[0].cmd.start, after[0].cmd.end):
                ls, _ = _whole_line_span(main, after[0].cmd.start, after[0].cmd.end)
                edit = Edit(main.path, ls, ls, "\\usepackage{hyperref}\n", order=5)
                self.add("HYPERREF_MISSING", "warning", "auto", RANK_TITLE,
                         "hyperref is not loaded; added it (before packages that must follow it). "
                         "It is needed to set the PDF title.", main, ls, edits=[edit])
            elif after:
                self.add("HYPERREF_MISSING", "warning", "manual", RANK_TITLE,
                         "hyperref is not loaded. Load it before " + ", ".join(sorted(set(after[0].names) & AFTER_HYPERREF)) + ".",
                         after[0].file, after[0].cmd.start)
            else:
                self.end_preamble_lines["hyperref"].append("\\usepackage{hyperref}")
                self.add("HYPERREF_MISSING", "warning", "auto", RANK_TITLE,
                         "hyperref is not loaded; added it at the end of the preamble. It is needed to set the PDF title.",
                         main, self.bd or 0)
            return
        h = hl[-1]
        idx = self.loads.index(h)
        later = [l for l in self.loads[idx + 1:] if not set(l.names) <= AFTER_HYPERREF]
        if not later:
            return
        names = sorted({n for l in later for n in l.names})
        last_plain = later[-1]
        between_after = [l for l in self.loads[idx + 1:self.loads.index(last_plain)] if set(l.names) & AFTER_HYPERREF]
        can_move = (
            h.file is main and h.names == ["hyperref"] and _own_lines(main, h.cmd.start, h.cmd.end)
            and all(l.file is main for l in later) and not between_after
            and _own_lines(main, last_plain.cmd.start, last_plain.cmd.end)
        )
        if can_move:
            seg = main.masked[h.cmd.end:last_plain.cmd.end]
            if re.search(r"\\(hypersetup|urlstyle|href|url|autoref|pdfbookmark|phantomsection|hyperref|hypertarget)(?![A-Za-z])", seg):
                can_move = False
        msg = f"hyperref should be loaded last, but {', '.join(names)} come after it."
        if can_move:
            ls, le = _whole_line_span(main, h.cmd.start, h.cmd.end)
            _, tgt = _whole_line_span(main, last_plain.cmd.start, last_plain.cmd.end)
            stmt = main.text[ls:le]
            if not stmt.endswith("\n"):
                stmt += "\n"
            self.add("HYPERREF_NOT_LAST", "warning", "auto", RANK_OTHER, msg + " Moved it after them.", main, h.cmd.start,
                     edits=[Edit(main.path, ls, le, ""), Edit(main.path, tgt, tgt, stmt, order=5)])
        else:
            self.add("HYPERREF_NOT_LAST", "warning", "manual", RANK_OTHER,
                     msg + " Move \\usepackage{hyperref} after them (but before cleveref and similar packages).",
                     h.file, h.cmd.start)

    def _hyperref_keyvals(self) -> list[tuple[SourceFile, int, int, str, str | None]]:
        """All hyperref settings (options and \\hypersetup), as (file, abs start, abs end, key, value)."""
        out = []
        for l in self.loaded("hyperref"):
            if l.cmd.args[0].present:
                s, _ = l.cmd.args[0].inner
                for k, v, (a, b) in parse_keyvals(l.options):
                    out.append((l.file, s + a, s + b, k, v))
        for f, c, _ in _cmds_in_spans(self.spans, "hypersetup", "m"):
            s, _ = c.args[0].inner
            for k, v, (a, b) in parse_keyvals(c.arg_text(f.masked, 0) or ""):
                out.append((f, s + a, s + b, k, v))
        return out

    # ---------- title ----------
    def check_title(self) -> None:
        kv = self._hyperref_keyvals()
        pdftitles = [(f, a, v) for f, a, b, k, v in kv if k == "pdftitle"]
        titles = _cmds_in_spans(self.spans, "title", "om")
        if pdftitles:
            f, a, v = pdftitles[-1]
            v = (v or "").strip()
            if not v or IMAGE_EXT_RE.search(v) or re.search(r"\.(tex|pdf)$", v, re.I):
                self.add("PDFTITLE_BAD", "error", "judgment", RANK_TITLE,
                         f"pdftitle is '{v}', which is empty or looks like a filename.", f, a,
                         hint="Use a human-readable title, e.g. 'Math 106 Worksheet 3: Limits'.")
            return
        titles = [t for t in titles if "#" not in (t[1].arg_text(t[0].masked, 1) or "")]
        if titles:
            f, c, _ = titles[-1]
            plain = plain_text(c.arg_text(f.masked, 1) or "")
            if plain:
                safe = plain.replace("#", "\\#").replace("%", "\\%")
                self.hypersetup_items.append(f"pdftitle={{{safe}}}")
                self.add("PDFTITLE_MISSING", "error", "auto", RANK_TITLE,
                         f"No PDF title set. Set pdftitle from \\title: '{plain}'.", f, c.start,
                         hint="Check that the title reads well on its own (Ally and screen readers show it).")
                return
        self.add("TITLE_MISSING", "error", "judgment", RANK_TITLE,
                 "The document has no title (no \\title or pdftitle). Ally reports 'This PDF does not have a title'.",
                 self.p.main, self.bd or 0,
                 hint="Add \\hypersetup{pdftitle={...}} with a meaningful title.",
                 data={"question": "pdftitle", "suggestion": self.p.main.path.stem.replace("_", " ").replace("-", " ")})

    # ---------- contrast ----------
    def check_contrast(self) -> None:
        table = col.ColorTable()
        for f, c, _ in _cmds_in_spans(self.spans, "definecolor", "ommm") + _cmds_in_spans(self.spans, "providecolor", "ommm"):
            table.define(c.arg_text(f.masked, 1) or "", c.arg_text(f.masked, 2) or "", c.arg_text(f.masked, 3) or "")
        for f, c, _ in _cmds_in_spans(self.spans, "colorlet", "omom"):
            table.let(c.arg_text(f.masked, 1) or "", c.arg_text(f.masked, 3) or "")

        new_defs: dict[str, tuple[col.RGB, float, str]] = {}
        unresolved: dict[str, tuple[SourceFile, int]] = {}

        def fixed_name(label: str) -> str:
            return "a11y" + re.sub(r"[^A-Za-z0-9]", "", label)

        def handle(f: SourceFile, pos: int, rgb: col.RGB | None, label: str, span: tuple[int, int], replacement_fmt: str):
            if rgb is None:
                unresolved.setdefault(label, (f, pos))
                return
            rgb = col.quantize(rgb)  # PDFs store 8-bit colour; Ally sees #808080 for xcolor's gray
            ratio = col.contrast_on_white(rgb)
            if ratio >= col.MIN_CONTRAST:
                return
            if ratio < 1.5:
                self.add("CONTRAST_NEAR_WHITE", "warning", "manual", RANK_CONTRAST,
                         f"Text colour '{label}' is white or nearly white (contrast {ratio:.2f}:1 on white). "
                         "Ally flags this even on a dark background or for hidden text.", f, pos,
                         hint="Remove hidden white text; for text on dark boxes, consider dark text on a light box.")
                return
            name = fixed_name(label)
            new = col.darken(rgb)
            new_defs[name] = (new, ratio, label)
            self.add("CONTRAST_LOW", "error", "auto", RANK_CONTRAST,
                     f"Text colour '{label}' has contrast {ratio:.2f}:1 on white (needs 4.5:1). "
                     f"Replaced with a darker shade #{col.to_hex(new)} ({col.contrast_on_white(new):.2f}:1).",
                     f, pos, edits=[Edit(f.path, span[0], span[1], replacement_fmt.format(name=name))])

        for cmdname, spec in (("color", "om"), ("textcolor", "omm")):
            for f, c, _ in _cmds_in_spans(self.spans, cmdname, spec):
                model_arg, spec_arg = c.args[0], c.args[1]
                spec_text = c.arg_text(f.masked, 1) or ""
                if model_arg.present:
                    model = c.arg_text(f.masked, 0) or ""
                    rgb = col.from_model(model, spec_text)
                    handle(f, c.start, rgb, f"[{model}]{{{spec_text}}}", (model_arg.start, spec_arg.end), "{{{name}}}")
                else:
                    if "#" in spec_text or "\\" in spec_text:
                        continue  # macro parameter or macro: can't resolve here
                    handle(f, c.start, table.resolve(spec_text), spec_text.strip(), (spec_arg.start, spec_arg.end), "{{{name}}}")

        # hyperref link colours (only matter with colorlinks).
        kv = self._hyperref_keyvals()
        colorlinks = False
        settings: dict[str, tuple[SourceFile, int, int, str]] = {}
        for f, a, b, k, v in kv:
            if k == "colorlinks":
                colorlinks = v is None or v.strip().lower() == "true"
            elif k in ("linkcolor", "citecolor", "urlcolor", "filecolor"):
                settings[k] = (f, a, b, v or "")
        if colorlinks:
            defaults = {"linkcolor": "red", "citecolor": "green", "urlcolor": "magenta"}
            for key, default in defaults.items():
                if key in settings:
                    f, a, b, v = settings[key]
                    rgb = table.resolve(v)
                    lead = f.text[a:b][: len(f.text[a:b]) - len(f.text[a:b].lstrip())]
                    handle(f, a, rgb, v.strip(), (a, b), lead + key + "={name}")
                else:
                    rgb = col.quantize(table.resolve(default))  # type: ignore[arg-type]
                    ratio = col.contrast_on_white(rgb)  # type: ignore[arg-type]
                    if ratio < col.MIN_CONTRAST:
                        name = fixed_name(default)
                        new = col.darken(rgb)  # type: ignore[arg-type]
                        new_defs[name] = (new, ratio, default)
                        self.hypersetup_items.append(f"{key}={name}")
                        self.add("CONTRAST_LOW", "error", "auto", RANK_CONTRAST,
                                 f"colorlinks is on and {key} defaults to {default} ({ratio:.2f}:1 on white). "
                                 f"Set {key} to a darker shade #{col.to_hex(new)}.", self.p.main, self.bd or 0)

        for label, (f, pos) in unresolved.items():
            self.add("CONTRAST_UNKNOWN", "info", "manual", RANK_CONTRAST,
                     f"Could not work out the colour '{label}'; check that it is at least as dark as #767676.", f, pos)
        for name, (rgb, ratio, label) in new_defs.items():
            r, g, b = (f"{x:.4f}".rstrip("0").rstrip(".") or "0" for x in rgb)
            self.end_preamble_lines["colors"].append(
                f"\\definecolor{{{name}}}{{rgb}}{{{r},{g},{b}}} % tex-a11y: darker {label} (contrast {ratio:.2f} -> {col.contrast_on_white(rgb):.2f})")
        pc = _cmds_in_spans(self.spans, "pagecolor", "om")
        if pc:
            f, c, _ = pc[0]
            self.add("PAGE_COLOR", "warning", "manual", RANK_CONTRAST,
                     "\\pagecolor changes the background, so contrast was checked against the wrong colour.", f, c.start)

    # ---------- figures ----------
    def _caption_near(self, f: SourceFile, pos: int) -> str | None:
        m = re.compile(r"\\end\s*\{(figure\*?|wrapfigure|center|minipage)\}").search(f.masked, pos, pos + 1500)
        stop = m.start() if m else min(len(f.masked), pos + 600)
        caps = find_commands(f.masked, "caption", "om", pos, stop)
        if not caps:
            # caption may precede the graphic
            start = max(0, pos - 600)
            caps = find_commands(f.masked, "caption", "om", start, pos)
        if caps:
            return plain_text(caps[-1].arg_text(f.masked, 1) or "")
        return None

    def _context(self, f: SourceFile, pos: int) -> str:
        before = f.text[max(0, pos - 500):pos]
        para = before.split("\n\n")[-1]
        return plain_text(re.sub(r"%[^\n]*", "", para))[-300:]

    def check_figures(self) -> None:
        for f, c, _ in _cmds_in_spans(self.body + self.pre, "includegraphics", "oom"):
            fname = (c.arg_text(f.masked, 2) or "").strip()
            if "#" in fname:
                continue
            keys = {}
            for i in (0, 1):
                if c.args[i].present:
                    for k, v, _ in parse_keyvals(c.arg_text(f.masked, i) or ""):
                        keys[k] = v
            self._alt_finding(f, c.start, keys, "\\includegraphics", fname)
        for sp in self.spans:
            for m in re.finditer(r"\\begin\s*\{tikzpicture\}", sp.file.masked[sp.start:sp.end]):
                f = sp.file
                pos = sp.start + m.start()
                parsed = parse_args(f.masked, sp.start + m.end(), "o")
                keys = {}
                if parsed and parsed[0][0].present:
                    a = parsed[0][0]
                    for k, v, _ in parse_keyvals(f.masked[a.inner[0]:a.inner[1]]):
                        keys[k] = v
                end = f.masked.find("\\end{tikzpicture}", pos)
                code = f.text[pos:end + len("\\end{tikzpicture}")] if end != -1 else f.text[pos:pos + 1500]
                self._alt_finding(f, pos, keys, "tikzpicture", None, code[:2500])

    def _alt_finding(self, f, pos, keys, kind, fname, code=None) -> None:
        if "artifact" in keys:
            return
        data = {"question": "alt-text", "kind": kind}
        if fname:
            data["image"] = fname
        cap = self._caption_near(f, pos)
        if cap:
            data["caption"] = cap
        ctx = self._context(f, pos)
        if ctx:
            data["context"] = ctx
        if code:
            data["code"] = code
        what = f"{kind}" + (f" '{fname}'" if fname else "")
        alt = keys.get("alt")
        if "alt" not in keys and "actualtext" not in keys:
            why = ("LaTeX would use the filename, which Ally treats as missing." if fname
                   else "Ally reports figures without alt text ('images without description').")
            self.add("ALT_MISSING", "error", "judgment", RANK_FIGURES,
                     f"{what} has no alt text. {why}",
                     f, pos, hint="Add alt={...} describing what a student needs from the figure, or mark a purely "
                                  "decorative graphic with 'artifact'.", data=data)
            return
        alt = (alt or "").strip()
        base = Path(fname).name if fname else ""
        if not alt or IMAGE_EXT_RE.search(alt) or (base and alt in (base, Path(base).stem)):
            self.add("ALT_FILENAME", "error", "judgment", RANK_FIGURES,
                     f"{what} has alt text '{alt}', which is empty or a filename.", f, pos, data=data)
        elif alt.lower().strip(". ") in GENERIC_ALT or len(alt) < 6:
            data["current_alt"] = alt
            self.add("ALT_WEAK", "warning", "judgment", RANK_FIGURES,
                     f"{what} has alt text '{alt}', which Ally accepts but which doesn't describe the figure.",
                     f, pos, data=data)

    # ---------- tables ----------
    def check_tables(self) -> None:
        event_re = re.compile(r"\\(begin|end)\s*\{([^}]+)\}|\\tagpdfsetup\s*(?=\{)")
        stack: list[tuple[str, dict]] = []
        cur = {"rows": None, "cols": None, "presentation": False, "set_at": None, "used": 0}
        for sp in self.body:
            f = sp.file
            pos = sp.start
            while True:
                m = event_re.search(f.masked, pos, sp.end)
                if not m:
                    break
                pos = m.end()
                if m.group(1) is None:  # \tagpdfsetup{...}
                    end = read_group(f.masked, m.end())
                    if end is None:
                        continue
                    body = f.masked[m.end() + 1:end - 1]
                    for k, v, _ in parse_keyvals(body):
                        v = (v or "").strip()
                        if k == "table/header-rows":
                            cur = dict(cur, rows=v or None, set_at=(f, m.start()), used=0)
                        elif k == "table/header-columns":
                            cur = dict(cur, cols=v or None, set_at=(f, m.start()), used=0)
                        elif k == "table/tagging":
                            cur = dict(cur, presentation=(v == "presentation"))
                    pos = end
                    continue
                kind, env = m.group(1), m.group(2).strip()
                if kind == "begin" and env in TABLE_ENVS:
                    end = self._env_end(f, env, m.end())
                    body_text = f.masked[m.end():end] if end else ""
                    rows = _count_rows(body_text)
                    if rows >= 3 and not cur["presentation"]:
                        if not cur["rows"] and not cur["cols"]:
                            sev = "warning" if env == "array" else "error"
                            self.add("TABLE_NO_HEADERS", sev, "judgment", RANK_TABLES,
                                     f"{env} with {rows} rows has no header rows or columns. Ally penalizes data tables "
                                     "(3+ rows) without header cells.", f, m.start(),
                                     hint="If it is a data table, put \\tagpdfsetup{table/header-rows={1}} (or "
                                          "header-columns) before it; if it is only for layout, use table/tagging=presentation.",
                                     data={"question": "table-headers", "env": env, "rows": rows,
                                           "first_rows": _first_rows(f.masked[m.end():end or m.end()], 3)})
                        elif cur["used"] >= 1 and cur["set_at"]:
                            sf, sp_pos = cur["set_at"]
                            self.add("TABLE_INHERITED_HEADERS", "info", "confirm", RANK_TABLES,
                                     f"{env} reuses header settings (rows={cur['rows'] or 'none'}, "
                                     f"columns={cur['cols'] or 'none'}) set at {self.p.rel(sf)}:{sf.line(sp_pos)} "
                                     "for an earlier table. Check they fit this table.", f, m.start(),
                                     data={"question": "table-headers", "env": env, "rows": rows,
                                           "first_rows": _first_rows(f.masked[m.end():end or m.end()], 3)})
                        cur["used"] += 1
                    stack.append((env, dict(cur)))
                    if end:
                        pos = end
                    continue
                if kind == "begin":
                    stack.append((env, dict(cur)))
                elif kind == "end":
                    # restore settings saved at the matching \begin
                    for i in range(len(stack) - 1, -1, -1):
                        if stack[i][0] == env:
                            saved = dict(stack[i][1])
                            del stack[i:]
                            if saved["set_at"] == cur["set_at"]:
                                saved["used"] = max(saved["used"], cur["used"])
                            cur = saved
                            break

    def _env_end(self, f: SourceFile, env: str, pos: int) -> int | None:
        pat = re.compile(r"\\(begin|end)\s*\{" + re.escape(env) + r"\}")
        depth = 1
        for m in pat.finditer(f.masked, pos):
            depth += 1 if m.group(1) == "begin" else -1
            if depth == 0:
                return m.start()
        return None

    # ---------- headings ----------
    def check_headings(self) -> None:
        heads = []
        for name, lvl in HEADING_LEVELS.items():
            for f, c, _ in _cmds_in_spans(self.body, name, "om"):
                heads.append((self._order(f, c.start), lvl, name, f, c))
        heads.sort(key=lambda h: h[0])
        booklike = (self.doc_class in BOOKLIKE_CLASSES) and any(h[1] == 0 for h in heads)
        top = 0 if booklike else 1
        pages, how = self._page_estimate()
        fakes = self._fake_headings()

        if not heads:
            if pages >= 3:
                self.add("HEADINGS_NONE", "error", "judgment", RANK_HEADINGS,
                         f"No headings in a document of about {pages} pages ({how}). Ally penalizes documents of 3+ pages "
                         "without tagged headings.", self.p.main, self.bd or 0,
                         hint="Use \\section (or \\section*) for the document's parts; for a long problem set, group "
                              "problems (e.g. \\section*{Problems 1–10}).",
                         data={"question": "headings", "fake_headings": [x[2] for x in fakes][:30]})
            elif fakes:
                self.add("HEADINGS_NONE", "info", "judgment", RANK_HEADINGS,
                         f"No real headings (about {pages} page(s), {how}). Ally only requires them from 3 pages, "
                         "but headings help screen-reader users navigate.", self.p.main, self.bd or 0)
        else:
            first = heads[0]
            if first[1] > top:
                expected = "\\chapter" if top == 0 else "\\section"
                self.add("HEADING_START", "error", "judgment", RANK_HEADING_START,
                         f"The first heading is \\{first[2]}, but the top level here is {expected}. Ally expects "
                         "headings to start at level 1.", first[3], first[4].start,
                         data={"question": "heading-levels", "outline": self._outline(heads)})
            prev = None
            for h in heads:
                if prev is not None and h[1] > prev + 1:
                    self.add("HEADING_SKIP", "error", "judgment", RANK_HEADING_SKIP,
                             f"\\{h[2]} follows a higher-level heading but skips a level.", h[3], h[4].start,
                             data={"question": "heading-levels", "outline": self._outline(heads)})
                prev = h[1]
        for f, pos, label in fakes:
            self.add("FAKE_HEADING", "warning", "judgment", RANK_HEADINGS,
                     f"'{label}' looks like a heading but is only bold or large text, so it is not tagged as one.",
                     f, pos, hint="If it starts a section, use \\section*{...} (styled to look the same if needed); "
                                  "if it is a run-in label (e.g. 'Problem 3.'), leave it.",
                     data={"question": "fake-heading", "text": label})

    def _outline(self, heads) -> list[str]:
        return [f"{'  ' * max(0, h[1])}\\{h[2]}{{{plain_text(h[4].arg_text(h[3].masked, 1) or '')}}}" for h in heads][:60]

    def _fake_headings(self) -> list[tuple[SourceFile, int, str]]:
        """Lines that consist only of bold/large text, after a paragraph break."""
        pat = re.compile(
            r"[ \t]*(?:\\noindent\s*)?"
            r"(?:\\(?:textbf|textsc|underline)\s*(\{)|(\{)\s*\\(?:bf|bfseries|Large|large|LARGE|huge|Huge|scshape)(?![A-Za-z]))"
        )
        tail = re.compile(r"(\\\\(\[[^\]]*\])?|\\(par|medskip|smallskip|bigskip|newline)(?![A-Za-z])|\\vspace\*?\{[^}]*\}|\s)*")
        out = []
        for sp in self.body:
            f = sp.file
            for m in re.finditer(r"(?m)^.*$", f.masked[sp.start:sp.end]):
                ls = sp.start + m.start()
                le = sp.start + m.end()
                pm = pat.match(f.masked, ls, le)
                if not pm:
                    continue
                g = pm.start(1) if pm.group(1) else pm.start(2)
                e = read_group(f.masked, g)
                if e is None or e > le:
                    continue
                if tail.fullmatch(f.masked, e, le) is None:
                    continue
                # Must start a paragraph: previous line blank, or ends with vertical space.
                prev = f.masked[f.masked.rfind("\n", 0, max(ls - 1, 0)) + 1:max(ls - 1, 0)] if ls > 0 else ""
                if prev.strip() and not re.search(r"\\(par|medskip|bigskip|smallskip|vspace\*?\{[^}]*\}|item)\s*$|\\\\\s*$|\\end\{[^}]*\}\s*$", prev):
                    continue
                label = plain_text(f.masked[g:e]).strip()
                if not 0 < len(label) <= 80:
                    continue
                if re.match(r"^(problem|exercise|question|q|part)\s*\(?[0-9a-z]{1,3}\b", label, re.I):
                    continue
                out.append((f, pm.start(1) if pm.group(1) else pm.start(2), label))
        return out

    def _page_estimate(self) -> tuple[int, str]:
        pdf = self.p.main.path.with_suffix(".pdf")
        if pdf.is_file():
            try:
                raw = pdf.read_bytes()
                n = len(re.findall(rb"/Type\s*/Page(?![s\w])", raw))
                if n:
                    return n, f"counted in {pdf.name}"
            except OSError:
                pass
        words = 0
        displays = 0
        breaks = 0
        for sp in self.body:
            seg = sp.file.masked[sp.start:sp.end]
            words += len(re.findall(r"(?<![\\A-Za-z])[A-Za-z]{2,}", re.sub(r"\\[A-Za-z@]+", " ", seg)))
            displays += len(re.findall(r"\\\[|\\begin\{(equation|align|gather|multline)", seg))
            breaks += len(re.findall(r"\\(newpage|clearpage|pagebreak)\b", seg))
            displays += 4 * len(re.findall(r"\\(includegraphics|begin\{tikzpicture\})", seg))
        est = max(breaks + 1, round(words / 400 + displays * 0.06))
        return max(1, est), "estimated from the source; compile first for an exact count"

    # ---------- $$ ----------
    def check_display_math(self) -> None:
        for sp in self.body:
            f = sp.file
            seg = f.masked
            positions = []
            i = sp.start
            while True:
                j = seg.find("$$", i, sp.end)
                if j == -1:
                    break
                k = j - 1
                bs = 0
                while k >= 0 and seg[k] == "\\":
                    bs += 1
                    k -= 1
                if bs % 2 == 0:
                    positions.append(j)
                    i = j + 2
                else:
                    i = j + 1
            if len(positions) % 2:
                self.add("DOLLAR_UNPAIRED", "warning", "manual", RANK_OTHER,
                         "Found an odd number of $$ signs; the last one has no partner. Check the display math "
                         "around here (or a literal $ that should be written \\$).", f, positions[-1])
            for a, b in zip(positions[0::2], positions[1::2]):
                inner = seg[a + 2:b]
                if "$" in inner.replace("\\$", ""):
                    continue
                self.add("DOLLAR_DISPLAY", "warning", "auto", RANK_OTHER,
                         "$$...$$ is plain-TeX display math; replaced with \\[...\\].", f, a,
                         edits=[Edit(f.path, a, a + 2, "\\["), Edit(f.path, b, b + 2, "\\]")])

    # ---------- links ----------
    def check_links(self) -> None:
        bad = {"here", "click here", "link", "this link", "this", "website", "this website", "page", "this page", "url"}
        for f, c, _ in _cmds_in_spans(self.body, "href", "omm"):
            url = (c.arg_text(f.masked, 1) or "").strip()
            txt = plain_text(c.arg_text(f.masked, 2) or "")
            if txt.lower().strip(". ") in bad or txt.strip() == url:
                self.add("LINK_TEXT", "warning", "judgment", RANK_OTHER,
                         f"Link text '{txt}' does not say where the link goes (WCAG 2.4.4).", f, c.start,
                         data={"question": "link-text", "url": url, "text": txt})

    # ---------- end of preamble ----------
    def finish_end_preamble(self) -> None:
        lines = []
        lines += self.end_preamble_lines["hyperref"]
        lines += self.end_preamble_lines["colors"]
        if self.hypersetup_items:
            lines.append("\\hypersetup{" + ", ".join(self.hypersetup_items) + "}")
        if not lines or self.bd is None:
            return
        main = self.p.main
        ls = main.text.rfind("\n", 0, self.bd) + 1
        if main.masked[ls:self.bd].strip():
            ls = self.bd
        block = "% tex-a11y: added for accessibility\n" + "\n".join(lines) + "\n"
        # Attach the edit to the first finding that needs it (any auto finding is fine).
        self.a.add(Finding("PREAMBLE_ADDITIONS", "info", "auto", RANK_OTHER,
                           "Added settings at the end of the preamble: " + "; ".join(l.split(" %")[0] for l in lines),
                           self.p.rel(main), main.line(ls), edits=[Edit(main.path, ls, ls, block, order=90)]))


def split_top_level_str(s: str) -> list[str]:
    return [s[a:b] for a, b in split_top_level(s)] if s else []


def _row_breaks(masked_body: str) -> list[int]:
    out = []
    depth = 0
    i = 0
    while i < len(masked_body):
        ch = masked_body[i]
        if ch == "\\":
            if i + 1 < len(masked_body) and masked_body[i + 1] == "\\" and depth == 0:
                out.append(i)
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    return out


def _count_rows(masked_body: str) -> int:
    breaks = _row_breaks(masked_body)
    tail = masked_body[breaks[-1] + 2:] if breaks else masked_body
    tail = re.sub(r"\\(hline|bottomrule|midrule|toprule|cline\{[^}]*\}|endlastfoot|end\{[^}]*\})", "", tail)
    tail = re.sub(r"^\s*\{[^{}]*\}", "", tail)  # column spec when no rows
    return len(breaks) + (1 if tail.strip() and breaks else 0)


def _first_rows(body: str, n: int) -> list[str]:
    breaks = _row_breaks(body)
    # skip the column spec {lcr}
    start = 0
    m = re.match(r"\s*(\[[^\]]*\])?\s*\{", body)
    if m:
        e = read_group(body, m.end() - 1)
        start = e or 0
    rows = []
    prev = start
    for b in breaks[:n]:
        rows.append(" ".join(body[prev:b].split()))
        prev = b + 2
    return rows


def analyze(main: str | Path, opts: Options | None = None) -> Analysis:
    from .project import load
    proj = load(main)
    return Checker(proj, opts or Options()).run()
