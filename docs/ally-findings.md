# What Anthology Ally rewards in LaTeX-made PDFs

A briefing for building a Claude Skill that helps people turn LaTeX documents into PDFs that score well in Anthology Ally (Canvas) and meet accessibility standards.

**Source.** Controlled experiments from the `pdfcheck` project (github.com/znorwood2/pdfcheck), September–October 2026. Each test PDF was a copy of a known document with one property changed, uploaded to Canvas, and scored by Ally. That gives 62 Ally scores plus Ally's "Increase score up to N%" figures for three files. All test documents were short (one to three pages) and compiled with LuaLaTeX from TeX Live 2026.

**Confidence labels used below:**
- **Measured:** directly observed in Ally, usually more than once.
- **Inferred:** fits the observed scores, but Ally's own label or mechanism was not confirmed.
- **Untested:** sensible advice that these experiments did not check.

---

## 1. Priorities for a LaTeX author, by score impact

| Rank | What to get right | Ally score if wrong (one-page document) | Confidence |
|---:|---|---|---|
| 1 | The PDF is tagged (has a structure tree with content) | 12 | Measured |
| 2 | No text below WCAG 4.5:1 contrast against white | 5 (one page of text), ~52 (two pages), ~68 (three pages) | Measured |
| 3 | Every figure has real alt text (not a filename) | 54 | Measured |
| 4 | Documents with 3+ pages have tagged headings | 54 | Measured |
| 5 | Data tables (3+ rows) have header cells | 69 | Measured |
| 6 | Language is set and matches the text | 95 | Measured score; label inferred |
| 7 | Headings start at H1 | 95 | Measured |
| 8 | Document title is set in the PDF Info dictionary | 98 | Measured |
| 9 | Headings don't skip levels, and none go beyond H6 | 98 | Measured |

**Key point for the Skill:** tagging and contrast dominate. An untagged PDF can never score above 12. One page of light-gray text alone drops a perfect document to 5.

---

## 2. How Ally combines issues into a score

The model below reproduces all 62 observations to within 1 point. Ally's scores drift by about 1 point between files with identical issues, so that's the best precision possible.

- **Minor issues subtract fixed points** (measured, several combinations).
  - The minor issues are title (−2), language (−5), heading start (−5), heading sequence (−2) and beyond-H6 (−2).
  - Example: untagged plus no language scored 12 − 5 = 7.
  - Example: missing alt plus no title plus no language scored 54 − 2 − 5 = 47.
- **Major issues multiply** (inferred from two observations).
  - Each major issue leaves a fraction of the score: untagged ×0.12, missing alt ×0.54, no headings ×0.54, table headers ×0.69, contrast ×0.05 on one page.
  - Example: no headings plus three-page contrast scored 54 × 0.68 = 37.
  - Example: untagged plus three-page contrast scored about 9.
- **The floor is 5.** No document without a severe issue scored below 5, even when the penalties add up to more.
- **Scanned PDFs score 0.**
- **Contrast is the only penalty seen to shrink with length.** The loss is about 95 ÷ (number of pages with visible text). Blank pages don't count. It doesn't matter how many of the pages have gray text: one gray page out of three cost as much as three.
- **Untagged does not shrink with length:** it scored 12 on one page and on three.
- **Missing alt text:** unknown whether it shrinks on longer documents. Blank pages didn't change it, but documents with more text pages weren't tested.
- **"Increase score up to N%".** Ally lists this under each issue. It's the score after fixing only that issue, and it matched the model in every case recorded. The Skill can tell users to read these figures to decide what to fix first.

---

## 3. What exactly Ally checks (measured unless marked)

### Tagging
- No structure tree means untagged (12).
- **A structure tree with no elements in it also counts as untagged** (12). Some tools produce this.
- A missing `/MarkInfo` entry did not matter.

### Title
- **Ally reads the classic Info dictionary `/Title`.** A title only in the XMP metadata (normal in PDF 2.0) was reported as missing.
- A title only in the Info dictionary passed.
- In LaTeX, `\hypersetup{pdftitle={...}}` with `\DocumentMetadata` wrote both, which passed.

### Language
- A missing catalog `/Lang` costs 5.
- **A wrong language** (`fr-FR` or `es-ES` on English text) also cost 5. The label is inferred to be Ally's language-correctness check.
- **A malformed value** (`english` instead of `en`) also cost 5.
- Current LaTeX inserts a default English `/Lang` when tagging is on. Non-English documents must set `lang=` explicitly.

### Headings
- Documents with 3 or more pages and no tagged headings lose 46 points. At 2 pages there was no penalty.
- **Bold "visual headings" (`\textbf{...}` on its own line) do not count.**
- A first heading at H2 costs 5. Skipping a level (H1 → H3) costs 2. A literal `/H7` element costs 2, even when role-mapped to H6.
- With `article` and `\DocumentMetadata`, `\section` is tagged H1 and `\subsection` H2. That passed.
- With `report`/`book`, check what `\chapter` and `\section` map to (**untested**). The document must start at H1.

