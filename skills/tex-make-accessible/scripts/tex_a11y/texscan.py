"""Low-level helpers for reading LaTeX source without a full TeX parser.

The main idea is a *masked* copy of the source: the same length as the
original, with comments and verbatim material blanked out. Searches run on
the masked text, so offsets found there are valid in the original text too.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field

VERBATIM_ENVS = ("verbatim", "verbatim*", "Verbatim", "lstlisting", "minted", "comment", "filecontents", "filecontents*")


def _blank(s: str) -> str:
    """Replace every character except newlines with a space."""
    return re.sub(r"[^\n]", " ", s)


def mask(text: str) -> str:
    """Return text with comments, \\verb and verbatim environments blanked."""
    out = list(text)
    n = len(text)
    i = 0
    env_re = re.compile(r"\\begin\{(" + "|".join(re.escape(e) for e in VERBATIM_ENVS) + r")\}")
    while i < n:
        c = text[i]
        if c == "\\":
            # \verb|...|
            if text.startswith("verb", i + 1) and i + 5 < n and not text[i + 5].isalpha():
                j = i + 5
                if j < n and text[j] == "*":
                    j += 1
                if j < n:
                    delim = text[j]
                    end = text.find(delim, j + 1)
                    nl = text.find("\n", j + 1)
                    if end != -1 and (nl == -1 or end < nl):
                        for k in range(j + 1, end):
                            out[k] = " "
                        i = end + 1
                        continue
            m = env_re.match(text, i)
            if m:
                env = m.group(1)
                end_tag = "\\end{" + env + "}"
                end = text.find(end_tag, m.end())
                if end == -1:
                    end = n
                for k in range(m.end(), end):
                    if text[k] != "\n":
                        out[k] = " "
                i = end + len(end_tag)
                continue
            i += 2  # skip escaped character, e.g. \% or \\
            continue
        if c == "%":
            j = text.find("\n", i)
            if j == -1:
                j = n
            for k in range(i, j):
                out[k] = " "
            i = j
            continue
        i += 1
    return "".join(out)


class LineIndex:
    """Map character offsets to 1-based line numbers."""

    def __init__(self, text: str):
        self.starts = [0] + [m.end() for m in re.finditer(r"\n", text)]

    def line(self, pos: int) -> int:
        return bisect.bisect_right(self.starts, pos)

    def line_start(self, pos: int) -> int:
        return self.starts[self.line(pos) - 1]


def read_group(s: str, pos: int, open_ch: str = "{", close_ch: str = "}") -> int | None:
    """Given s[pos] == open_ch, return the index just after the matching close.

    For brace groups, nested braces count. For bracket groups, a closing
    bracket only counts outside braces. Escaped characters are skipped.
    Returns None if unbalanced.
    """
    if pos >= len(s) or s[pos] != open_ch:
        return None
    depth_brace = 0
    depth = 0
    i = pos
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if open_ch == "{":
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
        else:
            if c == "{":
                depth_brace += 1
            elif c == "}":
                depth_brace -= 1
            elif depth_brace == 0:
                if c == open_ch:
                    depth += 1
                elif c == close_ch:
                    depth -= 1
                    if depth == 0:
                        return i + 1
        i += 1
    return None


def skip_space(s: str, pos: int) -> int:
    """Skip spaces and at most one newline (a blank line ends argument scanning)."""
    newlines = 0
    while pos < len(s) and s[pos] in " \t\n":
        if s[pos] == "\n":
            newlines += 1
            if newlines > 1:
                break
        pos += 1
    return pos


@dataclass
class Arg:
    kind: str          # "o" (optional [..]) or "m" (mandatory {..})
    start: int         # offset of the opening delimiter
    end: int           # offset just after the closing delimiter
    present: bool = True

    @property
    def inner(self) -> tuple[int, int]:
        return (self.start + 1, self.end - 1)


@dataclass
class Command:
    name: str
    start: int
    end: int
    star: bool
    args: list[Arg] = field(default_factory=list)

    def arg_text(self, text: str, i: int) -> str | None:
        a = self.args[i]
        if not a.present:
            return None
        s, e = a.inner
        return text[s:e]


def parse_args(s: str, pos: int, spec: str) -> tuple[list[Arg], int] | None:
    """Parse arguments after a command according to spec ("o" optional, "m" mandatory).

    A mandatory argument may also be a single unbraced token (e.g. \\input file);
    that case is not supported and returns None.
    """
    args: list[Arg] = []
    for kind in spec:
        p = skip_space(s, pos)
        if kind == "o":
            if p < len(s) and s[p] == "[":
                end = read_group(s, p, "[", "]")
                if end is None:
                    return None
                args.append(Arg("o", p, end))
                pos = end
            else:
                args.append(Arg("o", pos, pos, present=False))
        else:
            if p < len(s) and s[p] == "{":
                end = read_group(s, p, "{", "}")
                if end is None:
                    return None
                args.append(Arg("m", p, end))
                pos = end
            else:
                return None
    return args, pos


def find_commands(masked: str, name: str, spec: str = "", start: int = 0, end: int | None = None) -> list[Command]:
    """Find every \\name (optionally starred) with arguments per spec."""
    out = []
    end = len(masked) if end is None else end
    pat = re.compile(r"\\" + re.escape(name) + r"(?![A-Za-z@])(\*?)")
    for m in pat.finditer(masked, start, end):
        # Skip if this backslash is itself escaped (\\name is a line break + text).
        k = m.start() - 1
        bs = 0
        while k >= 0 and masked[k] == "\\":
            bs += 1
            k -= 1
        if bs % 2 == 1:
            continue
        parsed = parse_args(masked, m.end(), spec) if spec else ([], m.end())
        if parsed is None:
            continue
        args, cend = parsed
        out.append(Command(name, m.start(), cend, bool(m.group(1)), args))
    return out


def split_top_level(s: str, sep: str = ",") -> list[tuple[int, int]]:
    """Split s at top-level separators (not inside braces). Returns spans."""
    spans = []
    depth = 0
    last = 0
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == sep and depth == 0:
            spans.append((last, i))
            last = i + 1
        i += 1
    spans.append((last, len(s)))
    return spans


def strip_braces(v: str) -> str:
    v = v.strip()
    while len(v) >= 2 and v[0] == "{" and read_group(v, 0) == len(v):
        v = v[1:-1].strip()
    return v


def parse_keyvals(s: str) -> list[tuple[str, str | None, tuple[int, int]]]:
    """Parse a key=value list. Returns (key, value or None, span of the item)."""
    items = []
    for a, b in split_top_level(s):
        raw = s[a:b]
        if not raw.strip():
            continue
        eq = None
        depth = 0
        for i, c in enumerate(raw):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            elif c == "=" and depth == 0:
                eq = i
                break
        if eq is None:
            items.append((raw.strip(), None, (a, b)))
        else:
            items.append((raw[:eq].strip(), strip_braces(raw[eq + 1:]), (a, b)))
    return items


def plain_text(tex: str) -> str:
    """Rough conversion of a short LaTeX fragment (like a title) to plain text."""
    s = tex
    # Drop \thanks{...} and \footnote{...} with their arguments.
    for cmd in ("thanks", "footnote", "footnotemark", "label"):
        while True:
            m = re.search(r"\\" + cmd + r"(?![A-Za-z])\s*", s)
            if not m:
                break
            e = m.end()
            if e < len(s) and s[e] == "[":
                e2 = read_group(s, e, "[", "]")
                e = e2 if e2 else e
            if e < len(s) and s[e] == "{":
                e2 = read_group(s, e)
                e = e2 if e2 else e
            s = s[: m.start()] + s[e:]
    s = re.sub(r"\\\\(\[[^\]]*\])?", " ", s)
    s = s.replace("~", " ")
    s = re.sub(r"\\(newline|linebreak|par|quad|qquad|,|;|:|!| )", " ", s)
    s = re.sub(r"\\([&%$#_{}])", r"\1", s)
    s = s.replace("--", "–")
    s = re.sub(r"\\[A-Za-z@]+\*?(\[[^\]]*\])?", "", s)
    s = s.replace("{", "").replace("}", "").replace("$", "")
    return re.sub(r"\s+", " ", s).strip()
