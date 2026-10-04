import base64
import html
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from ..models import PresentationData, SlideData, SlideType, ThemeConfig, TableData
from ..markdown_utils import render_markdown_html


def render_html_presentation(pres: PresentationData, theme: ThemeConfig, dist_dir: Path) -> Path:
    dist_dir.mkdir(parents=True, exist_ok=True)
    html_file = dist_dir / "index.html"

    # Prepare audio assets (copy, convert to mp3 for max compatibility, generate base64)
    audio_assets: Dict[int, Dict[str, str]] = {}
    for slide in pres.slides:
        if slide.audio_path and slide.audio_path.exists():
            audio_info = _prepare_audio_asset(slide.audio_path, dist_dir)
            audio_assets[slide.index] = audio_info

    # Prepare image assets (copy to dist/images, generate base64 data URIs)
    image_assets: Dict[str, Dict[str, str]] = {}
    for slide in pres.slides:
        for img in slide.images:
            if img.resolved_path and img.resolved_path.exists():
                path_key = str(img.resolved_path.resolve())
                if path_key not in image_assets:
                    image_assets[path_key] = _prepare_image_asset(img.resolved_path, dist_dir)

    html_content = _build_html(pres, theme, audio_assets, image_assets)
    html_file.write_text(html_content, encoding="utf-8")
    return html_file


def _prepare_image_asset(src_path: Path, dist_dir: Path) -> Dict[str, str]:
    """Ensures image is copied to dist/images/ and encoded as Base64 Data URI."""
    images_dir = dist_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    dest_path = images_dir / src_path.name
    if not dest_path.exists() or src_path.stat().st_mtime > dest_path.stat().st_mtime:
        shutil.copy2(src_path, dest_path)

    ext = src_path.suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    mime_type = mime_types.get(ext, "image/png")
    raw_bytes = src_path.read_bytes()
    b64_str = base64.b64encode(raw_bytes).decode("ascii")
    data_uri = f"data:{mime_type};base64,{b64_str}"

    return {
        "rel_path": f"images/{dest_path.name}",
        "data_uri": data_uri,
        "mime_type": mime_type
    }


