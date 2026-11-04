---
name: tex-make-accessible
description: Make LaTeX documents compile to accessible, tagged PDFs that meet WCAG 2.1 AA and score well in Anthology Ally (Canvas). Use when someone wants to remediate, fix or check a .tex file (worksheet, exam, syllabus, problem set, lecture notes, Beamer slides) for accessibility; asks why Canvas/Ally gives their LaTeX PDF a low score; or asks about \DocumentMetadata, tagged PDF, alt text for figures, table headers, LuaLaTeX tagging errors, or converting Beamer to ltx-talk or the exam class to article.
---

# Make LaTeX documents accessible

You help instructors, mostly mathematicians who know LaTeX but not PDF accessibility, turn their LaTeX source into tagged PDFs.

- **Target:** WCAG 2.1 AA.
- **First milestone:** a 100% Ally score in Canvas.
- **Scripts do the mechanical work; you make the judgment calls:** alt text, table headers, headings, hard cases.

The department guidance this skill follows is at https://zachnorwood.github.io/math-resources-e4d30825c35241edbce4876eb472905a/ (the "resource page"). Link to its sections rather than contradicting it.

## Ground rules

- **Never overwrite the user's files.** The scripts write `NAME-accessible.tex` plus a diff. Make your own edits in that copy too.
- **Never claim a document is "compliant" or "accessible".** Say what passes automated checks and what a person still has to review: alt-text accuracy, reading order, how the math reads.
- **Usable math comes before a perfect score.** If a student using a screen reader is involved, prefer what works for them (see `math/alt/use` below).
- **Ask before risky or visible choices:**
  - changing the document class;
  - converting Beamer or the exam class;
  - replacing fonts;
  - anything that changes how the document looks.

  Make the safe fixes without asking.
- **Keep the author's style.** Change only what accessibility needs, mark your edits with a `% tex-a11y:` comment, and list every visible change in your summary.
- **Treat the user's documents as their property.** Don't quote them to anyone else or reuse their content in examples.
- **Requirements:** TeX Live 2026 and LuaLaTeX. Don't support older releases. If `lualatex --version` shows an older year, stop and explain how to install TeX Live 2026; the resource page has steps. `tlmgr update` does not move to a new year.

## The preamble every document gets

`\DocumentMetadata` must be the first thing in the file, before `\documentclass`:

```latex
\DocumentMetadata{
  lang = en-US,
  pdfversion = 2.0,
  tagging = on,
  pdfstandard = ua-2,
  tagging-setup = {math/setup=mathml-SE, math/alt/use}
}
```

- **`lang`:** set it to the document's language. The script reads it from babel/polyglossia; ask if unsure.
- **`math/alt/use`:** a compromise for Ally, which doesn't yet recognize embedded MathML. If a student who uses a screen reader will read the document, leave it out (`--no-math-alt`) and keep `math/setup=mathml-SE`. See the resource page's "MathML and math/alt/use" section.
- **The PDF title must be set.** Ally reads the Info dictionary title, so use `\hypersetup{pdftitle={...}}` with a human-readable title.
- **Compile with LuaLaTeX,** twice, or three times if there's a table of contents. With `\printindex`, run `makeindex` before the last pass.

## Workflow

### 1. Intake

Get every file the document needs: the main `.tex`, every `\input`/`\include` file, images, custom `.sty`/`.cls`/macro files, and `.bib`.

If `check` reports `GRAPHICS_MISSING`, ask for the images before writing alt text. If they can't be had now, test the tagging in a scratch folder with blank stand-in images of the same names (never in the user's folder). Draft alt text from the math and context, and list those figures as unverified.

Ask only what you need:
- Where do they compile (local TeX Live 2026 or Overleaf with TeX Live 2026 and LuaLaTeX)?
- Is a student who uses a screen reader involved?
- Do they have an Ally report? The score, issue texts and "Increase score up to N%" figures help you prioritize.

For a syllabus or similar text with little math, mention that a Canvas page may be less work than LaTeX.

### 2. Check

