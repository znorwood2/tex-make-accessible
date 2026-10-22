# tex-a11y

Checks and fixes LaTeX source so it compiles to an accessible, tagged PDF. Needs only Python 3.9 or later; nothing to install.

## Use

```sh
python3 path/to/tex-a11y check worksheet.tex    # report problems; changes nothing
python3 path/to/tex-a11y fix worksheet.tex      # write worksheet-accessible.tex + worksheet-accessible.diff
```

Then compile `worksheet-accessible.tex` with LuaLaTeX, twice. Your original files are never changed. Included files (`\input`, `\include`) that need changes get their own `-accessible` copies, and the fixed main file points to them.

Options:

| Option | Meaning |
|---|---|
| `--lang de-DE` | Document language, if it isn't English and isn't set by babel/polyglossia |
| `--no-math-alt` | Leave out `math/alt/use` (better for screen readers that support MathML; Ally may score lower) |
| `--texlive 2026` | TeX Live year where you compile, if `lualatex` isn't on this machine |
| `--dry-run` | (`fix`) Print the changes as a diff; write nothing |
| `-o FILE` | (`fix`) Name of the fixed main file |
| `--json` | Machine-readable report (used by the AI skill) |
| `-v` | Also list information-only items |

`check` exits with status 1 if errors or blockers remain, so it can be used in scripts.

## What the report means

Each finding is in one of these groups:

- **Stop and decide first:** the document can't be tagged as it is. Examples: Beamer, the `exam` class, an unsupported class, TeX Live older than 2026.
- **Automatic fixes:** what `fix` changes:
  - the `\DocumentMetadata` block from the [department resource page](https://zachnorwood.github.io/math-resources-e4d30825c35241edbce4876eb472905a/);
  - the LuaLaTeX magic comment;
  - `pdftitle` taken from `\title`;
  - loading `hyperref`, and loading it last;
  - removing `inputenc`, `fontenc`, `lmodern` and `enumitem`;
  - darker shades for text colours below 4.5:1 contrast, including hyperref link colours;
  - `$$...$$` to `\[...\]`.
- **Needs judgment:** questions for you or the AI:
  - alt text for figures and TikZ pictures;
  - header rows or columns for tables with 3+ rows;
  - fake headings (bold lines);
  - heading levels;
  - a missing title;
  - vague link text.
- **Needs a manual change:**
  - pdfLaTeX font packages (with a suggested OpenType replacement);
  - white text;
  - `hyperref` that can't be moved safely;
  - unpaired `$$`.
- **For information:**
  - packages that are only partly supported by tagging, or not yet checked;
  - the `math/alt/use` trade-off.

Package and class support comes from the LaTeX Project's [tagging status list](https://latex3.github.io/tagging-project/tagging-status/), copied into `../data/packages.json` (see `dev/update_packages.py` in the repository).

## Limits

The tool reads TeX source with patterns, not with TeX itself, so:

- **Macros can hide things.** It can't see through custom macros that hide `\section`, `\includegraphics` or colours, and it may miss or misplace something in unusual code.
- **Page counts are estimates** unless a compiled PDF sits next to the `.tex` file.
- **A clean report isn't the end.** Always compile the result and check it with `pdfcheck --canvas` or in Ally.