### Figures and alt text
- A Figure without `/Alt` costs 46.
- **A filename as alt text (`test-figure.png`) is treated as missing.** This matters because current LaTeX inserts the filename as fallback alt text when none is given, so forgetting `alt=` produces an Ally failure, not a warning.
- Alt text of `test-figure` (no extension) or `image` passed Ally. Ally checks only the file extension, not quality. The Skill should still require meaningful descriptions; Ally just won't catch bad ones.
- One-figure test documents only. Multiple figures with only some missing alt text were **untested**.

### Tables
- A tagged table of 3+ rows with no TH cells costs 31.
- **Tables with 1 or 2 rows were not checked at all**, presumably because Ally treats them as layout tables.
- `\tagpdfsetup{table/header-rows={1}}` before the `tabular` produced TH cells, and the table passed.

### Contrast
- Ally's threshold matched WCAG AA 4.5:1 against white exactly. `#767676` (4.54:1) passed; `#808080` (3.95:1) and anything lighter failed.
- The penalty did not depend on how light the text was: #EEEEEE and #808080 both scored 5.
- White text (an invisible text layer done with `\color{white}`) was flagged as a contrast failure.
- **Untested:** whether a single short gray phrase (a footer, a "draft" note, a caption) triggers the full penalty, and whether Ally considers the real background (white text on a dark box).

### Scans
- An **untagged** PDF that is mostly one image (70%, 80% or 100% of the page) scored 0. This held even with an invisible OCR text layer or a visible line of text.
- At 58% coverage it was not flagged.
- **A tagged document with a large figure (85% of the page, with alt text) scored 100.** Large images in properly tagged LaTeX documents are safe.

### Text Ally displays for each issue
Ally shows descriptions, not codes. Seen so far:
- "This PDF is untagged"
- "This PDF does not have a title"
- "This PDF does not have a language set"
- "This PDF does not have headings"
- "This PDF contains images without description"
- "This PDF contains text with insufficient contrast"

---

## 4. LaTeX recipe that scored 100 in Ally

Compiled with **LuaLaTeX** (TeX Live 2026), run twice:

```latex
\DocumentMetadata{testphase=latest, lang=en-US}
\documentclass[11pt]{article}
\usepackage{graphicx,xcolor,hyperref}
\hypersetup{pdftitle={A Human-Readable Title}}

\begin{document}
\section{Introduction}            % tagged H1
Text.
\subsection{Details}              % tagged H2

\begin{figure}[h]
  \centering
  \includegraphics[width=.7\linewidth,
    alt={What the figure shows and why it matters}]{figure.png}
  \caption{Caption text}
\end{figure}

\tagpdfsetup{table/header-rows={1}}
\begin{tabular}{lr}
Category & Count \\   % becomes TH cells
Apples & 4 \\
Pears & 7 \\
\end{tabular}
\end{document}
```

Notes for the Skill:
- `testphase=latest` is what the experiments used. Newer LaTeX releases also accept `tagging=on` and a `pdfstandard` key (for example `ua-2`). Check what the user's TeX installation supports (`latex --version`, release date) rather than assuming.
- Tagging support is most complete with LuaLaTeX. The experiments did not test pdfLaTeX or XeLaTeX.
- Without `\DocumentMetadata`, LaTeX produces an untagged PDF (score 12 at best) no matter what else is right.
- Packages vary in tagging support. Before relying on one, check the LaTeX Project's tagging status list (latex3.github.io/tagging-project). Tagging problems often show up only as missing or broken structure, not as compile errors.

---

## 5. Checklist the Skill could apply to a .tex file

1. `\DocumentMetadata{...}` is the first line, with `lang=` matching the document's language.
2. `\hypersetup{pdftitle={...}}` is set to a meaningful title, not the filename.
3. The compile engine is LuaLaTeX.
4. Every `\includegraphics` has `alt={...}` with a real description.
   - Flag any missing `alt`, since LaTeX will silently insert the filename.
   - For purely decorative images, consider the `artifact` option (**untested** in Ally).
5. Documents longer than two pages use `\section`-style headings, not `\textbf` lines. The first heading is level 1 and no levels are skipped.
6. Tables with three or more rows declare header rows (`\tagpdfsetup{table/header-rows={1}}`, or the equivalent for the user's LaTeX version).
7. No text colour lighter than `#767676` on a white page. Search for:
   - `\color{gray}`, `\color{lightgray}`, `gray!NN`, `black!NN` with NN below about 54
   - light `hyperref` link colours (`colorlinks` with `linkcolor`/`urlcolor`)
   - coloured headers, footers or theme colours (beamer)
   - any `\color{white}` text
8. Don't embed a full-page scanned image as the content of a page in an untagged document. If the document is tagged, a large image is fine.
9. After compiling, verify instead of trusting the source. Run `pdfcheck --canvas file.pdf` from the pdfcheck repository: it predicts Ally's issues and score for the checks above and prints suggestions.

---

## 6. Open questions (no Ally data yet)

- Whether missing alt text and missing table headers shrink on longer documents, as contrast does.
- Whether a small amount of low-contrast text (one gray footer line) costs as much as a full page.
- Scores for repeated issues (several figures, only some without alt text).
- Beamer slides, math (Ally may not check math at all), links, lists, footnotes and bibliographies.
- Real documents with many pages. Every test file here was one to three pages long.

If the Skill's users collect Ally results on their own documents, record the score, every issue description, and the "Increase score up to" figures. The pdfcheck repository's `probes/*/results.csv` format turns those directly into regression tests.
