# Plan: a skill for making LaTeX documents pass Canvas Ally

## Goal

Give colleagues a skill (for Claude, and portable to ChatGPT) that takes their existing `.tex` source and helps them produce a PDF that:

1. scores well in Anthology Ally on Canvas, and
2. meets the underlying standard (WCAG 2.1 AA / PDF/UA-style tagging), not just Ally's checks.

The evidence base is [`docs/ally-findings.md`](docs/ally-findings.md): 62 controlled Ally scores from the `pdfcheck` project. The skill should rank its advice by that data, and say so when advice goes beyond it.

## Who uses it, and how

- **Users:** faculty and staff who write LaTeX but don't know PDF tagging. Many use Overleaf, not a local TeX install.
- **Surfaces:**
  - Claude.ai / Claude desktop with the skill uploaded (most colleagues).
  - Claude Code (people with a local TeX install; can compile and verify).
  - ChatGPT (same `SKILL.md` format; may lack code execution or a TeX install).
- **Consequence:** the skill must work in "no tools" mode (read the source, propose edits) and get better when it can run scripts and compile.

## What the skill does (the workflow in `SKILL.md`)

1. **Intake.** Collect the `.tex` files (including `\input`/`\include` children), the document class, the engine, and where it's compiled (Overleaf or local, TeX Live year). Ask for the Ally report if they have one: score, issue descriptions, and the "Increase score up to N%" figures.
2. **Audit.** Check the source against the checklist below. Report findings ranked by Ally score impact (tagging and contrast first), each with the line, the fix and the expected score gain.
3. **Fix.** Edit a copy of the source, never silently. Typical edits:
   - add `\DocumentMetadata{...}` as line 1 with the right `lang=`;
   - add `\hypersetup{pdftitle={...}}`;
   - add `alt={...}` to every `\includegraphics` (drafted from the image and caption if visible, marked for the author to confirm);
   - turn bold "fake headings" into `\section`-style commands;
   - declare table header rows;
   - darken colours below 4.5:1 against white.
4. **Compile and verify** (when possible). Compile with LuaLaTeX twice and run `pdfcheck --canvas` on the PDF. Without tools, give exact Overleaf steps instead (set compiler to LuaLaTeX, check TeX Live version) and tell the user what to check in Ally after upload.
5. **Hand-off.** A short change log, a list of things only the author can judge (alt-text accuracy, decorative vs. informative images, reading order), and anything the skill couldn't fix (unsupported packages).

## The checklist (from the findings, ordered by impact)

| # | Check | Ally cost if wrong | Source-level test |
|---:|---|---|---|
| 1 | Tagged PDF | caps score at 12 | `\DocumentMetadata` present and first; engine is LuaLaTeX |
| 2 | Contrast ≥ 4.5:1 on white | down to 5 | colour uses lighter than `#767676`: `gray`, `lightgray`, `black!NN` (NN < ~54), link colours, beamer themes, `\color{white}` |
| 3 | Alt text on every figure | ×0.54 | every `\includegraphics` has `alt=`; missing alt means the filename is used, which Ally fails |
| 4 | Real headings (3+ pages) | ×0.54 | sectioning commands used; no `\textbf{...}` heading lines |
| 5 | Table header cells (3+ rows) | ×0.69 | `table/header-rows` set before data tables |
| 6 | Correct `lang` | −5 | `lang=` matches the text (default is English) |
| 7 | Headings start at H1 | −5 | first heading maps to H1 |
| 8 | Title in Info dictionary | −2 | `pdftitle` set and meaningful |
| 9 | No skipped heading levels / > H6 | −2 | no `\section` → `\subsubsection` jumps |

