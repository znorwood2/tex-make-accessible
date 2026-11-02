# LuaLaTeX tagging errors and fixes

All of these were reproduced with TeX Live 2026 (LuaHBTeX 1.24, `tagging=on`, MathML on). The `fix` script handles the ones marked **auto**.

Many tagging problems produce output that looks fine on screen. Read the log for `Package tagpdf Error` and `Warning` lines, not just the exit code.

| Symptom in the log | Cause | Fix |
|---|---|---|
| `Runaway argument? \begin ...` / `Paragraph ended before \environment equation was complete`; text after equations goes missing | A macro hides `\begin{equation}`/`\end{equation}` (e.g. `\newcommand{\beq}{\begin{equation}}`). With MathML tagging, math environments read their body as an argument and must see the `\end{...}` written out. | **auto:** write the environments out at each use. |
| `The number of automatic begin (N) and end (M) text-unit para hooks differ!`, plus `The structure section can not be closed` | **Display math** (`\[ \]`, `equation`, `align*`, `gather*`, ...) **inside a `center` environment.** | **auto** when `center` holds only display math: remove `center` (display math is centred anyway). Otherwise move the math out. |
| Same "para hooks differ" error, near a box | **A run-in heading** (`\@startsection` with a negative after-skip, like amsart's `\subsection`) **followed directly by a `tcolorbox`**, or a heading **inside** a `tcolorbox`. | Put the heading above the box, and use a display heading (positive after-skip). |
| Same error elsewhere | Usually an unsupported package. | Check `data/packages.json` or the tagging status list. Search https://github.com/latex3/tagging-project/issues. Try `lualatex-dev` to see whether a fix is in the pre-release. |
| `LaTeX template Error: The instance 'proof-3' of type 'block' is unknown` | A `proof` inside lists nested two deep. | **auto:** `\DeclareInstanceCopy{block}{proof-3}{proof-2}` (and `proof-4` for deeper). |
| `tag \l__tag_name_sec/10000_tl is not known`, `invalid escape sequence near '\l'`, `Missing number` at each numbered heading | `\tableofcontents` in **amsart** (amsart's contents code isn't supported yet). | Switch to `article`, or drop the table of contents. Redefining amsart's `\l@section` doesn't help. |
| `Parent-Child 'Link' --> 'Link'` (many) | `\ref` (or `\eqref`, `\cite`) in a heading: in the contents and bookmarks it becomes a link inside a link. | **auto:** `\ref*`. For `\cite` in headings, consider moving the citation out of the heading. |
| `Unknown color 'NAME'` in `\hypersetup` | Colour used by `\hypersetup` before it's defined: hyperref resolves colours immediately. | **auto:** `fix` defines its colours right after the colour package. For your own colours, define them before `\hypersetup`. |
| `Font shape 'TU/txr/b/n' undefined` (or similar `TU/...`) | A pdfLaTeX font package (`txfonts`, `mathptmx`, ...) under LuaLaTeX: bold or italic silently fall back to regular. | Replace with `unicode-math` and OpenType fonts (`data/fonts.json`). Remove `amssymb`. |
| `Undefined control sequence` for a math symbol used in the preamble (e.g. in `\setbox...\hbox{$\langle$}`) after switching to `unicode-math` | `unicode-math` defines symbols at `\begin{document}`. | Wrap that preamble code in `\AtBeginDocument{...}`. |
| `LaTeX Error: Command \X undefined` for something the author's macro file defines | The macro file is loaded from an absolute path that doesn't exist here. | Ask for the file. Don't guess its contents. |
| `Parent-Child 'mathml:mo' --> 'mathml:math'` or `'P' --> 'mathml:math'` (a few) | MathML structure nesting inside some constructs. | Minor; mention it, no action needed. |

## Other things compiling can reveal

- **Page count changes** (different fonts, or text that was being swallowed). Ally requires headings from 3 pages.
- **Overfull lines on slides:** `ltx-talk`'s smallest size is 10pt. Break long equations over lines.
- **`ltx-talk` projector PDFs** draw not-yet-revealed overlay text transparent. pdfcheck counts that as a contrast failure; post the `handout` build in Canvas.