If you can run code, run the checker from this skill's folder:

```sh
python3 scripts/tex-a11y check main.tex --json      # add --texlive 2026 if lualatex isn't installed here
```

It needs only Python 3.9+. Findings come in five groups:
- **blocker:** stop and decide first;
- **auto:** `fix` will change it;
- **judgment:** you decide;
- **manual:** the author or you edit it;
- **info.**

They're ranked by Ally score impact: tagging, then contrast, figures, headings, tables, language, title. `scripts/README.md` lists the options.

If you can't run code (some free accounts), read the source yourself against the checklist in "Without code execution" below.

### 3. Hard cases: stop and ask

| Situation | What to tell the user / ask |
|---|---|
| **Beamer** (`CLASS_BEAMER`) | Beamer can't be tagged. Offer to convert to `ltx-talk` (see recipe below), warning that it changes quickly and the theme won't carry over. The alternative is an accessible handout or notes version. |
| **`exam` class** (`CLASS_EXAM`) | It's incompatible with tagging. Ask how much layout must survive: **content only** (convert to `article` with lists); **some layout** (rebuild point values, answer space, header; list what will look different); or **exact appearance** (keep the original for printing and make a separate accessible version). |
| **`amsart` with `\tableofcontents`** (`AMSART_TOC`) | It breaks tagging. Offer to switch to `article` (recipe below) or drop the contents (PDF bookmarks still give an outline). |
| **Other unsupported class or package** (`CLASS_UNSUPPORTED`, `PACKAGE_NO_SUPPORT`) | Name it, say what it does in the document, and propose a replacement. Check `data/packages.json` and https://latex3.github.io/tagging-project/tagging-status/. |
| **TeX Live older than 2026** | Stop; explain how to install TeX Live 2026. |
| **Scanned or handwritten pages** | Out of scope here; point to the resource page's "Handwritten content" section. |

### 4. Fix

```sh
python3 scripts/tex-a11y fix main.tex      # writes main-accessible.tex and main-accessible.diff
```

**What it changes automatically:**
- the preamble above, and the LuaLaTeX magic comment;
- `pdftitle` from `\title`;
- `hyperref` loaded, and loaded last;
- `inputenc`, `fontenc` and `lmodern` removed;
- `enumitem`/`enumerate` removed, with short labels like `[(a)]` rewritten as `[label=(\alph*)]`;
- text colours below 4.5:1 contrast darkened, including hyperref link colours;
- `$$...$$` changed to `\[...\]`;
- equation shortcuts such as `\beq` written out;
- `center` removed around display math;
- missing proof levels declared;
- `\ref` in headings changed to `\ref*`;
- unused tagging-incompatible packages (`xy`, `amscd`, `framed`, `mdframed`) removed;
- `\newtheorem*{X*}` removed where `\newtheorem{X}` already gives the same unnumbered `X*` under tagging.

It keeps line endings and converts Latin-1 files to UTF-8. Show the user the summary, not the whole diff.

### 5. Judgment items (your job)

Work in the `-accessible` copy. Show proposed alt text and heading names to the user before finalizing.

- **`ALT_MISSING`, `ALT_FILENAME`, `ALT_WEAK`:** write alt text. Look at the image if you can (render it if needed), and use the caption and surrounding text from the finding's `data`. See `reference/alt-text.md`.
  - Purely decorative graphics get `artifact` instead: `\includegraphics[artifact]{logo}`.
  - For TikZ: `\begin{tikzpicture}[alt={...}]`.
- **An image that is a table of data** (scanned or exported): replace it with a real `tabular`, keeping the image line as a comment. Alt text can't carry a table.
- **`TABLE_NO_HEADERS`:** decide whether it's a data table, and which rows/columns are headers:
  - `\tagpdfsetup{table/header-rows={1}}` (or `{1,2}`, or `table/header-columns={1}`) before the table;
  - for a layout-only table, `\tagpdfsetup{table/tagging=presentation}`.
  - These settings persist until changed, so reset them (`table/header-rows={}`) or put the table in a group.