def _prepare_audio_asset(src_path: Path, dist_dir: Path) -> Dict[str, str]:
    """Ensures audio is available in both MP3 (high compatibility) and original format, plus Base64."""
    # 1. Copy original file
    dest_orig = dist_dir / src_path.name
    if not dest_orig.exists() or src_path.stat().st_mtime > dest_orig.stat().st_mtime:
        shutil.copy2(src_path, dest_orig)

    mp3_filename = None
    mp3_path = dist_dir / (src_path.stem + ".mp3")

    # 2. Convert to MP3 using ffmpeg if available
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        try:
            if not mp3_path.exists() or src_path.stat().st_mtime > mp3_path.stat().st_mtime:
                cmd = [
                    ffmpeg_bin, "-y", "-i", str(src_path),
                    "-c:a", "libmp3lame", "-b:a", "128k",
                    str(mp3_path)
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if mp3_path.exists():
                mp3_filename = mp3_path.name
        except Exception as e:
            print(f"[HTML Renderer] Warning: ffmpeg MP3 conversion failed ({e})")

    # 3. Choose best file for Base64 embedding (MP3 preferred for universal browser support)
    chosen_path = mp3_path if (mp3_path.exists() and mp3_path.stat().st_size > 0) else dest_orig
    mime_type = "audio/mpeg" if chosen_path.suffix.lower() == ".mp3" else "audio/mp4"

    raw_bytes = chosen_path.read_bytes()
    b64_str = base64.b64encode(raw_bytes).decode("ascii")
    data_uri = f"data:{mime_type};base64,{b64_str}"

    return {
        "orig_name": dest_orig.name,
        "mp3_name": mp3_filename or "",
        "data_uri": data_uri,
        "mime_type": mime_type
    }


def _build_html(pres: PresentationData, theme: ThemeConfig, audio_assets: Dict[int, Dict[str, str]], image_assets: Optional[Dict[str, Dict[str, str]]] = None) -> str:
    slides_html = []
    total_slides = len(pres.slides)

    for slide in pres.slides:
        audio_info = audio_assets.get(slide.index)
        slides_html.append(_render_slide(slide, total_slides, theme, audio_info, deck_title=pres.title, image_assets=image_assets))

    slides_joined = "\n".join(slides_html)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{pres.title}</title>
  <style>
    :root {{
      --bg-color: {theme.colors['background']};
      --card-bg: {theme.colors['card_bg']};
      --card-border: {theme.colors.get('card_border', '#E2E8F0')};
      --primary-text: {theme.colors['primary_text']};
      --secondary-text: {theme.colors['secondary_text']};
      --accent: {theme.colors['accent']};
      --accent-light: {theme.colors.get('accent_light', '#EFF6FF')};
      --badge-bg: {theme.colors.get('badge_bg', '#DBEAFE')};
      --badge-text: {theme.colors.get('badge_text', '#1E40AF')};
      --audio-btn-bg: {theme.colors.get('audio_btn_bg', theme.colors['accent'])};
      --audio-btn-text: {theme.colors.get('audio_btn_text', '#FFFFFF')};
      --title-font: {theme.fonts['title_font']};
      --body-font: {theme.fonts['body_font']};
      --card-radius: {theme.styles.get('card_radius_px', 16)}px;
      --card-shadow: {theme.styles.get('card_shadow', '0 10px 25px -5px rgba(0,0,0,0.05)')};
      --border-width: {theme.styles.get('border_width_px', 1)}px;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      background: #000000;
      font-family: var(--body-font);
      color: var(--primary-text);
      margin: 0;
      padding: 0;
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      user-select: none;
    }}

    #presentation-stage {{
      width: 100vw;
      height: 100vh;
      display: flex;
      justify-content: center;
      align-items: center;
      overflow: hidden;
      background: #000000;
      touch-action: pan-y pinch-zoom;
    }}

    #presentation-viewport {{
      position: relative;
      width: 1600px;
      height: 900px;
      min-width: 1600px;
      min-height: 900px;
      max-width: 1600px;
      max-height: 900px;
      transform-origin: center center;
      background-color: var(--bg-color);
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
      overflow: hidden;
    }}

    .slide {{
      position: absolute;
      top: 0;
      left: 0;
      width: 1600px;
      height: 900px;
      display: none;
      flex-direction: column;
      padding: 60px 80px 90px 80px;
      background-color: var(--bg-color);
      opacity: 0;
      transition: opacity 0.25s ease-in-out;
      box-sizing: border-box;
    }}

    .slide.active {{
      display: flex;
      opacity: 1;
    }}

    /* Title Slide Layout */
    .slide-title-container {{
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: flex-start;
      height: 100%;
      max-width: 90%;
    }}

    .title-pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: var(--badge-bg);
      color: var(--badge-text);
      border-radius: 9999px;
      font-weight: 600;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }}

    .slide-main-title {{
      font-family: var(--title-font);
      font-weight: 800;
      color: var(--primary-text);
    }}

    .slide-author {{
      font-weight: 500;
      color: var(--secondary-text);
      display: flex;
      align-items: center;
      gap: 14px;
    }}

    .slide-author::before {{
      content: "";
      display: inline-block;
      width: 36px;
      height: 4px;
      background: var(--accent);
      border-radius: 2px;
    }}

    /* Header for Content Slides */
    .slide-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-shrink: 0;
    }}

    .header-left {{
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}

    .slide-category {{
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--accent);
    }}

    .slide-heading {{
      font-family: var(--title-font);
      font-weight: 700;
      color: var(--primary-text);
      font-size: 48px;
      line-height: 1.22;
    }}

    .slide-content {{
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: center;
      min-height: 0;
    }}

    /* Intro, Footnotes, Paragraphs */
    .slide-intro {{
      color: var(--secondary-text);
      line-height: 1.5;
    }}

    .slide-footnote {{
      color: var(--secondary-text);
      font-style: italic;
    }}

    .text-center {{
      text-align: center;
    }}

    .slide-para {{
      color: var(--primary-text);
    }}

    /* Definition Card Layout */
    .definition-card {{
      background: var(--card-bg);
      border: var(--border-width) solid var(--card-border);
      border-left: 8px solid var(--accent);
      border-radius: var(--card-radius);
      box-shadow: var(--card-shadow);
      position: relative;
    }}

    .definition-quote-icon {{
      position: absolute;
      line-height: 1;
      color: var(--accent-light);
      font-family: serif;
      pointer-events: none;
    }}

    .definition-text {{
      color: var(--primary-text);
      font-weight: 450;
    }}

    /* Multi-Card Grid Layout */
    .cards-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      height: 100%;
      align-items: stretch;
    }}

    .cards-grid:has(> .info-card:only-child) {{
      grid-template-columns: 1fr;
      max-width: 1050px;
      margin: 0 auto;
      width: 100%;
    }}

    .cards-grid:has(> .info-card:nth-child(3):last-child) > .info-card:last-child {{
      grid-column: span 2;
    }}

    .info-card {{
      background: var(--card-bg);
      border: var(--border-width) solid var(--card-border);
      border-radius: var(--card-radius);
      box-shadow: var(--card-shadow);
      display: flex;
      flex-direction: column;
      transition: transform 0.2s ease, border-color 0.2s ease;
    }}

    .info-card:hover {{
      transform: translateY(-2px);
      border-color: var(--accent);
    }}

    .card-top {{
      display: flex;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 12px;
    }}

    .card-index-badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 8px;
      background: var(--badge-bg);
      color: var(--badge-text);
      font-weight: 700;
      flex-shrink: 0;
    }}

    .card-title {{
      font-family: var(--title-font);
      font-weight: 700;
      color: var(--primary-text);
      line-height: 1.25;
    }}

    .card-desc {{
      color: var(--secondary-text);
      flex: 1;
    }}

    /* Inline Markdown Elements */
    strong {{
      font-weight: 700;
      color: var(--primary-text);
    }}

    em {{
      font-style: italic;
    }}

    code {{
      font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
      background: rgba(125, 125, 125, 0.12);
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.9em;
    }}

    del.md-strike {{
      text-decoration: line-through;
      opacity: 0.65;
    }}

    mark.md-highlight {{
      background-color: #FEF08A;
      color: #854D0E;
      padding: 1px 5px;
      border-radius: 4px;
      font-weight: 600;
    }}

    sup {{
      font-size: 0.72em;
      vertical-align: super;
      line-height: 0;
    }}

    sub {{
      font-size: 0.72em;
      vertical-align: sub;
      line-height: 0;
    }}

    /* Table Layout */
    .slide-table-container {{
      width: 100%;
      overflow-x: auto;
      margin-top: 8px;
    }}

    .slide-table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--card-bg);
      border-radius: var(--card-radius);
      overflow: hidden;
      box-shadow: var(--card-shadow);
      border: var(--border-width) solid var(--card-border);
    }}

    .slide-table th {{
      background: var(--accent);
      color: #FFFFFF;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}

    .slide-table td {{
      border-bottom: 1px solid var(--card-border);
      color: var(--primary-text);
      line-height: 1.5;
    }}

    .slide-table tr:last-child td {{
      border-bottom: none;
    }}

    .slide-table tr:nth-child(even) {{
      background: rgba(125, 125, 125, 0.03);
    }}

    .slide-table th.align-left, .slide-table td.align-left {{ text-align: left; }}
    .slide-table th.align-center, .slide-table td.align-center {{ text-align: center; }}
    .slide-table th.align-right, .slide-table td.align-right {{ text-align: right; }}

    /* Task Lists & Standard Lists */
    .content-list {{
      list-style-type: none;
      display: flex;
      flex-direction: column;
    }}

    .content-list li {{
      position: relative;
      color: var(--primary-text);
    }}

    .content-list li::before {{
      content: "";
      position: absolute;
      border-radius: 50%;
      background: var(--accent);
    }}

    .task-list li::before {{
      display: none !important;
    }}

    .task-list li {{
      padding-left: 0 !important;
    }}

    .task-item {{
      display: flex;
      align-items: flex-start;
      line-height: 1.5;
    }}

    .task-checkbox {{
      border: 2px solid var(--accent);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      background: var(--card-bg);
      font-weight: bold;
      color: transparent;
    }}

    .task-checkbox.checked {{
      background: var(--accent);
      color: #FFFFFF;
    }}

    /* Standalone Image Hero Layout */
    .slide-image-container {{
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100%;
      gap: 16px;
    }}

    .slide-hero-image {{
      max-width: 100%;
      max-height: 520px;
      object-fit: contain;
      border-radius: var(--card-radius);
      box-shadow: var(--card-shadow);
      border: var(--border-width) solid var(--card-border);
    }}

    .image-caption {{
      color: var(--secondary-text);
      font-style: italic;
      text-align: center;
    }}

    /* Split Layout: Content + Image */
    .split-layout {{
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 48px;
      align-items: center;
      height: 100%;
    }}

    .split-layout-left {{
      display: flex;
      flex-direction: column;
      justify-content: center;
    }}

    .split-layout-right {{
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }}

    .split-image {{
      max-width: 100%;
      max-height: 480px;
      object-fit: contain;
      border-radius: var(--card-radius);
      box-shadow: var(--card-shadow);
      border: var(--border-width) solid var(--card-border);
    }}

    /* Fenced Code Block */
    .code-block {{
      background: #0D1117;
      border: 1px solid var(--card-border);
      border-radius: var(--card-radius);
      overflow: hidden;
      box-shadow: var(--card-shadow);
      display: flex;
      flex-direction: column;
      height: 100%;
    }}

    .code-header {{
      background: rgba(255, 255, 255, 0.05);
      padding: 10px 22px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }}

    .code-lang {{
      font-size: 0.85rem;
      text-transform: uppercase;
      font-weight: 700;
      letter-spacing: 0.08em;
      color: var(--accent);
      font-family: monospace;
    }}

    .code-block pre {{
      background: transparent;
      padding: 24px 30px;
      color: #E6EDF3;
      font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
      line-height: 1.6;
      white-space: pre-wrap;
      overflow-x: auto;
      flex: 1;
    }}

    /* Audio Player Widget */
    .audio-widget {{
      display: inline-flex;
      align-items: center;
      gap: 12px;
      background: var(--card-bg);
      border: var(--border-width) solid var(--card-border);
      border-radius: 9999px;
      padding: 6px 18px 6px 10px;
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
      cursor: pointer;
      transition: all 0.2s ease;
      user-select: none;
    }}

    .audio-widget:hover {{
      transform: scale(1.02);
      border-color: var(--accent);
    }}

    .audio-play-btn {{
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background: var(--audio-btn-bg);
      color: var(--audio-btn-text);
      display: flex;
      align-items: center;
      justify-content: center;
      border: none;
      cursor: pointer;
      flex-shrink: 0;
      transition: background-color 0.2s ease;
    }}

    .audio-play-btn svg {{
      width: 20px;
      height: 20px;
      fill: currentColor;
    }}

    .audio-label {{
      display: flex;
      flex-direction: column;
      gap: 2px;
    }}

    .audio-label-title {{
      font-size: 0.9rem;
      font-weight: 600;
      color: var(--primary-text);
    }}

    .audio-label-status {{
      font-size: 0.78rem;
      color: var(--secondary-text);
    }}

    .audio-waves {{
      display: flex;
      align-items: center;
      gap: 3px;
      height: 16px;
      margin-left: 4px;
    }}

    .wave-bar {{
      width: 3px;
      height: 4px;
      background: var(--accent);
      border-radius: 2px;
      transition: height 0.2s ease;
    }}

    .audio-playing .wave-bar:nth-child(1) {{ animation: waveAnim 0.7s infinite alternate ease-in-out; }}
    .audio-playing .wave-bar:nth-child(2) {{ animation: waveAnim 0.9s infinite alternate ease-in-out 0.2s; }}
    .audio-playing .wave-bar:nth-child(3) {{ animation: waveAnim 0.6s infinite alternate ease-in-out 0.4s; }}
    .audio-playing .wave-bar:nth-child(4) {{ animation: waveAnim 0.8s infinite alternate ease-in-out 0.1s; }}

    @keyframes waveAnim {{
      0% {{ height: 4px; }}
      100% {{ height: 16px; }}
    }}

    /* Global Navigation Footer */
    #nav-footer {{
      position: absolute;
      bottom: 28px;
      left: 80px;
      right: 80px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      pointer-events: none;
      z-index: 100;
    }}

    .nav-controls {{
      display: flex;
      gap: 12px;
      pointer-events: auto;
    }}

    .nav-btn {{
      background: var(--card-bg);
      border: var(--border-width) solid var(--card-border);
      color: var(--primary-text);
      width: 44px;
      height: 44px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
      transition: all 0.15s ease;
    }}

    .nav-btn:hover:not(:disabled) {{
      background: var(--accent);
      color: #FFFFFF;
      border-color: var(--accent);
    }}

    .nav-btn:disabled {{
      opacity: 0.35;
      cursor: not-allowed;
    }}

    .slide-counter {{
      background: var(--card-bg);
      border: var(--border-width) solid var(--card-border);
      color: var(--secondary-text);
      padding: 8px 18px;
      border-radius: 20px;
      font-size: 1rem;
      font-weight: 600;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
      pointer-events: auto;
    }}

    /* ==========================================================
       DENSITY TIERS: SPACIOUS, BALANCED, COMPACT
       ========================================================== */

    /* 1. Spacious Tier (Light content: bold, punchy, generous) */
    .density-spacious .title-pill {{ font-size: 20px; padding: 10px 24px; margin-bottom: 32px; }}
    .density-spacious .slide-main-title {{ font-size: 76px; line-height: 1.15; margin-bottom: 32px; }}
    .density-spacious .slide-author {{ font-size: 32px; }}

    .density-spacious .slide-header {{ margin-bottom: 36px; }}
    .density-spacious .slide-category {{ font-size: 18px; }}
    .density-spacious .slide-heading {{ font-size: 48px; line-height: 1.22; }}

    .density-spacious .slide-intro {{ font-size: 28px; margin-bottom: 28px; }}
    .density-spacious .slide-footnote {{ font-size: 22px; margin-top: 26px; }}
    .density-spacious .slide-para {{ font-size: 34px; line-height: 1.6; margin-bottom: 26px; }}

    .density-spacious .content-list {{ gap: 24px; margin-top: 24px; }}
    .density-spacious .content-list li {{ font-size: 32px; line-height: 1.6; padding-left: 40px; }}
    .density-spacious .content-list li::before {{ left: 8px; top: 18px; width: 14px; height: 14px; }}
    .density-spacious .task-item {{ font-size: 32px; gap: 18px; margin-bottom: 20px; }}
    .density-spacious .task-checkbox {{ width: 32px; height: 32px; font-size: 20px; border-radius: 8px; margin-top: 4px; }}

    .density-spacious .definition-card {{ padding: 56px 68px; }}
    .density-spacious .definition-quote-icon {{ font-size: 96px; top: 28px; right: 36px; }}
    .density-spacious .definition-text {{ font-size: 40px; line-height: 1.6; }}

    .density-spacious .cards-grid {{ gap: 36px; }}
    .density-spacious .info-card {{ padding: 38px 46px; }}
    .density-spacious .card-index-badge {{ width: 48px; height: 48px; font-size: 1.3rem; }}
    .density-spacious .card-title {{ font-size: 36px; }}
    .density-spacious .card-desc {{ font-size: 26px; line-height: 1.6; }}

    .density-spacious .slide-table th {{ padding: 20px 28px; font-size: 22px; }}
    .density-spacious .slide-table td {{ padding: 20px 28px; font-size: 24px; }}
    .density-spacious .code-block pre {{ font-size: 24px; padding: 28px 36px; }}
    .density-spacious .image-caption {{ font-size: 24px; }}

    /* 2. Balanced Tier (Standard content) */
    .density-balanced .title-pill {{ font-size: 18px; padding: 8px 20px; margin-bottom: 26px; }}
    .density-balanced .slide-main-title {{ font-size: 64px; line-height: 1.18; margin-bottom: 26px; }}
    .density-balanced .slide-author {{ font-size: 28px; }}

    .density-balanced .slide-header {{ margin-bottom: 32px; }}
    .density-balanced .slide-category {{ font-size: 18px; }}
    .density-balanced .slide-heading {{ font-size: 48px; line-height: 1.22; }}

    .density-balanced .slide-intro {{ font-size: 24px; margin-bottom: 22px; }}
    .density-balanced .slide-footnote {{ font-size: 19px; margin-top: 20px; }}
    .density-balanced .slide-para {{ font-size: 28px; line-height: 1.6; margin-bottom: 20px; }}

    .density-balanced .content-list {{ gap: 18px; margin-top: 18px; }}
    .density-balanced .content-list li {{ font-size: 28px; line-height: 1.55; padding-left: 34px; }}
    .density-balanced .content-list li::before {{ left: 6px; top: 15px; width: 10px; height: 10px; }}
    .density-balanced .task-item {{ font-size: 28px; gap: 16px; margin-bottom: 16px; }}
    .density-balanced .task-checkbox {{ width: 26px; height: 26px; font-size: 16px; border-radius: 6px; margin-top: 3px; }}

    .density-balanced .definition-card {{ padding: 44px 54px; }}
    .density-balanced .definition-quote-icon {{ font-size: 76px; top: 22px; right: 30px; }}
    .density-balanced .definition-text {{ font-size: 32px; line-height: 1.55; }}

    .density-balanced .cards-grid {{ gap: 28px; }}
    .density-balanced .info-card {{ padding: 28px 34px; }}
    .density-balanced .card-index-badge {{ width: 40px; height: 40px; font-size: 1.1rem; }}
    .density-balanced .card-title {{ font-size: 30px; }}
    .density-balanced .card-desc {{ font-size: 22px; line-height: 1.55; }}

    .density-balanced .slide-table th {{ padding: 16px 22px; font-size: 18px; }}
    .density-balanced .slide-table td {{ padding: 16px 22px; font-size: 20px; }}
    .density-balanced .code-block pre {{ font-size: 20px; padding: 22px 28px; }}
    .density-balanced .image-caption {{ font-size: 20px; }}

    /* 3. Compact Tier (Dense content: fits comfortably) */
    .density-compact .title-pill {{ font-size: 16px; padding: 6px 16px; margin-bottom: 20px; }}
    .density-compact .slide-main-title {{ font-size: 54px; line-height: 1.2; margin-bottom: 22px; }}
    .density-compact .slide-author {{ font-size: 24px; }}

    .density-compact .slide-header {{ margin-bottom: 28px; }}
    .density-compact .slide-category {{ font-size: 18px; }}
    .density-compact .slide-heading {{ font-size: 48px; line-height: 1.22; }}

    .density-compact .slide-intro {{ font-size: 20px; margin-bottom: 16px; }}
    .density-compact .slide-footnote {{ font-size: 16px; margin-top: 14px; }}
    .density-compact .slide-para {{ font-size: 24px; line-height: 1.5; margin-bottom: 16px; }}

    .density-compact .content-list {{ gap: 14px; margin-top: 14px; }}
    .density-compact .content-list li {{ font-size: 24px; line-height: 1.5; padding-left: 28px; }}
    .density-compact .content-list li::before {{ left: 5px; top: 12px; width: 8px; height: 8px; }}
    .density-compact .task-item {{ font-size: 24px; gap: 12px; margin-bottom: 12px; }}
    .density-compact .task-checkbox {{ width: 22px; height: 22px; font-size: 14px; border-radius: 5px; margin-top: 2px; }}

    .density-compact .definition-card {{ padding: 32px 38px; }}
    .density-compact .definition-quote-icon {{ font-size: 58px; top: 18px; right: 26px; }}
    .density-compact .definition-text {{ font-size: 26px; line-height: 1.5; }}

    .density-compact .cards-grid {{ gap: 20px; }}
    .density-compact .info-card {{ padding: 20px 26px; }}
    .density-compact .card-index-badge {{ width: 32px; height: 32px; font-size: 0.9rem; }}
    .density-compact .card-title {{ font-size: 24px; }}
    .density-compact .card-desc {{ font-size: 18px; line-height: 1.45; }}

    .density-compact .slide-table th {{ padding: 13px 18px; font-size: 15px; }}
    .density-compact .slide-table td {{ padding: 13px 18px; font-size: 16px; }}
    .density-compact .code-block pre {{ font-size: 17px; padding: 18px 22px; }}
    .density-compact .image-caption {{ font-size: 16px; }}

    /* ==========================================================
       ARCHETYPE SPECIFIC STYLES
       ========================================================== */

    /* 1. EDITORIAL ARCHETYPE */
    .archetype-editorial {{
      font-family: Georgia, 'Times New Roman', serif;
    }}
    .archetype-editorial .slide-main-title,
    .archetype-editorial .slide-heading,
    .archetype-editorial .card-title {{
      font-family: Georgia, 'Times New Roman', serif;
      font-weight: 700;
    }}
    .archetype-editorial .title-pill {{
      background: transparent;
      color: var(--accent);
      border: 1px solid var(--accent);
      border-radius: 4px;
      font-family: Georgia, serif;
      letter-spacing: 0.12em;
    }}
    .archetype-editorial .slide-header {{
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 18px;
    }}
    .archetype-editorial .info-card {{
      background: transparent !important;
      border: none !important;
      box-shadow: none !important;
      border-left: 2px solid var(--accent) !important;
      border-radius: 0 !important;
      padding: 10px 0 10px 24px !important;
    }}
    .archetype-editorial .info-card:hover {{
      transform: none !important;
    }}
    .archetype-editorial .card-index-badge {{
      background: transparent !important;
      color: var(--accent) !important;
      border: none !important;
      font-family: Georgia, serif !important;
      font-size: 1.15rem !important;
      width: auto !important;
      height: auto !important;
      margin-top: 0 !important;
    }}
    .archetype-editorial .definition-card {{
      background: transparent !important;
      box-shadow: none !important;
      border-radius: 0 !important;
      border: none !important;
      border-top: 1px solid var(--card-border) !important;
      border-bottom: 1px solid var(--card-border) !important;
      padding: 36px 0 !important;
    }}
    .archetype-editorial .definition-text {{
      font-family: Georgia, 'Times New Roman', serif;
      font-style: italic;
      line-height: 1.7;
    }}
    .archetype-editorial .definition-quote-icon {{
      display: none;
    }}
    .archetype-editorial .slide-table {{
      border: none !important;
      box-shadow: none !important;
      border-top: 2px solid var(--primary-text) !important;
      border-bottom: 2px solid var(--primary-text) !important;
      border-radius: 0 !important;
    }}
    .archetype-editorial .slide-table th {{
      background: transparent !important;
      color: var(--primary-text) !important;
      border-bottom: 1px solid var(--card-border) !important;
      font-family: Georgia, serif !important;
    }}
    .archetype-editorial .task-checkbox {{
      border-radius: 2px !important;
    }}
    .archetype-editorial .split-image,
    .archetype-editorial .slide-hero-image {{
      border-radius: 0 !important;
      box-shadow: none !important;
      border: 1px solid var(--card-border) !important;
    }}

    /* 2. NEUBRUTALISM ARCHETYPE */
    .archetype-neubrutalism .info-card {{
      border: 3px solid #000000 !important;
      border-radius: 2px !important;
      box-shadow: 5px 5px 0px #000000 !important;
      background: var(--card-bg) !important;
    }}
    .archetype-neubrutalism .info-card:hover {{
      transform: translate(2px, 2px) !important;
      box-shadow: 2px 2px 0px #000000 !important;
    }}
    .archetype-neubrutalism .definition-card {{
      border: 3px solid #000000 !important;
      border-left: 12px solid #000000 !important;
      border-radius: 2px !important;
      box-shadow: 6px 6px 0px #000000 !important;
    }}
    .archetype-neubrutalism .card-index-badge {{
      border: 2px solid #000000 !important;
      border-radius: 2px !important;
      box-shadow: 2px 2px 0px #000000 !important;
      background: var(--accent) !important;
      color: #000000 !important;
      font-weight: 900 !important;
    }}
    .archetype-neubrutalism .title-pill {{
      border: 2px solid #000000 !important;
      box-shadow: 3px 3px 0px #000000 !important;
      border-radius: 2px !important;
      color: #000000 !important;
    }}
    .archetype-neubrutalism .audio-widget {{
      border: 2px solid #000000 !important;
      box-shadow: 3px 3px 0px #000000 !important;
      border-radius: 4px !important;
    }}
    .archetype-neubrutalism .nav-btn,
    .archetype-neubrutalism .slide-counter {{
      border: 2px solid #000000 !important;
      box-shadow: 2px 2px 0px #000000 !important;
      border-radius: 2px !important;
    }}
    .archetype-neubrutalism .slide-table {{
      border: 3px solid #000000 !important;
      box-shadow: 6px 6px 0px #000000 !important;
      border-radius: 2px !important;
    }}
    .archetype-neubrutalism .slide-table th {{
      border-bottom: 3px solid #000000 !important;
      color: #000000 !important;
      background: var(--accent) !important;
    }}
    .archetype-neubrutalism .slide-table td {{
      border-bottom: 2px solid #000000 !important;
    }}
    .archetype-neubrutalism .task-checkbox {{
      border: 2px solid #000000 !important;
      border-radius: 2px !important;
      box-shadow: 2px 2px 0px #000000 !important;
    }}
    .archetype-neubrutalism .split-image,
    .archetype-neubrutalism .slide-hero-image {{
      border: 3px solid #000000 !important;
      box-shadow: 6px 6px 0px #000000 !important;
      border-radius: 2px !important;
    }}

    /* 3. TERMINAL ARCHETYPE */
    .archetype-terminal {{
      font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace !important;
    }}
    .archetype-terminal .slide-main-title,
    .archetype-terminal .slide-heading,
    .archetype-terminal .card-title,
    .archetype-terminal .definition-text {{
      font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace !important;
    }}
    .archetype-terminal .slide-category::before {{
      content: "root@slides:~# ";
      color: var(--secondary-text);
      opacity: 0.7;
    }}
    .archetype-terminal .title-pill::before {{
      content: "[INIT] ";
    }}
    .archetype-terminal .title-pill {{
      border-radius: 4px !important;
      border: 1px solid var(--accent) !important;
      background: rgba(0, 0, 0, 0.4) !important;
    }}
    .archetype-terminal .info-card {{
      border: 1px solid var(--card-border) !important;
      border-radius: 4px !important;
      background: var(--card-bg) !important;
      box-shadow: 0 0 16px rgba(46, 160, 67, 0.12) !important;
    }}
    .archetype-terminal .card-title::before {{
      content: "> ";
      color: var(--accent);
      font-weight: 700;
    }}
    .archetype-terminal .card-index-badge {{
      border-radius: 3px !important;
      background: rgba(255, 255, 255, 0.06) !important;
      color: var(--accent) !important;
      border: 1px solid var(--accent) !important;
      font-family: monospace !important;
    }}
    .archetype-terminal .definition-card {{
      border: 1px dashed var(--accent) !important;
      border-left: 6px solid var(--accent) !important;
      border-radius: 4px !important;
      background: var(--card-bg) !important;
    }}
    .archetype-terminal .slide-table {{
      border: 1px solid var(--accent) !important;
      box-shadow: 0 0 16px rgba(46, 160, 67, 0.12) !important;
    }}
    .archetype-terminal .slide-table th {{
      background: rgba(46, 160, 67, 0.2) !important;
      color: var(--accent) !important;
      border-bottom: 1px solid var(--accent) !important;
    }}
    .archetype-terminal .task-checkbox {{
      border-color: var(--accent) !important;
      border-radius: 2px !important;
    }}
    .archetype-terminal .split-image,
    .archetype-terminal .slide-hero-image {{
      border: 1px solid var(--accent) !important;
      border-radius: 2px !important;
    }}

    /* 4. SWISS MINIMAL ARCHETYPE */
    .archetype-minimal .info-card {{
      background: transparent !important;
      border: none !important;
      box-shadow: none !important;
      border-radius: 0 !important;
      padding: 0 !important;
    }}
    .archetype-minimal .info-card:hover {{
      transform: none !important;
    }}
    .archetype-minimal .card-top {{
      flex-direction: column !important;
      gap: 6px !important;
      margin-bottom: 8px !important;
    }}
    .archetype-minimal .card-index-badge {{
      background: transparent !important;
      color: var(--accent) !important;
      font-size: 2.6rem !important;
      font-weight: 900 !important;
      width: auto !important;
      height: auto !important;
      line-height: 1 !important;
      margin: 0 !important;
      justify-content: flex-start !important;
      letter-spacing: -0.04em;
    }}
    .archetype-minimal .definition-card {{
      background: transparent !important;
      border: none !important;
      border-left: 4px solid var(--accent) !important;
      border-radius: 0 !important;
      box-shadow: none !important;
      padding: 16px 0 16px 28px !important;
    }}
    .archetype-minimal .title-pill {{
      background: transparent !important;
      color: var(--accent) !important;
      padding-left: 0 !important;
      font-weight: 800 !important;
    }}

    /* 5. CORPORATE ARCHETYPE */
    .archetype-corporate .info-card {{
      border-radius: 4px !important;
      border: 1px solid var(--card-border) !important;
      border-top: 5px solid var(--accent) !important;
      box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06) !important;
    }}
    .archetype-corporate .definition-card {{
      border-radius: 4px !important;
      border: 1px solid var(--card-border) !important;
      border-top: 5px solid var(--accent) !important;
      box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06) !important;
    }}
    .archetype-corporate .card-index-badge {{
      border-radius: 2px !important;
      background: var(--accent) !important;
      color: #FFFFFF !important;
    }}
    .archetype-corporate .slide-category {{
      letter-spacing: 0.12em !important;
    }}
    .archetype-corporate .title-pill {{
      border-radius: 4px !important;
    }}

    /* Print styles for pixel-perfect 16:9 PDF export */
    @media print {{
      @page {{
        size: 16in 9in;
        margin: 0;
      }}
      body {{
        background: transparent !important;
        display: block !important;
        height: auto !important;
        min-height: auto !important;
        overflow: visible !important;
      }}
      #presentation-stage {{
        display: block !important;
        width: 16in !important;
        height: auto !important;
        overflow: visible !important;
        background: transparent !important;
      }}
      #presentation-viewport {{
        position: static !important;
        width: 16in !important;
        height: auto !important;
        min-width: 0 !important;
        min-height: 0 !important;
        max-width: none !important;
        max-height: none !important;
        transform: none !important;
        box-shadow: none !important;
        overflow: visible !important;
      }}
      .slide {{
        position: relative !important;
        display: flex !important;
        opacity: 1 !important;
        width: 16in !important;
        height: 9in !important;
        page-break-after: always !important;
        break-after: page !important;
        box-sizing: border-box !important;
      }}
      #nav-footer {{
        display: none !important;
      }}
      .audio-widget {{
        display: none !important;
      }}
    }}
  </style>
