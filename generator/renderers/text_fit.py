"""Measures PPTX text at generation time with bundled metric-compatible fonts.

PowerPoint lays text out with the font named in the run (Calibri, Arial, ...). The files in
`generator/fonts/` are only used here to measure; they are never embedded in the PPTX.
"""
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import ImageFont

from ..markdown_utils import parse_markdown_runs

FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"
_MEASURE_PX = 1000  # glyph widths are measured at 1000 px per em, then scaled to the point size


@dataclass(frozen=True)
class _Face:
    files: Tuple[str, str, str, str]  # regular, bold, italic, bold italic
    bold_variation: Optional[bytes] = None  # variable fonts: named instance used for bold
    width_scale: float = 1.0  # > 1.0 when the stand-in font is not metric-compatible


_CARLITO = _Face(("Carlito-Regular.ttf", "Carlito-Bold.ttf", "Carlito-Italic.ttf", "Carlito-BoldItalic.ttf"))
_LIB_SANS = ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "LiberationSans-Italic.ttf", "LiberationSans-BoldItalic.ttf")
_LIB_MONO = ("LiberationMono-Regular.ttf", "LiberationMono-Bold.ttf", "LiberationMono-Italic.ttf", "LiberationMono-BoldItalic.ttf")

# PPTX font name -> measuring face. Carlito, Liberation Sans and Gelasio are metric-compatible with
# Calibri, Arial and Georgia. Liberation Mono is wider than Consolas, so it errs on the safe side.
# Arial Black has a single heavy weight that is roughly a fifth wider than Arial Bold.
_FACES = {
    "Calibri": _CARLITO,
    "Arial": _Face(_LIB_SANS),
    "Arial Black": _Face((_LIB_SANS[1], _LIB_SANS[1], _LIB_SANS[3], _LIB_SANS[3]), width_scale=1.2),
    "Georgia": _Face(("Gelasio[wght].ttf", "Gelasio[wght].ttf", "Gelasio-Italic[wght].ttf", "Gelasio-Italic[wght].ttf"), bold_variation=b"Bold"),
    "Consolas": _Face(_LIB_MONO, width_scale=1.08),
}

# Break opportunities: after whitespace, and after '-' or '/' inside a word (as PowerPoint does in URLs).
_PIECE_RE = re.compile(r"\s+|[^\s/\-]*[/\-]+|[^\s/\-]+")


@lru_cache(maxsize=None)
def _font(font_name: str, bold: bool, italic: bool) -> Tuple[ImageFont.FreeTypeFont, float]:
    face = _FACES.get(font_name, _CARLITO)
    path = FONTS_DIR / face.files[(2 if italic else 0) + (1 if bold else 0)]
    font = ImageFont.truetype(str(path), _MEASURE_PX)
    if face.bold_variation:
        font.set_variation_by_name(face.bold_variation if bold else b"Regular")
    return font, face.width_scale


def line_height_pt(font_name: str, size_pt: float) -> float:
    """Single-spaced line pitch: ascent + descent, which PowerPoint uses for 100% line spacing."""
    font, _ = _font(font_name, False, False)
    ascent, descent = font.getmetrics()
    return size_pt * (ascent + descent) / _MEASURE_PX


def _width_pt(text: str, font_name: str, bold: bool, italic: bool, size_pt: float) -> float:
    font, scale = _font(font_name, bold, italic)
    return font.getlength(text) * size_pt / _MEASURE_PX * scale


@dataclass
class Wrapped:
    lines: int
    broke_word: bool  # a word was wider than the line and had to be split mid-word


def wrap_markdown(text: str, font_name: str, size_pt: float, width_pt: float,
                  bold: bool = False, prefix: str = "") -> Wrapped:
    """Counts the lines PowerPoint needs for one paragraph of inline Markdown at `size_pt` in `width_pt`."""
    # Styled chunks: (text, bold, italic, font, size). "\n" marks a soft line break.
    chunks = [(prefix, True, False, font_name, size_pt)] if prefix else []
    for run in parse_markdown_runs(text):
        if run.is_break:
            chunks.append(("\n", False, False, font_name, size_pt))
            continue
        run_font = "Consolas" if run.is_code else font_name
        run_size = size_pt * 0.72 if (run.is_sub or run.is_sup) else size_pt
        chunks.append((run.text, bold or run.is_bold or run.is_arrow, run.is_italic, run_font, run_size))

    # Items: [width, kind, can_break_after], kind is "word", "space" or "br".
    # Consecutive pieces without a break opportunity form one word, even across runs.
    items: List[list] = []
    for chunk, is_bold, is_italic, run_font, run_size in chunks:
        if chunk == "\n":
            items.append([0.0, "br", True])
            continue
        for piece in _PIECE_RE.findall(chunk):
            w = _width_pt(piece, run_font, is_bold, is_italic, run_size)
            if piece.isspace():
                items.append([w, "space", True])
            elif items and items[-1][1] == "word" and not items[-1][2]:
                items[-1][0] += w
                items[-1][2] = piece[-1] in "-/"
            else:
                items.append([w, "word", piece[-1] in "-/"])

    lines, x, pending, broke = 1, 0.0, 0.0, False
    for w, kind, _ in items:
        if kind == "br":
            lines, x, pending = lines + 1, 0.0, 0.0
        elif kind == "space":
            pending += w
        else:
            if x > 0 and x + pending + w > width_pt:
                lines, x = lines + 1, 0.0
            elif x > 0:
                x += pending
            pending = 0.0
            if w > width_pt:
                broke = True
                extra = math.ceil(w / width_pt) - 1
                lines += extra
                x = w - extra * width_pt
            else:
                x += w
    return Wrapped(lines, broke)
