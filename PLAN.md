# Plan: a skill for making LaTeX documents accessible

## Goal

A shareable AI skill that helps math faculty and grad students fix their LaTeX source so it compiles to accessible, tagged PDFs.

- **Target:** WCAG 2.1 AA.
- **First milestone:** a 100% Anthology Ally score in Canvas. That's what colleagues will see, and it covers the biggest problems.
- **Beyond Ally:** good alt text (Ally only checks that alt text exists and isn't a filename), math accessibility, link text and reading order.
- **Never claim "compliant."** The skill reports "passes automated checks; a person still needs to review: …".

Evidence base: [`docs/ally-findings.md`](docs/ally-findings.md), 62 controlled Ally scores from the [`pdfcheck`](https://github.com/znorwood2/pdfcheck) project. Advice keeps that document's labels: measured, inferred or untested.

## Audience and context

- Colleagues in the UNL math department who write LaTeX but aren't accessibility experts.
- Documents: syllabi, exams, worksheets, lecture notes and papers. `article` and similar classes come first. Exams need a conversion step, and Beamer slides are out of scope for now (see "Hard cases").
- Many colleagues won't have paid Claude accounts. The university's ChatGPT Edu accounts use Skills (Custom GPTs are retired there). The design must work with limited tools.
- **Local TeX first.** The first versions assume the user compiles on their own machine with TeX Live 2026. Overleaf support comes later (see "Overleaf").

## Architecture

1. **One repo, one skill, open `SKILL.md` format.** Claude and ChatGPT Skills read the same files. Platform differences go in the install docs, not in separate copies.
2. **Scripts do the mechanical work; the AI makes the judgment calls.** Scripts produce a JSON report. `SKILL.md` tells the model to run them, work through the judgment items, have the user recompile, re-check and summarize.
3. **Package compatibility is data, not code.** `data/packages.yaml` lists each package's tagging status, safe alternatives and notes. It starts from the LaTeX Project's tagging status list. New findings become pull requests to this file.
4. **Detect liberally, fix conservatively.** Regex parsing of TeX is fragile. Scripts flag problems widely but make only safe, repeatable edits (such as inserting the preamble). They never overwrite the original; they write a copy plus a diff.
5. **Python standard library only.** The scripts must run in Claude's and ChatGPT's sandboxes without installs.
6. **Require TeX Live 2026.** Supporting older installs would mean tracking individual LaTeX kernel releases, so the skill doesn't try. The check script reads the TeX Live year (`tex --version`, or the `.log` banner) and stops with upgrade instructions if it is older. The template and reference files use only the `\DocumentMetadata` keys that TeX Live 2026 supports.

## Workflow (what `SKILL.md` tells the model)

The AI sandbox probably lacks a recent TeX Live, so compiling happens on the user's machine:

```
check script → AI edits a copy → user compiles (LuaLaTeX, twice)
     ↑                                         ↓
     └── AI fixes ← pdfcheck / veraPDF report ←┘
```

1. **Intake.** Collect all `.tex` files (follow `\input`/`\include`), class, packages and TeX Live version. Ask for the Ally report if there is one: score, issue texts and the "Increase score up to N%" figures.
2. **Check.** Run `check_tex.py` and read its report. Stop and ask before going further if the document is in a "hard case" (below).
3. **Fix.** Apply safe fixes automatically. Make judgment fixes with the user: alt text, table headers and turning fake headings into real ones.
4. **Verify.** The user compiles with LuaLaTeX and runs `pdfcheck --canvas` (predicts Ally) and, optionally, veraPDF (PDF/UA). They paste the output back, and the AI maps each failure to a line of source.
5. **Hand-off.** A change log, plus the items a person must review: alt-text accuracy, decorative vs. informative images, reading order and math.

## Division of labour

**Scripts (mechanical)**
- **Preamble:** `\DocumentMetadata` present and first, with `lang`, tagging and `pdfstandard`. Insert the template if missing. Check `\hypersetup{pdftitle=...}`.
- **Packages:** scan against `packages.yaml`.
- **Inventory:**
  - `\includegraphics` without `alt=`. Missing alt means LaTeX inserts the filename, which Ally fails.
  - `tikzpicture`s and `tabular`s.
  - Heading outline.
- **Contrast:** colours lighter than `#767676` on white, computed from xcolor expressions (`gray!40`, `black!50`, `\definecolor`), link colours, `\color{white}`.
- **Lint:**
  - fake headings (`\textbf{...}` or `{\bf ...}` alone on a line);
  - headings that don't start at level 1 or that skip levels;
  - `$$...$$`;
  - bare URLs and "click here" link text.
- **After compiling:** condense `pdfcheck` and veraPDF output into a short list of failures.

**AI (judgment)**
- **Alt text, especially for math graphics.** Examples: function graphs, geometric figures, commutative diagrams and TikZ. The alt text says what a student needs from the figure, not just what it looks like. Complex figures also get a longer description in the text.
- **Tables:** whether one is a data table (needs header rows or columns) or only for layout.
- **Fake headings:** converting them to real sectioning without changing how the document looks.
- **Packages:** alternatives to incompatible packages, or deciding a package is safe with certain usage.
- **Colours:** darker colours that keep the author's intent.
- **Validator output:** mapping failures back to source lines.

## Ally checklist (first milestone), ordered by score impact

| # | Check | Ally cost if wrong |
|---:|---|---|
| 1 | Tagged PDF (`\DocumentMetadata`, LuaLaTeX) | caps score at 12 |
| 2 | All text ≥ 4.5:1 contrast on white | down to 5 on one page |
| 3 | Every figure has alt text that isn't a filename | ×0.54 |
| 4 | Real headings in documents of 3+ pages | ×0.54 |
| 5 | Header cells in data tables with 3+ rows | ×0.69 |
| 6 | `lang` set and correct | −5 |
| 7 | Headings start at H1 | −5 |
| 8 | Title in the PDF Info dictionary (`pdftitle`) | −2 |
| 9 | No skipped heading levels, none beyond H6 | −2 |

WCAG items that Ally doesn't score are reported separately as "still needed for WCAG 2.1 AA". These cover alt-text quality, math (MathML via LuaLaTeX), meaningful link text and reading order.

## Hard cases: warn and ask

The skill names the risk and asks the user how to proceed. It doesn't guess.

- **Beamer.** Tagging requires converting to `ltx-talk`, which is changing quickly. Warn and offer options: convert at the user's own risk, or produce an accessible handout or notes version from the same content.
- **The `exam` class.** It is incompatible with the tagging code. Converting an exam to `article` is fairly easy if the exact layout doesn't need to survive. Before converting, the skill asks what the user needs to keep:
  - **content only** (questions, parts, point values as text): convert to `article` with `enumerate`-based lists;
  - **some layout** (point values in the margin, answer space, headers with name/score lines): convert and rebuild those pieces with tagging-safe commands, listing anything that will look different;
  - **exact appearance** (a printed exam that must match): say that the tagged version can't match exactly yet, and offer to keep the original for printing and produce a separate accessible version.
  `reference/exam-conversion.md` holds the mapping (`questions`/`parts`/`\question[pts]`/`solution` → article equivalents) and a worked example.
- **Packages listed as incompatible** in `packages.yaml`, and other classes not yet checked (journal classes, department templates).
- **Heavy custom macros, or catcode tricks** that the scripts can't read reliably.
- **TeX Live older than 2026.** Stop and explain how to upgrade.

## Repository layout

```
tex-make-accessible/
├── README.md                       what it is; links to install docs
├── PLAN.md
├── docs/
│   ├── ally-findings.md            evidence base from pdfcheck
│   ├── install-claude.md           Claude app (upload zip), Claude Code (plugin)
│   ├── install-chatgpt.md          ChatGPT Edu Skills
│   └── for-colleagues.md           one-page how-to
├── skills/tex-make-accessible/
│   ├── SKILL.md                    workflow, decision rules, hard cases
│   ├── reference/
│   │   ├── preamble.md             \DocumentMetadata keys by TeX Live version
│   │   ├── ally-checklist.md       table above with fixes and scoring model
│   │   ├── alt-text-math.md        alt text for math graphics, with examples
│   │   ├── tables.md               data vs. layout tables, header-row syntax
│   │   ├── exam-conversion.md      exam class → article, by how much layout to keep
│   │   ├── contrast.md             safe colour substitutions
│   │   └── wcag-beyond-ally.md     math, links, reading order
│   ├── data/packages.yaml          package compatibility list
│   ├── scripts/
│   │   ├── check_tex.py            inventory + lint → JSON report
│   │   ├── fix_preamble.py         safe preamble insertion (writes a copy)
│   │   └── summarize_validation.py condenses pdfcheck / veraPDF output
│   └── templates/article.tex       the preamble that scored 100 in Ally
├── .claude-plugin/                 Claude Code marketplace manifest
├── PROMPT.md                       paste-anywhere prompt for any chatbot (later)
└── tests/
    ├── fixtures/                   tiny .tex files, one problem each
    └── corpus/                     anonymized department files (see roadmap step 1)
```

## Roadmap

1. **Test corpus.** Collect 10–15 typical department `.tex` files (syllabus, exam, worksheet, notes) with the authors' permission. Remove names and student information. These test the scripts on real documents, not just made-up examples.
2. **Check script + `packages.yaml`.** Run it on the corpus to find the most common problems and judgment calls.
3. **`SKILL.md` and reference files**, written around what step 2 finds. Release the Claude skill (zip and Claude Code plugin).
4. **Pilot** with 2–3 colleagues, including one on free Claude and one on ChatGPT Edu. Success means their documents reach Ally 100 and pass veraPDF, with alt text they're happy to sign off.
5. **ChatGPT Skills install guide**, once UNL IT confirms Skills are enabled for Edu.
6. **Overleaf support** (see below).
7. **`PROMPT.md`** for people with no skill support, then colleague docs and a department announcement.

## Overleaf (later)

Overleaf can compile tagged PDFs if the project uses LuaLaTeX and a recent TeX Live (both set in the project's Menu). The skill can still edit the source; the gap is verification. Options to evaluate:
- users download the PDF and run `pdfcheck` locally;
- users rely on Ally's report after uploading to Canvas;
- some web-based check, if one turns up.

The first step is confirming which TeX Live versions Overleaf currently offers and whether they support the needed `\DocumentMetadata` keys.

## Open questions

- Does UNL IT enable Skills in the ChatGPT Edu workspace?
- Which `\DocumentMetadata` keys does TeX Live 2026 support (`tagging=on`, `pdfstandard=ua-2`, `testphase`)? Verify before writing the template.
- What do `\chapter`/`\section` map to in `report`/`book`?
- Does Ally check math at all?
- How should TikZ pictures get alt text in TeX Live 2026?
- How should the skill link to and stay consistent with the department resource page (https://zachnorwood.github.io/math-resources-e4d30825c35241edbce4876eb472905a/)? Not yet reviewed.

## References

- Overleaf on native tagging: https://www.overleaf.com/blog/bridging-the-accessibility-gap-why-latexs-native-pdf-tagging-matters-now
- LaTeX tagging project status: https://latex3.github.io/tagging-project/
- Utah Math accessible LaTeX guide: https://www.math.utah.edu/accessibility/latex-generated-pdfs.php
- UF LaTeX accessibility guide: https://people.clas.ufl.edu/jnowell/latex-accessibility/
- Claude skills help: https://support.claude.com/en/articles/12512180-use-skills-in-claude