</head>
<body>
  <div id="presentation-stage">
    <div id="presentation-viewport" class="archetype-{theme.archetype.value}">
      {slides_joined}

      <div id="nav-footer">
        <div class="nav-controls">
          <button id="btn-prev" class="nav-btn" type="button" title="Previous slide (Left arrow)">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
          </button>
          <button id="btn-next" class="nav-btn" type="button" title="Next slide (Right arrow / Space)">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
          </button>
        </div>
        <div class="slide-counter">
          <span id="counter-current">1</span> / <span id="counter-total">{total_slides}</span>
        </div>
      </div>
    </div>
  </div>

  <script>
    let currentSlide = 0;
    const slides = document.querySelectorAll('.slide');
    const totalSlides = slides.length;
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    const counterCurrent = document.getElementById('counter-current');

    let currentPlayingAudio = null;
    let currentPlayingWidget = null;

    function stopAllAudio() {{
      if (currentPlayingAudio) {{
        currentPlayingAudio.pause();
        currentPlayingAudio.currentTime = 0;
      }}
      if (currentPlayingWidget) {{
        currentPlayingWidget.classList.remove('audio-playing');
        const status = currentPlayingWidget.querySelector('.audio-label-status');
        if (status) status.textContent = 'Click to play';
        const icon = currentPlayingWidget.querySelector('.audio-play-btn');
        if (icon) icon.innerHTML = '<svg viewBox="0 0 24 24"><polygon points="6 3 20 12 6 21 6 3"></polygon></svg>';
      }}
      currentPlayingAudio = null;
      currentPlayingWidget = null;
    }}

    function showSlide(index) {{
      if (index < 0 || index >= totalSlides) return;
      stopAllAudio();

      slides[currentSlide].classList.remove('active');
      currentSlide = index;
      slides[currentSlide].classList.add('active');

      counterCurrent.textContent = currentSlide + 1;
      btnPrev.disabled = (currentSlide === 0);
      btnNext.disabled = (currentSlide === totalSlides - 1);
    }}

    btnPrev.addEventListener('click', (e) => {{ e.preventDefault(); showSlide(currentSlide - 1); }});
    btnNext.addEventListener('click', (e) => {{ e.preventDefault(); showSlide(currentSlide + 1); }});

    document.addEventListener('keydown', (e) => {{
      if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') {{
        e.preventDefault();
        showSlide(currentSlide + 1);
      }} else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {{
        e.preventDefault();
        showSlide(currentSlide - 1);
      }} else if (e.key === 'Home') {{
        e.preventDefault();
        showSlide(0);
      }} else if (e.key === 'End') {{
        e.preventDefault();
        showSlide(totalSlides - 1);
      }} else if (e.key.toLowerCase() === 'f') {{
        if (!document.fullscreenElement) {{
          document.documentElement.requestFullscreen();
        }} else {{
          document.exitFullscreen();
        }}
      }}
    }});

    function formatTime(seconds) {{
      if (isNaN(seconds) || seconds < 0) return '0:00';
      const m = Math.floor(seconds / 60);
      const s = Math.floor(seconds % 60);
      return m + ':' + (s < 10 ? '0' : '') + s;
    }}

    // Initialize audio widgets
    document.querySelectorAll('.audio-widget').forEach(widget => {{
      const audioId = widget.getAttribute('data-audio-id');
      const audio = document.getElementById(audioId);
      if (!audio) return;

      const playBtn = widget.querySelector('.audio-play-btn');
      const statusLabel = widget.querySelector('.audio-label-status');

      function updatePlayingUI() {{
        widget.classList.add('audio-playing');
        playBtn.innerHTML = '<svg viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>';
        const dur = formatTime(audio.duration);
        const cur = formatTime(audio.currentTime);
        statusLabel.textContent = 'Playing (' + cur + ' / ' + dur + ')';
      }}

      function updatePausedUI() {{
        widget.classList.remove('audio-playing');
        playBtn.innerHTML = '<svg viewBox="0 0 24 24"><polygon points="6 3 20 12 6 21 6 3"></polygon></svg>';
        statusLabel.textContent = 'Paused';
      }}

      audio.addEventListener('timeupdate', () => {{
        if (!audio.paused && currentPlayingAudio === audio) {{
          const dur = formatTime(audio.duration);
          const cur = formatTime(audio.currentTime);
          statusLabel.textContent = 'Playing (' + cur + ' / ' + dur + ')';
        }}
      }});

      audio.addEventListener('ended', () => {{
        widget.classList.remove('audio-playing');
        playBtn.innerHTML = '<svg viewBox="0 0 24 24"><polygon points="6 3 20 12 6 21 6 3"></polygon></svg>';
        statusLabel.textContent = 'Completed (Replay)';
        currentPlayingAudio = null;
        currentPlayingWidget = null;
      }});

      audio.addEventListener('error', (e) => {{
        const err = audio.error;
        console.error('Audio load error:', err);
        widget.classList.remove('audio-playing');
        let msg = 'Load error';
        if (err) {{
          if (err.code === 4) msg = 'Format error (codec)';
          else if (err.code === 3) msg = 'Decoding error';
          else if (err.code === 2) msg = 'Network error';
          else if (err.code === 1) msg = 'Aborted';
        }}
        statusLabel.textContent = 'Error: ' + msg;
      }});

      widget.addEventListener('click', (e) => {{
        e.preventDefault();
        e.stopPropagation();

        if (currentPlayingAudio === audio && !audio.paused) {{
          audio.pause();
          updatePausedUI();
        }} else {{
          if (currentPlayingAudio && currentPlayingAudio !== audio) {{
            stopAllAudio();
          }}
          currentPlayingAudio = audio;
          currentPlayingWidget = widget;

          audio.play().then(() => {{
            updatePlayingUI();
          }}).catch(err => {{
            console.error('Audio play rejection:', err);
            widget.classList.remove('audio-playing');
            statusLabel.textContent = 'Error: ' + (err.name || 'Playback failed');
          }});
        }}
      }});
    }});

    // Scale-to-fit virtual canvas (1600x900)
    function updateViewportScale() {{
      const viewport = document.getElementById('presentation-viewport');
      if (!viewport) return;
      const stageW = window.innerWidth;
      const stageH = window.innerHeight;
      const scale = Math.min(stageW / 1600, stageH / 900);
      viewport.style.transform = `scale(${{scale}})`;
    }}

    window.addEventListener('resize', updateViewportScale);
    window.addEventListener('orientationchange', updateViewportScale);

    // Mobile touch swipe gestures
    let touchStartX = 0;
    let touchStartY = 0;

    document.addEventListener('touchstart', (e) => {{
      if (e.touches.length === 1) {{
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
      }}
    }}, {{ passive: true }});

    document.addEventListener('touchend', (e) => {{
      if (e.changedTouches.length === 1) {{
        const diffX = e.changedTouches[0].clientX - touchStartX;
        const diffY = e.changedTouches[0].clientY - touchStartY;
        if (Math.abs(diffX) > 50 && Math.abs(diffX) > Math.abs(diffY) * 1.4) {{
          if (diffX < 0) {{
            showSlide(currentSlide + 1);
          }} else {{
            showSlide(currentSlide - 1);
          }}
        }}
      }}
    }}, {{ passive: true }});

    // Initial setup
    showSlide(0);
    updateViewportScale();
  </script>