- **A data table typed as a math `array`:** rewrite it as a `tabular` with `$...$` cells and header settings.
- **`HEADINGS_NONE`, `FAKE_HEADING`:** documents of 3+ pages need real headings.
  - Turn bold or large lines that start sections into `\section*{...}`.
  - To keep the look, redefine `\section` with `\@startsection` (e.g. normal-size bold). Use a display heading (positive after-skip), not run-in, if a box or list follows.
  - For long problem sets, group problems (`\section*{Problems 1–10}`).
- **`HEADING_START`, `HEADING_SKIP`:** the first heading must be the top level (`\section` in article, `\chapter` in report/book), and levels must not be skipped. Move headings up a level; mention that they'll look different.
- **`TITLE_MISSING`:** propose a title (the finding may include one from the first bold line) and set `pdftitle`.
- **`LINK_TEXT`:** replace "here" or bare URLs with text saying where the link goes.
- **`FONT_SUGGEST`:** pdfLaTeX font packages (`txfonts`, `mathptmx`, `newtx*`, `MinionPro`, ...).
  - Replace them with `\usepackage{unicode-math}` and OpenType fonts loaded after `amsmath`, using the suggestion in the finding.
  - Remove `amssymb` too.
  - This changes the look, so ask. It's often necessary: `txfonts` under LuaLaTeX silently loses bold.
- **`PACKAGE_INCOMPATIBLE`:** a warning, not a verdict. `fix` already removes some unused ones (`PACKAGE_UNUSED`: `xy`, `amscd`, `framed`, `mdframed`); for others, check whether the document uses the package and remove it if not. Otherwise compile and inspect. Read the status note: some problems only affect one engine. For example, `framed` loses content after a page break under pdfLaTeX and XeLaTeX, and in testing (25 boxes in 117 pages of notes) it compiled and tagged cleanly under LuaLaTeX, so keep it if the boxes have no titles.
- **`HEADING_IN_THEOREM`:** a heading inside an example, theorem or proof breaks the heading tree for the rest of the document. Move it above the environment, or turn it into a run-in label (`\par\medskip\noindent\textbf{Discussion Question.}`).
- **`CLASS_PARTIAL` (amsart):** usually compiles; confirm the PDF title appears. Offer `article` only if there's a problem.
- **`CONTRAST_NEAR_WHITE`:** white or hidden text. Remove hidden text; for text on dark boxes, prefer dark text on a light box.

### 6. Compile

If you have LuaLaTeX, compile yourself; otherwise ask the user to, and to paste errors back. Read the log, not just the exit code: tagging problems often appear only as `tagpdf` warnings.

- **Errors** (`!` lines, "para hooks differ", "can not be closed", "instance ... unknown"): look them up in `reference/compile-errors.md`. Some errors were already in the original (a stray `\item`, say); compile it without `\DocumentMetadata` to tell them apart.
- **Warnings** such as `Parent-Child ... Relation is not allowed` for MathML are minor; mention them, but they don't block.
- **Check the page count:** a document that grows past 3 pages under LuaLaTeX now needs headings.

### 7. Verify

