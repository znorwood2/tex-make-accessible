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
2. **Scripts first; AI only for judgment.** Everything that can be decided from the source is done by a script, with no AI. The AI's job is reduced to a short list of questions that need judgment (alt text, table headers, heading names). See "Automation" below.
   - This keeps the AI part small enough for free Claude and ChatGPT accounts. Those have tight message limits and may not run code.
   - The scripts also work with no AI at all. A colleague can answer the questions themselves.
3. **Package compatibility is data, not code.** `data/packages.yaml` lists each package's tagging status, safe alternatives and notes. It starts from the LaTeX Project's [tagging status list](https://latex3.github.io/tagging-project/tagging-status/). New findings become pull requests to this file.
4. **Detect liberally, fix conservatively.** Regex parsing of TeX is fragile. Scripts flag problems widely but make only safe, repeatable edits (such as inserting the preamble). They never overwrite the original; they write a copy plus a diff.
5. **Python standard library only.** The scripts must run on the user's machine and in Claude's and ChatGPT's sandboxes without installs. Most Macs and Linux machines already have Python 3. Windows users may not, so a `texlua` version of the preamble fix is worth considering (`texlua` ships with every TeX install).
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
   - The page's source is `math-resources-e4d30825c35241edbce4876eb472905a/index.html` in [`zachnorwood/zachnorwood.github.io`](https://github.com/zachnorwood/zachnorwood.github.io). A sync script (`scripts/dev/sync_from_page.py`) reads that file from a local clone and pulls out the metadata block and the `tagged-pdf-example.tex` source. A test fails if the skill's template or `reference/preamble.md` disagree with it.
8. **The Ally findings predate the current preamble.** The experiments used `testphase=latest`. The skill uses `tagging=on` with PDF 2.0, as the page does. Phase 2 re-runs a few `pdfcheck` probes with the canonical preamble to confirm the findings still hold.

## Automation: scripts first

### The command-line tool

One stdlib-only Python program, `tex-a11y`, with five subcommands:

| Command | What it does | AI needed? |
|---|---|---|
| `tex-a11y check doc.tex` | Reads the document and all `\input`/`\include` files. Reports problems, ranked by Ally impact. | No |
| `tex-a11y fix doc.tex` | Applies every automatic fix to a copy (`doc-accessible.tex`) and writes a diff. Also writes `doc-questions.md` listing what still needs judgment. | No |
| `tex-a11y apply doc-questions.md` | Reads the answered questions file and puts the answers into `doc-accessible.tex`. | No |
| `tex-a11y build doc-accessible.tex` | Runs LuaLaTeX twice, then `pdfcheck --canvas`, and prints a short summary that maps each failure to a source line. | No |
| `tex-a11y convert-exam doc.tex --keep content` | Converts an `exam` class document to `article` (see "Hard cases"). | No |

### The questions file: the bridge between scripts and AI

`fix` writes every judgment item into `doc-questions.md`, one short section per item:
- **What is being asked:** for example, alt text for figure 3, or the number of header rows for table 2.
- **The context needed to answer:** the caption, the surrounding paragraph, the TikZ code or image filename, and the table's first few rows.
- **Guidance:** a few lines on what a good answer looks like. For example, alt text says what a student needs from the figure.
- **A blank answer field** in a fixed format that `apply` can read.

Anyone can fill it in:
- **Paid Claude/ChatGPT with the skill:** the AI fills it in, shows the answers, and runs `apply` itself.
- **Free accounts or any chatbot:** the user pastes the questions file (plus any figure images) into the chat with the short prompt from `PROMPT.md`. Then they save the reply and run `apply`. The chatbot never sees the whole document, so the conversation stays short.
- **No AI:** the user fills in the answers by hand.

`apply` checks the answers before using them. It rejects empty or filename-like alt text and header counts larger than the table. It never inserts placeholder alt text, because a placeholder like "TODO" would pass Ally.

### What is automated, what needs judgment

| Task | Script alone | Script proposes, person or AI confirms | AI or person decides |
|---|---|---|---|
| `\DocumentMetadata` | Insert or correct the canonical block, first in the file | `lang`: guessed from `babel`/`polyglossia` options and confirmed if not English | `math/alt/use`: kept unless the user says a screen-reader user is involved |
| PDF title | Copy `\title{...}` into `pdftitle` (macros stripped) | Title when there's no `\title` (filename-based guess) | |
| `hyperref` | Load it if missing; move it last | | |
| TeX Live version | Check it; stop with upgrade steps if older than 2026 | | |
| Fonts | Remove `inputenc`, `fontenc` and `lmodern`; replace known Type 1 font packages using a mapping table | Unknown font packages | |
| `$$...$$` | Convert to `\[...\]` | | |
| Contrast | Darken colours below 4.5:1 to the nearest passing shade, keeping the hue | Colours set inside macros or themes the script can't trace | |
| Table header settings | Scope each table's `\tagpdfsetup` so it doesn't leak into later tables | Header rows/columns when the source makes it clear (first row followed by `\hline` or `\midrule`, or bold first row) | Ambiguous tables; data vs. layout table |
| Figures | Find every `\includegraphics` and `tikzpicture` without `alt=` | Decorative graphics (logos, rules): mark as `artifact` on confirmation | Alt text |
| Headings | Report outline, skipped levels and fake headings | Turning a fake heading into `\section*` with matching appearance | Heading names for long problem sets |
| Lists | Convert simple `enumitem` labels to `item-label` | Complex `enumitem` settings | |
| Packages | Look up every package in `packages.yaml`; apply listed safe replacements | Partly supported packages, by how they're used | Unsupported packages with no listed replacement |
| `exam` class | Content-only conversion once the user picks that option | Partial layout rebuild | Which layout to keep |
| Links | Find bare URLs and "click here" text | | Better link text |
| After compiling | Run LuaLaTeX and `pdfcheck`, summarise failures by source line | | Failures the summary can't map |

Over time, answers that turn out to be predictable move left in this table. Examples: a new entry in `packages.yaml`, or a new header-row pattern the script recognizes.

## Workflow (what `SKILL.md` tells the model)

The AI sandbox probably lacks TeX Live 2026, so compiling happens on the user's machine:

```
tex-a11y fix → questions answered (AI or person) → tex-a11y apply → tex-a11y build
                                                                        ↓
                                     fix remaining failures ← summary ←─┘
```

1. **Intake.**
   - Get the `.tex` files.
   - Ask for the Ally report if there is one: score, issue texts and the "Increase score up to N%" figures.
   - Ask whether a student using a screen reader is involved (this decides `math/alt/use`).
   - For a syllabus or similar document with little or no math, mention that a Canvas page may be less work than LaTeX. The resource page says the same.
2. **Fix.** Run `tex-a11y fix`. Stop and ask before going further if the document is in a "hard case" (below).
3. **Answer the questions.** Fill in `doc-questions.md`, showing alt text and other answers to the user for approval. Then run `tex-a11y apply`.
4. **Verify.** The user runs `tex-a11y build` (or compiles and runs `pdfcheck` themselves) and pastes the summary back. Optionally they also run veraPDF (PDF/UA-2).
   - Compile errors go through `reference/troubleshooting.md`. For example, "text-unit para hooks differ" usually means an unsupported package.
5. **Hand-off.**
   - A change log, plus the items a person must review: alt-text accuracy, decorative vs. informative images, reading order and math.
   - A reminder that Ally scans every file in Canvas Files, including unpublished ones. Old inaccessible versions and instructor-only copies should be stored elsewhere.

Without the skill, a colleague follows the same steps: run `fix`, take the questions file to any chatbot (or answer it themselves), run `apply`, run `build`. `docs/for-colleagues.md` describes this path.

## Judgment guidance (for the AI, and for people answering by hand)

- **Alt text, especially for math graphics:**
  - Examples: function graphs, geometric figures, graphs (like the Petersen graph in the template), commutative diagrams.
  - The alt text says what a student needs from the figure, not just what it looks like (for example, "a parabola with y-intercept (0,3) and vertex (3,−6)").
  - Complex figures also get a fuller description in the surrounding text.
- **Tables:** whether a table holds data (needs header rows or columns) or is only for layout.
- **Headings:** for long problem sets, choose meaningful groups (e.g. `\section*{Problems 1–10}`).
- **Packages:** alternatives to unsupported packages, or whether a partly supported one is safe as used.
- **Leftover build failures:** map them back to source lines.

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
│   ├── data/fonts.yaml             pdfTeX font package → fontspec/unicode-math mapping
│   ├── scripts/
│   │   ├── tex_a11y/               the tex-a11y tool (check, fix, apply, build, convert-exam)
│   │   └── dev/sync_from_page.py   keeps the preamble and template in sync with the resource page
│   └── templates/article.tex       the resource page's tagged-pdf-example.tex
├── .claude-plugin/                 Claude Code marketplace manifest
├── PROMPT.md                       short prompt to paste with a questions file into any chatbot
└── tests/
    ├── fixtures/                   tiny .tex files, one problem each
    └── corpus/                     anonymized department files (see roadmap step 1)
```

## Roadmap

1. **Test corpus.** Collect 10–15 typical department `.tex` files (syllabus, exam, worksheet, problem set, notes) with the authors' permission, and remove names and student information. The Service Course Repository's Accessibility folder is a natural starting point.
2. **`tex-a11y check` and `fix` (automatic fixes only) + `packages.yaml`.** Run them on the corpus to find the most common problems and judgment calls. Re-run a few Ally probes with the canonical preamble (see Architecture 8). This alone gives a usable, no-AI tool.
3. **Questions file, `apply`, `build` and `PROMPT.md`.** Test the questions file on a free Claude and a free ChatGPT account to make sure it fits comfortably in one conversation.
4. **`SKILL.md` and reference files**, written around what steps 2–3 find and cross-linked to the resource page. Release the Claude skill (zip and Claude Code plugin).
5. **Pilot** with 2–3 colleagues, including one on free Claude and one on ChatGPT Edu. Success means their documents reach Ally 100 and pass veraPDF, with alt text they're happy to sign off.
6. **ChatGPT Skills install guide**, once UNL IT confirms Skills are enabled for Edu.
7. **Overleaf support** (see below).
8. **Colleague docs** and a link from the resource page.

## Overleaf (later)

Overleaf offers TeX Live 2026 and LuaLaTeX (both set in the project's Menu), so the same source edits work there. The remaining gap is checking the result. Options:
- users download the PDF and run `pdfcheck` locally (needs Python);
- users rely on Ally's report after uploading to Canvas;
- some web-based check, if one turns up.

The skill's Overleaf instructions would be short: select TeX Live 2026 and LuaLaTeX, paste the preamble, and recompile.

The `tex-a11y` scripts can't run inside Overleaf. Overleaf users can download the project's source, or let the AI run the scripts in its own sandbox. They then upload the fixed source back, with `build` replaced by Overleaf's compile button.

## Open questions

- Does UNL IT enable Skills in the ChatGPT Edu workspace?
- Do the Ally findings (made with `testphase=latest`) all hold with `tagging=on`, PDF 2.0 and MathML? See Architecture 8.
- How much does Ally penalize formulas without alt text, and does it shrink with document length?
- In `report`/`book`, does `\chapter` get tagged as H1 so Ally's "start at H1" check passes?
- Which `exam` features do colleagues use most? This decides what `exam-conversion.md` and `convert-exam` cover first.
- Can free Claude and free ChatGPT accounts run code or load skills? This decides whether free users get the full skill or the questions-file path.
- Do colleagues on Windows have Python, or should the core fixes also exist as a `texlua` script?

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