</body>
</html>"""


def _render_table_html(table: TableData) -> str:
    ths = []
    for i, h in enumerate(table.headers):
        align = table.alignments[i] if i < len(table.alignments) else "left"
        ths.append(f'<th class="align-{align}">{render_markdown_html(h)}</th>')
    th_row = "".join(ths)

    tbody_rows = []
    for row in table.rows:
        tds = []
        for i, cell in enumerate(row):
            align = table.alignments[i] if i < len(table.alignments) else "left"
            tds.append(f'<td class="align-{align}">{render_markdown_html(cell)}</td>')
        tbody_rows.append(f'<tr>{"".join(tds)}</tr>')
    tbody = "\n        ".join(tbody_rows)

    return f"""<div class="slide-table-container">
      <table class="slide-table">
        <thead><tr>{th_row}</tr></thead>
        <tbody>
          {tbody}
        </tbody>
      </table>
    </div>"""


def _render_slide(slide: SlideData, total_slides: int, theme: ThemeConfig,
                  audio_info: Optional[Dict[str, str]] = None, deck_title: str = "",
                  image_assets: Optional[Dict[str, Dict[str, str]]] = None) -> str:
    audio_widget_html = ""
    audio_tag_html = ""

    if audio_info:
        audio_id = f"audio-slide-{slide.index}"
        audio_widget_html = f"""
        <div class="audio-widget" data-audio-id="{audio_id}" title="Play slide narration">
          <button class="audio-play-btn" type="button" aria-label="Play narration">
            <svg viewBox="0 0 24 24"><polygon points="6 3 20 12 6 21 6 3"></polygon></svg>
          </button>
          <div class="audio-label">
            <span class="audio-label-title">Narration</span>
            <span class="audio-label-status">Click to play</span>
          </div>
          <div class="audio-waves">
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
          </div>
        </div>
        """

        sources = []
        # 1. Base64 Data URI (primary - zero network/filesystem dependency, completely standalone)
        if audio_info.get("data_uri"):
            sources.append(f'<source src="{audio_info["data_uri"]}" type="{audio_info.get("mime_type", "audio/mpeg")}"></source>')
        # 2. Converted MP3 relative file
        if audio_info.get("mp3_name"):
            sources.append(f'<source src="{audio_info["mp3_name"]}" type="audio/mpeg"></source>')
        # 3. Original file
        if audio_info.get("orig_name"):
            sources.append(f'<source src="{audio_info["orig_name"]}" type="audio/mp4"></source>')

        sources_html = "\n      ".join(sources)
        audio_tag_html = f"""
        <audio id="{audio_id}" preload="auto" style="display:none;">
          {sources_html}
        </audio>
        """

    cat_label = html.escape(deck_title.upper()) if deck_title else "PREZENTÁCIÓ"
    density_cls = f"density-{slide.density_tier.value}"

    if slide.slide_type == SlideType.TITLE:
        main_title = render_markdown_html(slide.title)
        author_text = render_markdown_html(slide.author or slide.subtitle)
        pill_text = html.escape(deck_title) if deck_title else "PREZENTÁCIÓ"
        return f"""
        <div class="slide {density_cls}" id="slide-{slide.index}">
          {audio_tag_html}
          <div class="slide-title-container">
            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
              <div class="title-pill">{pill_text}</div>
              {audio_widget_html}
            </div>
            <h1 class="slide-main-title">{main_title}</h1>
            {f'<div class="slide-author">{author_text}</div>' if author_text else ''}
          </div>
        </div>
        """

    elif slide.slide_type == SlideType.DEFINITION:
        def_content = render_markdown_html(slide.quote or (slide.paragraphs[0] if slide.paragraphs else ""))
        heading_title = render_markdown_html(slide.title)
        return f"""
        <div class="slide {density_cls}" id="slide-{slide.index}">
          {audio_tag_html}
          <div class="slide-header">
            <div class="header-left">
              <span class="slide-category">{cat_label}</span>
              <h2 class="slide-heading">{heading_title}</h2>
            </div>
            {audio_widget_html}
          </div>
          <div class="slide-content">
            <div class="definition-card">
              <div class="definition-quote-icon">&ldquo;</div>
              <p class="definition-text">{def_content}</p>
            </div>
          </div>
        </div>
        """

    elif slide.slide_type == SlideType.TABLE:
        table_html = _render_table_html(slide.table) if slide.table else ""
        intro_html = ""
        if slide.paragraphs:
            intro_html = f'<p class="slide-intro">{render_markdown_html(slide.paragraphs[0])}</p>'
        heading_title = render_markdown_html(slide.title)
        return f"""
        <div class="slide {density_cls}" id="slide-{slide.index}">
          {audio_tag_html}
          <div class="slide-header">
            <div class="header-left">
              <span class="slide-category">{cat_label}</span>
              <h2 class="slide-heading">{heading_title}</h2>
            </div>
            {audio_widget_html}
          </div>
          <div class="slide-content">
            {intro_html}
            {table_html}
          </div>
        </div>
        """

    elif slide.slide_type == SlideType.IMAGE:
        heading_title = render_markdown_html(slide.title)
        img = slide.images[0] if slide.images else None
        img_src = ""
        alt_text = ""
        if img:
            alt_text = html.escape(img.alt)
            if img.resolved_path:
                path_key = str(img.resolved_path.resolve())
                if image_assets and path_key in image_assets:
                    img_src = image_assets[path_key]["data_uri"]
            if not img_src:
                img_src = img.src

        caption_html = f'<p class="image-caption">{alt_text}</p>' if alt_text else ""
        intro_html = ""
        if slide.paragraphs:
            intro_html = f'<p class="slide-intro text-center">{render_markdown_html(slide.paragraphs[0])}</p>'

        return f"""
        <div class="slide {density_cls}" id="slide-{slide.index}">
          {audio_tag_html}
          <div class="slide-header">
            <div class="header-left">
              <span class="slide-category">{cat_label}</span>
              <h2 class="slide-heading">{heading_title}</h2>
            </div>
            {audio_widget_html}
          </div>
          <div class="slide-content">
            <div class="slide-image-container">
              {intro_html}
              <img class="slide-hero-image" src="{img_src}" alt="{alt_text}" />
              {caption_html}
            </div>
          </div>
        </div>
        """

    elif slide.slide_type == SlideType.CARDS:
        cards_html = []
        for card in slide.cards:
            badge_idx = f"0{card.card_index}" if card.card_index < 10 else str(card.card_index)
            c_title = render_markdown_html(card.title)
            c_desc = render_markdown_html(card.description)
            cards_html.append(f"""
            <div class="info-card">
              <div class="card-top">
                <span class="card-index-badge">{badge_idx}</span>
                <h3 class="card-title">{c_title}</h3>
              </div>
              <p class="card-desc">{c_desc}</p>
            </div>
            """)
        cards_joined = "\n".join(cards_html)
        heading_title = render_markdown_html(slide.title)

        intro_html = ""
        footer_html = ""
        if slide.paragraphs:
            intro_html = f'<p class="slide-intro">{render_markdown_html(slide.paragraphs[0])}</p>'
            if len(slide.paragraphs) > 1:
                footer_html = f'<p class="slide-footnote">{render_markdown_html(slide.paragraphs[1])}</p>'

        return f"""
        <div class="slide {density_cls}" id="slide-{slide.index}">
          {audio_tag_html}
          <div class="slide-header">
            <div class="header-left">
              <span class="slide-category">{cat_label}</span>
              <h2 class="slide-heading">{heading_title}</h2>
            </div>
            {audio_widget_html}
          </div>
          <div class="slide-content">
            {intro_html}
            <div class="cards-grid">
              {cards_joined}
            </div>
            {footer_html}
          </div>
        </div>
        """

    elif slide.slide_type == SlideType.CODE:
        lang = (slide.code_snippet.get("language") if slide.code_snippet else "code") or "code"
        code_text = (slide.code_snippet.get("code") if slide.code_snippet else "") or ""
        heading_title = render_markdown_html(slide.title)
        return f"""
        <div class="slide {density_cls}" id="slide-{slide.index}">
          {audio_tag_html}
          <div class="slide-header">
            <div class="header-left">
              <span class="slide-category">Kódrészlet</span>
              <h2 class="slide-heading">{heading_title}</h2>
            </div>
            {audio_widget_html}
          </div>
          <div class="slide-content">
            <div class="code-block">
              <div class="code-header">
                <span class="code-lang">{html.escape(lang)}</span>
              </div>
              <pre><code>{html.escape(code_text)}</code></pre>
            </div>
          </div>
        </div>
        """

    else:
        # Standard content slide (paragraphs + lists)
        paras_html = "".join(f"<p class='slide-para'>{render_markdown_html(p)}</p>" for p in slide.paragraphs)
        lists_html = ""
        if slide.list_items:
            items_rendered = []
            has_task = any(item.startswith(("[x] ", "[ ] ")) for item in slide.list_items)
            for item in slide.list_items:
                if item.startswith(("[x] ", "[ ] ")):
                    checked = item.startswith("[x] ")
                    item_text = item[4:]
                    check_symbol = "✓" if checked else ""
                    checked_cls = "checked" if checked else ""
                    items_rendered.append(
                        f'<li class="task-item"><span class="task-checkbox {checked_cls}">{check_symbol}</span><span>{render_markdown_html(item_text)}</span></li>'
                    )
                else:
                    items_rendered.append(f"<li>{render_markdown_html(item)}</li>")
            list_class = "content-list task-list" if has_task else "content-list"
            lists_html = f"<ul class='{list_class}'>{''.join(items_rendered)}</ul>"

        heading_title = render_markdown_html(slide.title)

        if slide.images:
            img = slide.images[0]
            img_src = ""
            alt_text = html.escape(img.alt)
            if img.resolved_path:
                path_key = str(img.resolved_path.resolve())
                if image_assets and path_key in image_assets:
                    img_src = image_assets[path_key]["data_uri"]
            if not img_src:
                img_src = img.src
            caption_html = f'<p class="image-caption">{alt_text}</p>' if alt_text else ""

            body_content = f"""
            <div class="split-layout">
              <div class="split-layout-left">
                {paras_html}
                {lists_html}
              </div>
              <div class="split-layout-right">
                <img class="split-image" src="{img_src}" alt="{alt_text}" />
                {caption_html}
              </div>
            </div>
            """
        else:
            body_content = f"""
            {paras_html}
            {lists_html}
            """

        return f"""
        <div class="slide {density_cls}" id="slide-{slide.index}">
          {audio_tag_html}
          <div class="slide-header">
            <div class="header-left">
              <span class="slide-category">{cat_label}</span>
              <h2 class="slide-heading">{heading_title}</h2>
            </div>
            {audio_widget_html}
          </div>
          <div class="slide-content">
            {body_content}
          </div>
        </div>
        """