Beyond Ally (WCAG items Ally doesn't score, flagged as advice): meaningful alt-text quality, decorative images as artifacts, link text, math accessibility, reading order.

## Repository layout

```
README.md                         what this is, how to install on each surface
PLAN.md                           this file
docs/
  ally-findings.md                evidence base (the pdfcheck briefing)
  install-claude.md               upload to Claude.ai / use in Claude Code
  install-chatgpt.md              ChatGPT setup and limitations
skills/latex-ally-accessibility/
  SKILL.md                        trigger description + the 5-step workflow (kept short)
  references/
    checklist.md                  the table above, with fixes and examples
    ally-scoring.md               score model, issue texts, "Increase score up to" use
    recipes.md                    preambles for article, report/book, beamer, Overleaf
    colour-contrast.md            safe colour substitutions, xcolor mix arithmetic
    alt-text.md                   how to write alt text for figures, plots, diagrams, math
    package-compat.md             packages known to break or need care under tagging
    troubleshooting.md            common compile errors after adding \DocumentMetadata
  scripts/
    audit_tex.py                  static checker: .tex in, ranked findings out (JSON + text)
    contrast.py                   contrast ratio for xcolor expressions (gray!40, etc.)
  templates/
    article-accessible.tex        the recipe that scored 100
tests/
  fixtures/                       small .tex files, one problem each, plus expected findings
  test_audit.py
```

Keep `SKILL.md` short (workflow and decision rules) and put detail in `references/`, so the skill loads quickly and the model reads detail only when needed. Scripts use only the Python standard library, so they run in Claude's and ChatGPT's sandboxes.

## Build phases

**Phase 1: working skill for `article` documents (MVP)**
- `SKILL.md`, `checklist.md`, `recipes.md` (article only), `alt-text.md`, the template.
- Works with no scripts: the model audits by reading the source.
- Done when: three real colleague documents go from their current Ally score to 95+ using only the skill.

**Phase 2: deterministic audit**
- `audit_tex.py` and `contrast.py`, with fixtures and tests for each checklist row.
- Handles multi-file projects and resolves `\definecolor` / `\colorlet`.
- The skill runs the script when it can and falls back to reading when it can't.

**Phase 3: other document types**
- `report`/`book` (check what `\chapter` maps to; must start at H1).
- Beamer slides (tagging support is incomplete; may need advice like "export handouts" or "keep slides simple").
- Math-heavy notes (test whether Ally checks math; document LuaLaTeX MathML options).
- Exam and assignment classes commonly used in the department.
- Each needs a few Ally probes through `pdfcheck` before writing advice; mark advice "untested" until then.

**Phase 4: packaging and roll-out**
- Install guides for Claude and ChatGPT, a one-page "how to use it" for colleagues.
- A results log template so colleagues' Ally scores feed back into `pdfcheck` regression tests (the `probes/*/results.csv` format).

## Rules the skill must follow

- Never claim a score; say what Ally is expected to report and tell the user to confirm in Canvas.
- Label advice as measured, inferred or untested, matching the findings doc.
- Draft alt text but always ask the author to confirm it; never use the filename or "image".
- Don't change visible content or layout except where needed (colours, fake headings), and list every such change.
- Check the TeX version before choosing `\DocumentMetadata` keys (`testphase=latest` vs. `tagging=on`, `pdfstandard`).
- If a package blocks tagging, say so plainly rather than producing a PDF that looks tagged but isn't.

## Open questions for you

1. **Where do colleagues compile?** Mostly Overleaf, local TeX, or both? This sets how much of the skill is "Overleaf steps" vs. "run this".
2. **Which document types matter most?** Lecture notes, Beamer slides, problem sets/exams, papers? Beamer is the hardest and least tested.
3. **ChatGPT target:** the newer Skills feature (same `SKILL.md` format) or a Custom GPT with knowledge files? The plan assumes Skills.
4. **Can colleagues install `pdfcheck`?** If not, the verify step relies on uploading to Canvas.
5. **Target bar:** Ally 100, or full WCAG 2.1 AA (the ADA Title II rule for public universities)? The plan aims at both but ranks by Ally.
6. **Can I use real documents** (with permission) as test fixtures for Phase 1?
