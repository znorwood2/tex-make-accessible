# Plan: a skill for making LaTeX documents accessible

## Goal

A shareable AI skill that helps math faculty and grad students fix their LaTeX source so it compiles to accessible, tagged PDFs.

- **Target:** WCAG 2.1 AA.
- **First milestone:** a 100% Anthology Ally score in Canvas. That's what colleagues will see, and it covers the biggest problems.
- **Beyond Ally:** good alt text (Ally only checks that alt text exists and isn't a filename), usable math, link text and reading order.
- **Usable math comes before a perfect score.** This follows UNL's FAQ and the department resource page.
- **Never claim "compliant."** The skill reports "passes automated checks; a person still needs to review: …".

**Sources:**
- The [department resource page](https://zachnorwood.github.io/math-resources-e4d30825c35241edbce4876eb472905a/) is the colleague-facing guidance. The skill must agree with it and link to its sections, not contradict or duplicate it.
- [`docs/ally-findings.md`](docs/ally-findings.md) holds 62 controlled Ally scores from the [`pdfcheck`](https://github.com/znorwood2/pdfcheck) project. Advice keeps that document's labels: measured, inferred or untested.

## Audience and context

- Colleagues in the UNL math department who write LaTeX but aren't accessibility experts.
- **Documents:** syllabi, exams, worksheets, problem sets, lecture notes and papers. `article` and similar classes come first. Exams need a conversion step, and Beamer slides are a warn-and-ask case (see "Hard cases").
- **Accounts:** many colleagues won't have paid Claude accounts. The university's ChatGPT Edu accounts use Skills (Custom GPTs are retired there). The design must work with limited tools.
- **Local TeX first.** The first versions assume TeX Live 2026 on the user's machine. Overleaf also offers TeX Live 2026, so it's a small step later (see "Overleaf").

## Architecture

1. **One repo, one skill, open `SKILL.md` format.** Claude and ChatGPT Skills read the same files. Platform differences go in the install docs, not in separate copies.
2. **Scripts do the mechanical work; the AI makes the judgment calls.** Scripts produce a JSON report. `SKILL.md` tells the model to run them, work through the judgment items, have the user recompile, re-check and summarize.
3. **Package compatibility is data, not code.** `data/packages.yaml` lists each package's tagging status, safe alternatives and notes. It starts from the LaTeX Project's [tagging status list](https://latex3.github.io/tagging-project/tagging-status/). New findings become pull requests to this file.
4. **Detect liberally, fix conservatively.** Regex parsing of TeX is fragile. Scripts flag problems widely but make only safe, repeatable edits (such as inserting the preamble). They never overwrite the original; they write a copy plus a diff.
5. **Python standard library only.** The scripts must run in Claude's and ChatGPT's sandboxes without installs.
6. **Require TeX Live 2026.** Supporting older installs would mean tracking individual LaTeX kernel releases, so the skill doesn't try. The check script reads the TeX Live year (`tex --version`, or the `.log` banner). If it is older, it stops and points to the resource page's installation section. It also reminds users that `tlmgr update --self --all` updates packages within a release but doesn't upgrade to a new year.
7. **One canonical preamble, shared with the resource page:**

   ```latex
   \DocumentMetadata{
     lang = en-US,
     pdfversion = 2.0,
     tagging = on,
     pdfstandard = ua-2,
     tagging-setup = {math/setup=mathml-SE, math/alt/use}
   }
   ```

   - `templates/article.tex` is the page's `tagged-pdf-example.tex`.
   - `math/alt/use` is an Ally compromise: Ally doesn't yet recognize embedded MathML. The skill explains this, and drops the option if a student who uses a screen reader is involved, keeping `math/setup=mathml-SE`.
   - When the page's block changes, the skill's copy changes in the same week. A test checks that the template and `reference/preamble.md` agree.
8. **The Ally findings predate the current preamble.** The experiments used `testphase=latest`. The skill uses `tagging=on` with PDF 2.0, as the page does. Phase 2 re-runs a few `pdfcheck` probes with the canonical preamble to confirm the findings still hold.

## Workflow (what `SKILL.md` tells the model)

The AI sandbox probably lacks TeX Live 2026, so compiling happens on the user's machine:

```
check script → AI edits a copy → user compiles (LuaLaTeX, twice)
     ↑                                         ↓
     └── AI fixes ← pdfcheck / veraPDF report ←┘
```

1. **Intake.**
   - Collect all `.tex` files (follow `\input`/`\include`), the class, the packages and the TeX Live version.
   - Ask for the Ally report if there is one: score, issue texts and the "Increase score up to N%" figures.
   - Ask whether a student using a screen reader is involved (this decides `math/alt/use`).
   - For a syllabus or similar document with little or no math, mention that a Canvas page may be less work than LaTeX. The resource page says the same.
2. **Check.** Run `check_tex.py` and read its report. Stop and ask before going further if the document is in a "hard case" (below).
3. **Fix.** Apply safe fixes automatically. Make the judgment fixes with the user: alt text, table headers, headings, fonts and package replacements.
4. **Verify.** The user compiles with LuaLaTeX and runs `pdfcheck --canvas` (predicts Ally) and, optionally, veraPDF (PDF/UA-2). They paste the output back, and the AI maps each failure to a line of source.
   - Compile errors go through `reference/troubleshooting.md`. For example, "text-unit para hooks differ" usually means an unsupported package.
5. **Hand-off.**
   - A change log, plus the items a person must review: alt-text accuracy, decorative vs. informative images, reading order and math.
   - A reminder that Ally scans every file in Canvas Files, including unpublished ones. Old inaccessible versions and instructor-only copies should be stored elsewhere.

## Division of labour

**Scripts (mechanical)**
- **Preamble:**
  - `\DocumentMetadata` present, first, and matching the canonical block; insert it if missing.
  - `\hypersetup{pdftitle=...}` set (not the filename).
  - `hyperref` loaded last.
- **Engine and fonts:** flag pdfTeX-only font setup (`inputenc`, `fontenc`, Type 1 font packages such as `mathptmx`). Suggest the `fontspec`/`unicode-math` equivalent from the template.
- **Packages and classes:** scan against `packages.yaml`. Flag `amsart` (unsupported; it loses the PDF title, so suggest `article`). Note that `amsmath` and `amsthm` are only partly supported.
- **Inventory:**
  - `\includegraphics` and `tikzpicture` without `alt=`. Missing alt means LaTeX inserts the filename, which Ally fails.
  - Graphics that may be decorative (candidates for `artifact`).
  - `tabular`/`array` environments and their `table/header-rows`/`header-columns` settings. These settings persist until changed, so the script tracks which table inherits which setting.
  - Heading outline and page-count estimate (Ally wants headings from 3 pages up).
- **Contrast:** colours lighter than `#767676` on white, computed from xcolor expressions (`gray!40`, `black!50`, `\definecolor`). Also link colours and `\color{white}`.
- **Lint:**
  - fake headings (`\textbf{...}`, `{\bf ...}` or `\Large` text alone on a line);
  - headings that don't start at the top level or that skip levels;
  - `$$...$$`;
  - `enumitem` options that should become the tagged `item-label` syntax;
  - bare URLs and "click here" link text.
- **After compiling:** condense `pdfcheck` and veraPDF output into a short list of failures.

**AI (judgment)**
- **Alt text, especially for math graphics:**
  - Examples: function graphs, geometric figures, graphs (like the Petersen graph in the template), commutative diagrams.
  - The alt text says what a student needs from the figure, not just what it looks like (for example, "a parabola with y-intercept (0,3) and vertex (3,−6)").
  - Complex figures also get a fuller description in the surrounding text.
- **Tables:** whether a table is a data table (needs header rows or columns) or only for layout.
- **Headings:**
  - Converting fake headings to real sectioning without changing how the document looks.
  - For long problem sets, choosing meaningful groups (e.g. `\section*{Problems 1–10}`).
- **Packages:** alternatives to incompatible packages, or deciding a package is safe with certain usage.
- **Colours:** darker colours that keep the author's intent.
- **Validator output:** mapping failures back to source lines.

## Ally checklist (first milestone), ordered by score impact

| # | Check | Ally cost if wrong |
|---:|---|---|
| 1 | Tagged PDF (`\DocumentMetadata`, LuaLaTeX) | caps score at 12 |
| 2 | All text ≥ 4.5:1 contrast on white | down to 5 on one page |
| 3 | Every figure (`\includegraphics`, `tikzpicture`) has alt text that isn't a filename | ×0.54 |
| 4 | Real headings in documents of 3+ pages | ×0.54 |
| 5 | Header cells in data tables with 3+ rows | ×0.69 |
| 6 | Formulas carry alt text (`math/alt/use`) | low score (resource page; not yet measured) |
| 7 | `lang` set and correct | −5 |
| 8 | Headings start at H1 | −5 |
| 9 | Title in the PDF Info dictionary (`pdftitle`) | −2 |
| 10 | No skipped heading levels, none beyond H6 | −2 |

WCAG items that Ally doesn't score are reported separately as "still needed for WCAG 2.1 AA". These cover alt-text quality, MathML that works with the student's reader, meaningful link text and reading order.

## Hard cases: warn and ask

The skill names the risk and asks the user how to proceed. It doesn't guess.

- **Beamer.** The tagging project doesn't support Beamer and doesn't plan to. The alternative is `ltx-talk`, which needs LaTeX 2025-11-01 or later (TeX Live 2026 qualifies) and is changing quickly.
  - Basic overlays work, but fine control of appearance and navigation buttons don't.
  - The skill warns about this and asks whether to convert at the user's own risk or to produce an accessible handout or notes version.
  - It points to the resource page's slides section and examples.
- **The `exam` class.** It is incompatible with the tagging code. Converting an exam to `article` is fairly easy if the exact layout doesn't need to survive. Before converting, the skill asks what the user needs to keep:
  - **Content only** (questions, parts, point values as text): convert to `article` with `enumerate`-based lists.
  - **Some layout** (point values in the margin, answer space, name/score header): convert, rebuild those pieces with tagging-safe commands, and list anything that will look different.
  - **Exact appearance** (a printed exam that must match): explain that the tagged version can't match exactly yet. Offer to keep the original for printing and make a separate accessible version.

  `reference/exam-conversion.md` holds the mapping (`questions`/`parts`/`\question[pts]`/`solution` → `article` equivalents) and a worked example.
- **Other unsupported packages and classes** (`amsart`, journal classes, department templates). Check `packages.yaml` and the tagging status list first.
- **Heavy custom macros, or catcode tricks** that the scripts can't read reliably.
- **TeX Live older than 2026.** Stop and explain how to upgrade.
- **Out of scope:** handwritten or scanned content, and LaTeX-to-HTML conversion. The skill points to the resource page's sections on these instead.

## Repository layout

```
tex-make-accessible/
├── README.md                       what it is; links to install docs and the resource page
├── PLAN.md
├── docs/
│   ├── ally-findings.md            evidence base from pdfcheck
│   ├── install-claude.md           Claude app (upload zip), Claude Code (plugin)
│   ├── install-chatgpt.md          ChatGPT Edu Skills
│   └── for-colleagues.md           one-page how-to
├── skills/tex-make-accessible/
│   ├── SKILL.md                    workflow, decision rules, hard cases
│   ├── reference/
│   │   ├── preamble.md             canonical \DocumentMetadata block, math/alt/use tradeoff
│   │   ├── fonts-engine.md         moving from pdfLaTeX to LuaLaTeX fonts
│   │   ├── ally-checklist.md       table above with fixes and scoring model
│   │   ├── alt-text-math.md        alt text for math graphics and TikZ, with examples
│   │   ├── tables.md               data vs. layout tables, header-row/column syntax
│   │   ├── headings.md             top level per class, problem-set grouping
│   │   ├── exam-conversion.md      exam class → article, by how much layout to keep
│   │   ├── contrast.md             safe colour substitutions
│   │   ├── troubleshooting.md      common errors, lualatex-dev, tagging-project issues
│   │   └── wcag-beyond-ally.md     math, links, reading order
│   ├── data/packages.yaml          package compatibility list
│   ├── scripts/
│   │   ├── check_tex.py            inventory + lint → JSON report
│   │   ├── fix_preamble.py         safe preamble insertion (writes a copy)
│   │   └── summarize_validation.py condenses pdfcheck / veraPDF output
│   └── templates/article.tex       the resource page's tagged-pdf-example.tex
├── .claude-plugin/                 Claude Code marketplace manifest
├── PROMPT.md                       paste-anywhere prompt for any chatbot (later)
└── tests/
    ├── fixtures/                   tiny .tex files, one problem each
    └── corpus/                     anonymized department files (see roadmap step 1)
```

## Roadmap

1. **Test corpus.** Collect 10–15 typical department `.tex` files (syllabus, exam, worksheet, problem set, notes) with the authors' permission, and remove names and student information. The Service Course Repository's Accessibility folder is a natural starting point.
2. **Check script + `packages.yaml`.** Run it on the corpus to find the most common problems and judgment calls. Re-run a few Ally probes with the canonical preamble (see Architecture 8).
3. **`SKILL.md` and reference files**, written around what step 2 finds and cross-linked to the resource page. Release the Claude skill (zip and Claude Code plugin).
4. **Pilot** with 2–3 colleagues, including one on free Claude and one on ChatGPT Edu. Success means their documents reach Ally 100 and pass veraPDF, with alt text they're happy to sign off.
5. **ChatGPT Skills install guide**, once UNL IT confirms Skills are enabled for Edu.
6. **Overleaf support** (see below).
7. **`PROMPT.md`** for people with no skill support, then colleague docs and a link from the resource page.

## Overleaf (later)

Overleaf offers TeX Live 2026 and LuaLaTeX (both set in the project's Menu), so the same source edits work there. The remaining gap is checking the result. Options:
- users download the PDF and run `pdfcheck` locally (needs Python);
- users rely on Ally's report after uploading to Canvas;
- some web-based check, if one turns up.

The skill's Overleaf instructions would be short: select TeX Live 2026 and LuaLaTeX, paste the preamble, and recompile.

## Open questions

- Does UNL IT enable Skills in the ChatGPT Edu workspace?
- Do the Ally findings (made with `testphase=latest`) all hold with `tagging=on`, PDF 2.0 and MathML? See Architecture 8.
- How much does Ally penalize formulas without alt text, and does it shrink with document length?
- In `report`/`book`, does `\chapter` get tagged as H1 so Ally's "start at H1" check passes?
- Which `exam` features do colleagues use most? This decides what `exam-conversion.md` covers first.

## References

- Department resource page: https://zachnorwood.github.io/math-resources-e4d30825c35241edbce4876eb472905a/
- LaTeX tagging project usage instructions: https://latex3.github.io/tagging-project/documentation/usage-instructions
- Tagging status of packages and classes: https://latex3.github.io/tagging-project/tagging-status/
- Table tagging (`latex-lab-table`): https://texdoc.org/serve/latex-lab-table/0
- Graphics tagging (`latex-lab-graphic`): https://texdoc.org/serve/latex-lab-graphic/0
- `ltx-talk`: https://www.ctan.org/pkg/ltx-talk
- Overleaf on accessible PDFs: https://docs.overleaf.com/writing-and-editing/creating-accessible-pdfs
- Ally accessibility checklist: https://help.anthology.com/ally-lms/en/administrators/ally-accessibility-checklist.html
- UNL ADA FAQ: https://ada.unl.edu/faqs/
- Claude skills help: https://support.claude.com/en/articles/12512180-use-skills-in-claude
