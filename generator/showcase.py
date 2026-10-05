"""Showcase contact sheet: one example slide rendered in every theme x archetype combination, tiled into a PNG.

Every combination is built as a standalone index.html; a single grid page embeds them as scaled iframes and one
headless Chrome process screenshots it. One browser for all combinations keeps memory flat (one Chrome per
combination exhausted RAM).
"""
import html
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .parser import parse_slides_file
from .renderers import render_html_presentation
from .renderers.pdf_renderer import find_chrome_binary
from .theme_engine import ARCHETYPES_INFO, list_available_themes, load_theme

# The deck title feeds the category label; only the content slide is shown.
SHOWCASE_MARKDOWN = """# A keringési rendszer

---

# Keringés -> áttekintés

### A szív
- pitvarok és kamrák
- billentyűk -> egyirányú áramlás

### Az erek
- **artériák**: oxigéndús vér
- vénák <- visszaáramlás

### A vér
- plazma és `sejtes elemek`
- ==oxigénszállítás==
"""

SLIDE_SIZE = (1600, 900)
SCALE = 0.3
GAP = 16
ROW_LABEL_WIDTH = 260
HEADER_HEIGHT = 56


def _grid_html(theme_ids: list, archetypes: list) -> str:
    thumb_w, thumb_h = int(SLIDE_SIZE[0] * SCALE), int(SLIDE_SIZE[1] * SCALE)
    header = "".join(f"<div class='col-label'>{html.escape(a)}</div>" for a in archetypes)
    rows = []
    for theme_id in theme_ids:
        cells = "".join(
            f"<div class='cell'><iframe src='{html.escape(theme_id)}__{html.escape(a)}/index.html' scrolling='no'></iframe></div>"
            for a in archetypes
        )
        rows.append(f"<div class='row-label'>{html.escape(theme_id)}</div>{cells}")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  html, body {{ margin: 0; background: #f5f6f8; font: 600 22px system-ui, sans-serif; color: #1e2228; }}
  .grid {{ display: grid; grid-template-columns: {ROW_LABEL_WIDTH}px repeat({len(archetypes)}, {thumb_w}px);
          gap: {GAP}px; padding: 0 {GAP}px {GAP}px 0; grid-auto-rows: {thumb_h}px; }}
  .grid > .corner, .grid > .col-label {{ height: {HEADER_HEIGHT}px; align-self: end; }}
  .col-label {{ display: flex; align-items: center; justify-content: center; }}
  .row-label {{ display: flex; align-items: center; padding-left: {GAP}px; }}
  .cell {{ width: {thumb_w}px; height: {thumb_h}px; overflow: hidden; border-radius: 6px;
          box-shadow: 0 1px 4px rgba(0,0,0,.15); }}
  .cell iframe {{ width: {SLIDE_SIZE[0]}px; height: {SLIDE_SIZE[1]}px; border: 0;
                 transform: scale({SCALE}); transform-origin: 0 0; }}
</style></head><body>
<div class="grid" style="grid-template-rows: {HEADER_HEIGHT}px;"><div class="corner"></div>{header}{"".join(rows)}</div>
</body></html>"""


def render_showcase(output_path: Path, bullet_style_override: Optional[str] = None) -> Path:
    """Renders the showcase slide for every theme (rows) x archetype (columns) into one PNG grid."""
    chrome_bin = find_chrome_binary("render the showcase")
    theme_ids = [t["id"] for t in list_available_themes()]
    archetypes = list(ARCHETYPES_INFO.keys())

    thumb_w, thumb_h = int(SLIDE_SIZE[0] * SCALE), int(SLIDE_SIZE[1] * SCALE)
    page_w = ROW_LABEL_WIDTH + len(archetypes) * (thumb_w + GAP) + GAP
    page_h = HEADER_HEIGHT + len(theme_ids) * (thumb_h + GAP) + GAP
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="showcase_") as tmp:
        work = Path(tmp)
        (work / "slides.md").write_text(SHOWCASE_MARKDOWN, encoding="utf-8")
        pres = parse_slides_file(work / "slides.md")
        pres.slides = pres.slides[1:]  # drop the title slide so the content slide is the one shown on load

        for theme_id in theme_ids:
            for archetype in archetypes:
                theme = load_theme(theme_id, archetype_override=archetype, bullet_style_override=bullet_style_override)
                render_html_presentation(pres, theme, work / f"{theme_id}__{archetype}")

        grid_path = work / "showcase.html"
        grid_path.write_text(_grid_html(theme_ids, archetypes), encoding="utf-8")

        cmd = [
            chrome_bin,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--allow-file-access-from-files",
            f"--user-data-dir={work / 'profile'}",
            f"--window-size={page_w},{page_h}",
            "--virtual-time-budget=3000",
            f"--screenshot={output_path}",
            str(grid_path),
        ]
        if output_path.exists():
            output_path.unlink()
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"Showcase screenshot failed: {result.stderr or result.stdout}")

    return output_path
