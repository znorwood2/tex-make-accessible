"""Tests for tex-a11y check/fix. Run from the repo root: python3 -m unittest discover tests"""

import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "tex-make-accessible" / "scripts"))

from tex_a11y import colors  # noqa: E402
from tex_a11y.checks import Options, analyze  # noqa: E402
from tex_a11y.fixer import fix, write  # noqa: E402
from tex_a11y.texscan import mask, parse_keyvals, plain_text  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
OPTS = Options(texlive=2026)


def codes(analysis, action=None):
    return sorted(f.code for f in analysis.findings if action is None or f.action == action)


class TempDoc(unittest.TestCase):
    """Helpers for writing small documents into a temporary folder."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir)

    def doc(self, body, name="doc.tex"):
        p = self.dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
        return p

    def fixed(self, path, opts=OPTS):
        res = fix(analyze(path, opts))
        write(res)
        out = path.with_name(path.stem + "-accessible.tex")
        return out.read_text(encoding="utf-8") if out.exists() else path.read_text(encoding="utf-8")


class TestColors(unittest.TestCase):
    def test_ally_threshold(self):
        self.assertGreaterEqual(colors.contrast_on_white(colors.from_model("HTML", "767676")), 4.5)
        self.assertLess(colors.contrast_on_white(colors.from_model("HTML", "808080")), 4.5)

    def test_xcolor_expressions(self):
        t = colors.ColorTable()
        self.assertEqual(t.resolve("black!50"), (0.5, 0.5, 0.5))
        self.assertEqual(t.resolve("red!50!blue"), (0.5, 0, 0.5))
        self.assertEqual(t.resolve("-white"), (0, 0, 0))
        self.assertIsNone(t.resolve("NavyBlue"))
        t.define("mine", "rgb", "0.2,0.4,0.6")
        self.assertEqual(t.resolve("mine"), (0.2, 0.4, 0.6))

    def test_darken_passes_and_keeps_hue(self):
        for name in ("gray", "red", "orange", "cyan", "lightgray"):
            rgb = colors.BASE_COLORS[name]
            new = colors.darken(rgb)
            self.assertGreaterEqual(colors.contrast_on_white(new), 4.5, name)


class TestScan(unittest.TestCase):
    def test_mask_comments_and_verbatim(self):
        src = "a % comment\n50\\% b\n\\begin{verbatim}\n$$x$$\n\\end{verbatim}\n\\verb|$$|"
        m = mask(src)
        self.assertEqual(len(m), len(src))
        self.assertNotIn("comment", m)
        self.assertIn("50\\%", m)
        self.assertNotIn("$$", m)

    def test_keyvals_and_plain_text(self):
        kv = parse_keyvals("lang = en-US, tagging-setup = {math/setup=mathml-SE, math/alt/use}")
        self.assertEqual(kv[0][:2], ("lang", "en-US"))
        self.assertEqual(kv[1][1], "math/setup=mathml-SE, math/alt/use")
        self.assertEqual(plain_text(r"Worksheet 3\thanks{Draft}: \emph{Limits}\\ and $x^2$"),
                         "Worksheet 3: Limits and x^2")


class TestFixtures(unittest.TestCase):
    def test_resource_page_example_is_clean(self):
        a = analyze(FIXTURES / "good" / "tagged-pdf-example.tex", OPTS)
        serious = [f for f in a.findings if f.severity in ("blocker", "error", "warning")]
        self.assertEqual(serious, [], [f.message for f in serious])

    def test_worksheet_findings(self):
        a = analyze(FIXTURES / "worksheet" / "worksheet.tex", OPTS)
        found = set(codes(a))
        for code in ("METADATA_MISSING", "ENGINE_COMMENT", "CONTRAST_LOW", "PDFTITLE_MISSING", "FONT_PDFTEX",
                     "HYPERREF_NOT_LAST", "ENUMITEM", "DOLLAR_DISPLAY", "DOLLAR_UNPAIRED", "ALT_MISSING",
                     "TABLE_NO_HEADERS", "HEADING_START", "FAKE_HEADING", "LINK_TEXT", "CONTRAST_NEAR_WHITE"):
            self.assertIn(code, found)

    def test_fix_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("worksheet", "multifile"):
                shutil.copytree(FIXTURES / name, Path(d) / name)
            for main in (Path(d) / "worksheet" / "worksheet.tex", Path(d) / "multifile" / "main.tex"):
                write(fix(analyze(main, OPTS)))
                out = main.with_name(main.stem + "-accessible.tex")
                again = analyze(out, OPTS)
                self.assertEqual(codes(again, "auto"), [], main.name)

    def test_multifile_includes_point_to_copies(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(FIXTURES / "multifile", Path(d) / "multifile")
            main = Path(d) / "multifile" / "main.tex"
            write(fix(analyze(main, OPTS)))
            out = (Path(d) / "multifile" / "main-accessible.tex").read_text()
            self.assertIn("\\input{preamble-accessible}", out)
            self.assertIn("\\include{chapters/one-accessible}", out)
            self.assertTrue((Path(d) / "multifile" / "chapters" / "one-accessible.tex").exists())
            self.assertIn("\\[A \\cup B\\]", (Path(d) / "multifile" / "chapters" / "one-accessible.tex").read_text())
            # originals untouched
            self.assertIn("$$A \\cup B$$", (Path(d) / "multifile" / "chapters" / "one.tex").read_text())


class TestMetadata(TempDoc):
    def test_old_testphase_block_is_replaced(self):
        p = self.doc(r"""
            \DocumentMetadata{testphase=latest, lang=en-GB}
            \documentclass{article}
            \begin{document}
            Hi.
            \end{document}
            """)
        out = self.fixed(p)
        self.assertNotIn("testphase", out)
        self.assertIn("lang = en-GB", out)
        self.assertIn("tagging = on", out)
        self.assertIn("math/alt/use", out)

    def test_deliberate_no_math_alt_is_kept(self):
        p = self.doc(r"""
            \DocumentMetadata{lang=en-US, pdfversion=2.0, tagging=on, pdfstandard=ua-2,
              tagging-setup={math/setup=mathml-SE}}
            \documentclass{article}
            \usepackage{hyperref}
            \hypersetup{pdftitle={T}}
            \begin{document}
            Hi.
            \end{document}
            """)
        a = analyze(p, OPTS)
        self.assertNotIn("METADATA_UPDATE", codes(a))
        self.assertIn("MATH_ALT_OFF", codes(a))

    def test_metadata_after_documentclass_is_moved_to_top(self):
        p = self.doc(r"""
            % my notes
            \documentclass{article}
            \DocumentMetadata{lang=en-US}
            \begin{document}
            Hi.
            \end{document}
            """)
        out = self.fixed(p)
        self.assertLess(out.index("\\DocumentMetadata"), out.index("\\documentclass"))
        self.assertEqual(out.count("\\DocumentMetadata"), 1)

    def test_language_from_babel(self):
        p = self.doc(r"""
            \documentclass{article}
            \usepackage[english,ngerman]{babel}
            \begin{document}
            Hallo.
            \end{document}
            """)
        self.assertIn("lang = de-DE", self.fixed(p))

    def test_mismatched_language_is_reported(self):
        p = self.doc(r"""
            \DocumentMetadata{lang=en-US, pdfversion=2.0, tagging=on, pdfstandard=ua-2,
              tagging-setup={math/setup=mathml-SE, math/alt/use}}
            \documentclass{article}
            \usepackage[french]{babel}
            \begin{document}
            Bonjour.
            \end{document}
            """)
        self.assertIn("LANG_MISMATCH", codes(analyze(p, OPTS)))


class TestBodyChecks(TempDoc):
    PRE = "\\DocumentMetadata{lang=en-US, pdfversion=2.0, tagging=on, pdfstandard=ua-2, tagging-setup={math/setup=mathml-SE, math/alt/use}}\n\\documentclass{article}\n\\usepackage{graphicx,tikz,xcolor,hyperref}\n\\hypersetup{pdftitle={T}}\n\\begin{document}\n"

    def body(self, text):
        return self.doc(self.PRE + textwrap.dedent(text) + "\n\\end{document}\n")

    def test_alt_text_variants(self):
        p = self.body(r"""
            \includegraphics[alt={A parabola opening upward with vertex (3,-6)}]{a.png}
            \includegraphics[alt=b.png]{b.png}
            \includegraphics[alt=image]{c}
            \includegraphics[artifact]{logo}
            \begin{tikzpicture}[alt={The Petersen graph}]\end{tikzpicture}
            """)
        self.assertEqual(codes(analyze(p, OPTS), "judgment"), ["ALT_FILENAME", "ALT_WEAK"])

    def test_table_header_tracking(self):
        p = self.body(r"""
            \begin{center}
            \tagpdfsetup{table/header-rows={1}}
            \begin{tabular}{ll} a & b \\ 1 & 2 \\ 3 & 4 \end{tabular}
            \end{center}
            \begin{tabular}{ll} a & b \\ 1 & 2 \\ 3 & 4 \end{tabular}
            \begin{tabular}{ll} a & b \\ 1 & 2 \end{tabular}
            """)
        a = analyze(p, OPTS)
        no_headers = [f for f in a.findings if f.code == "TABLE_NO_HEADERS"]
        self.assertEqual(len(no_headers), 1)  # second table: setting was local to center; third has 2 rows
        self.assertEqual(no_headers[0].data["first_rows"][0], "a & b")

    def test_heading_skip_and_fake_headings(self):
        p = self.body(r"""
            \section{One}
            \subsubsection{Too deep}

            \textbf{Looks like a heading}

            \textbf{Problem 1.} Compute this.
            """)
        found = codes(analyze(p, OPTS))
        self.assertIn("HEADING_SKIP", found)
        self.assertEqual(found.count("FAKE_HEADING"), 1)

    def test_contrast_ok_colors_untouched(self):
        p = self.body(r"""
            {\color{black!60} fine} \textcolor[HTML]{767676}{fine} \textcolor{blue}{fine}
            \textcolor[HTML]{AAAAAA}{too light}
            """)
        a = analyze(p, OPTS)
        low = [f for f in a.findings if f.code == "CONTRAST_LOW"]
        self.assertEqual(len(low), 1)
        out = self.fixed(p)
        self.assertIn("\\textcolor{a11yHTMLAAAAAA}{too light}", out)
        self.assertIn("\\definecolor{a11yHTMLAAAAAA}", out)

    def test_missing_title_needs_judgment(self):
        p = self.doc(r"""
            \documentclass{article}
            \begin{document}
            Hi.
            \end{document}
            """)
        a = analyze(p, OPTS)
        self.assertIn("TITLE_MISSING", codes(a, "judgment"))
        self.assertIn("HYPERREF_MISSING", codes(a, "auto"))

    def test_hard_cases(self):
        for cls, code in (("beamer", "CLASS_BEAMER"), ("exam", "CLASS_EXAM"), ("amsart", "CLASS_PARTIAL")):
            p = self.doc("\\documentclass{%s}\n\\begin{document}\nHi.\n\\end{document}\n" % cls, f"{cls}.tex")
            self.assertIn(code, codes(analyze(p, OPTS)), cls)

    def test_old_texlive_blocks(self):
        p = self.doc("\\documentclass{article}\n\\begin{document}\nHi.\n\\end{document}\n")
        self.assertIn("TEXLIVE_OLD", codes(analyze(p, Options(texlive=2024))))

    def test_standalone_figure_is_skipped(self):
        p = self.doc("\\documentclass{standalone}\n\\usepackage{tikz}\n\\begin{document}\n"
                     "\\begin{tikzpicture}\\draw (0,0)--(1,1);\\end{tikzpicture}\n\\end{document}\n")
        self.assertEqual(codes(analyze(p, OPTS)), ["STANDALONE_FIGURE"])

    def test_not_main_file(self):
        p = self.doc("\\section{Only a chapter}\n")
        self.assertEqual(codes(analyze(p, OPTS)), ["NOT_MAIN_FILE"])


if __name__ == "__main__":
    unittest.main()