- **`pdfcheck --canvas file.pdf`** (https://github.com/znorwood2/pdfcheck; `pip install -e .`) predicts Ally's issues and score.
- **`pdfcheck --full file.pdf`** adds a manual-review checklist.
- **veraPDF (optional)** checks PDF/UA-2.

Ally's own report after upload is the final word. Report predicted scores as predictions.

### 8. Hand-off

Give a short summary:
- what changed, grouped (preamble, figures, tables, headings, fonts, other);
- every visible change;
- what the author must review: alt-text accuracy, decorative vs. informative images, reading order, math;
- predicted score.

Remind them that Ally scans every file in Canvas Files, including unpublished ones, so old inaccessible versions and instructor-only copies belong elsewhere. Mention content typos you noticed, without fixing them.

## Recipes

**Beamer to `ltx-talk`** (needs LaTeX 2025-11-01 or later; TeX Live 2026 qualifies):
1. `\documentclass[aspect-ratio=4:3, 10pt]{ltx-talk}`. 4:3 matches Beamer's default; the only sizes are 10, 11 and 12pt.
2. Remove `\usetheme`, `\useinnertheme`, `\usecolortheme`, `\setbeamertemplate`, `\setbeamercolor` and `\insert...` hacks. Tell the user the theme isn't recreated.
3. `ltx-talk` loads `amsmath`, `unicode-math` (sans-serif New Computer Modern), `hyperref`, `xcolor`, `graphicx` and `geometry`. Remove those, plus font packages, `amssymb` and `amsthm` (its `\newtheorem` would replace `ltx-talk`'s overlay-aware one).
4. Beamer predefines `theorem`, `example`, `definition` and so on; `ltx-talk` doesn't. Add `\newtheorem{theorem}{Theorem}` etc. for the ones used.
5. `\titlepage` becomes `\maketitle`. `frame`, `\frametitle`, `\pause`, `\only`, `\onslide`, `\uncover`, `\visible`, `\alert`, `block`, `columns`/`column`, `\section` and `thebibliography` work as in Beamer.
6. Fix overfull lines (the size is usually larger than before).
7. Build two PDFs:
   - the projector version;
   - a handout (add `handout` to the class options: one page per slide). **Post the handout in Canvas.** The projector version draws not-yet-revealed text transparent, which pdfcheck counts as a contrast failure; Ally's behaviour there is untested.

**`amsart` to `article`:**
- Change the class (drop options article doesn't know).
- Load what amsart loaded itself: `\usepackage{amsmath,amsthm}`, and `\usepackage{makeidx}` if the document uses `\printindex`.
- Remove `\title`'s optional short-title argument.
- Add stand-ins for amsart-only commands, e.g. `\newcommand{\address}[1]{...}` and `\newcommand{\email}[1]{...}` printing at the end as amsart does.
- The layout changes (page size, margins, heading styles); say so. amsart's run-in `\subsection` becomes a display heading.

**`mdframed` to `tcolorbox`** (mdframed is not supported):

```latex
\usepackage{tcolorbox}
\newtcolorbox{mdframed}[1][]{colback=white, colframe=black, boxrule=0.4pt, sharp corners,
  left=10pt, right=10pt, top=4pt, bottom=4pt, #1}
```

The body stays unchanged. Put headings outside boxes, not inside.

**Personal macro files loaded from absolute paths** (e.g. `\InputIfFileExists{/Users/...}`): you can't see them, so ask for them, or tell the user what to check in them. With `unicode-math`, macros that measure math symbols in the preamble need `\AtBeginDocument{...}`.

## Without code execution

If you can't run the scripts (some free accounts), apply the same checks by reading the source, in this order:
1. `\DocumentMetadata` first, as above.
2. No text colour lighter than `#767676` (watch `gray`, `lightgray`, `black!NN` below about 54, light link colours, white text).
3. Every `\includegraphics` and `tikzpicture` has `alt=` or `artifact`.
4. Documents of 3+ pages have real headings, starting at the top level, without skipped levels.
5. Data tables with 3+ rows declare header rows or columns.
6. `pdftitle` is set.
7. No `$$`, no display math inside `center`, no `\beq`-style shortcuts.
8. Packages are on the tagging status list.

Then give the user the edits and ask them to compile and paste back the log or `pdfcheck` output.

For very long documents, ask the user to run `python3 scripts/tex-a11y fix main.tex` themselves and paste the report. Its judgment items are short and self-contained, so they fit in a free-tier conversation.

## Files in this skill

- `scripts/tex-a11y`: the checker and fixer (`check`, `fix`). Usage in `scripts/README.md`.
- `data/packages.json`: package and class tagging status, generated from the LaTeX Project's list.
- `data/fonts.json`: pdfLaTeX font packages and their OpenType replacements.
- `reference/compile-errors.md`: LuaLaTeX tagging errors and their fixes.
- `reference/alt-text.md`: how to write alt text for math graphics.
