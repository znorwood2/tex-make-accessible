# tex-make-accessible

Tools and an AI skill (for Claude and ChatGPT) that help UNL math colleagues fix LaTeX source so it compiles to accessible, tagged PDFs. The target is WCAG 2.1 AA; a 100% Anthology Ally score in Canvas is the first milestone.

**Status:** early development. The command-line checker and fixer (`tex-a11y check` / `tex-a11y fix`) work; the AI skill itself is not written yet. See [PLAN.md](PLAN.md).

## Try it

Requires TeX Live 2026 (to compile the result) and Python 3.9+.

```sh
python3 skills/tex-make-accessible/scripts/tex-a11y check mydoc.tex
python3 skills/tex-make-accessible/scripts/tex-a11y fix mydoc.tex
lualatex mydoc-accessible.tex && lualatex mydoc-accessible.tex
```

Details: [skills/tex-make-accessible/scripts/README.md](skills/tex-make-accessible/scripts/README.md).

## Related

- [Department resource page](https://zachnorwood.github.io/math-resources-e4d30825c35241edbce4876eb472905a/): the guidance this tool follows.
- [pdfcheck](https://github.com/znorwood2/pdfcheck): predicts a PDF's Ally score before upload.
- [docs/ally-findings.md](docs/ally-findings.md): what Ally rewards, from controlled experiments.

## Development

```sh
python3 -m unittest discover tests
python3 dev/update_packages.py /path/to/clone/of/latex3/tagging-project   # refresh package data
```
