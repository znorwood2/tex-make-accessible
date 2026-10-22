"""Resolve xcolor expressions to RGB and compute WCAG contrast against white."""

from __future__ import annotations

import colorsys
import re

RGB = tuple[float, float, float]

# Colours xcolor always defines (values from the xcolor manual).
BASE_COLORS: dict[str, RGB] = {
    "red": (1, 0, 0), "green": (0, 1, 0), "blue": (0, 0, 1),
    "cyan": (0, 1, 1), "magenta": (1, 0, 1), "yellow": (1, 1, 0),
    "black": (0, 0, 0), "white": (1, 1, 1),
    "gray": (0.5, 0.5, 0.5), "darkgray": (0.25, 0.25, 0.25), "lightgray": (0.75, 0.75, 0.75),
    "brown": (0.75, 0.5, 0.25), "lime": (0.75, 1, 0), "olive": (0.5, 0.5, 0),
    "orange": (1, 0.5, 0), "pink": (1, 0.75, 0.75), "purple": (0.75, 0, 0.25),
    "teal": (0, 0.5, 0.5), "violet": (0.5, 0, 0.5),
}

# WCAG AA for normal text. Ally's threshold matched this exactly (#767676 passes).
MIN_CONTRAST = 4.5


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb: RGB) -> float:
    r, g, b = (_lin(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_on_white(rgb: RGB) -> float:
    return 1.05 / (luminance(rgb) + 0.05)


def to_hex(rgb: RGB) -> str:
    return "".join(f"{round(max(0, min(1, x)) * 255):02X}" for x in rgb)


def quantize(rgb: RGB) -> RGB:
    return tuple(round(max(0, min(1, x)) * 255) / 255 for x in rgb)  # type: ignore[return-value]


def darken(rgb: RGB, target: float = 4.6) -> RGB:
    """Scale the colour toward black (keeping its hue) until it reaches the target contrast."""
    if contrast_on_white(quantize(rgb)) >= target:
        return quantize(rgb)
    lo, hi = 0.0, 1.0  # scale factor; 0 = black
    for _ in range(40):
        mid = (lo + hi) / 2
        if contrast_on_white(quantize(tuple(x * mid for x in rgb))) >= target:  # type: ignore[arg-type]
            lo = mid
        else:
            hi = mid
    return quantize(tuple(x * lo for x in rgb))  # type: ignore[arg-type]


def from_model(model: str, spec: str) -> RGB | None:
    """Convert an xcolor model/spec pair (e.g. 'HTML', '808080') to RGB."""
    model = model.strip()
    parts = [p.strip() for p in re.split(r"[,\s]+", spec.strip()) if p.strip()]
    try:
        if model == "HTML":
            h = spec.strip().lstrip("#")
            if len(h) != 6:
                return None
            return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]
        nums = [float(p) for p in parts]
        if model == "rgb" and len(nums) == 3:
            return tuple(nums)  # type: ignore[return-value]
        if model == "RGB" and len(nums) == 3:
            return tuple(x / 255 for x in nums)  # type: ignore[return-value]
        if model == "gray" and len(nums) == 1:
            return (nums[0],) * 3  # type: ignore[return-value]
        if model == "Gray" and len(nums) == 1:
            return (nums[0] / 15,) * 3  # type: ignore[return-value]
        if model == "cmyk" and len(nums) == 4:
            c, m, y, k = nums
            return ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
        if model == "cmy" and len(nums) == 3:
            return tuple(1 - x for x in nums)  # type: ignore[return-value]
        if model == "hsb" and len(nums) == 3:
            return colorsys.hsv_to_rgb(*nums)
    except ValueError:
        return None
    return None


class ColorTable:
    """Named colours known at a point in the document."""

    def __init__(self) -> None:
        self.names: dict[str, RGB | None] = dict(BASE_COLORS)

    def define(self, name: str, model: str, spec: str) -> None:
        # \definecolor may list several models separated by '/'; use the first we understand.
        rgb = None
        for mdl, sp in zip(model.split("/"), spec.split("/")):
            rgb = from_model(mdl, sp)
            if rgb is not None:
                break
        self.names[name.strip()] = rgb

    def let(self, name: str, expr: str) -> None:
        self.names[name.strip()] = self.resolve(expr)

    def resolve(self, expr: str) -> RGB | None:
        """Resolve an xcolor expression such as 'gray', 'red!30', 'blue!50!black'."""
        e = expr.strip()
        if not e or "\\" in e or "#" in e:
            return None
        complement = False
        while e.startswith("-"):
            complement = not complement
            e = e[1:]
        if "!!" in e:
            return None  # colour series: not supported
        parts = e.split("!")
        cur = self.names.get(parts[0].strip())
        if cur is None:
            return None
        i = 1
        while i < len(parts):
            try:
                pct = float(parts[i]) / 100
            except ValueError:
                return None
            other_name = parts[i + 1].strip() if i + 1 < len(parts) else "white"
            other = self.names.get(other_name)
            if other is None:
                return None
            cur = tuple(pct * a + (1 - pct) * b for a, b in zip(cur, other))  # type: ignore[assignment]
            i += 2
        if complement:
            cur = tuple(1 - x for x in cur)  # type: ignore[assignment]
        return cur
