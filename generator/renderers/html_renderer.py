import base64
import html
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from ..models import PresentationData, SlideData, SlideType, ThemeConfig
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

    html_content = _build_html(pres, theme, audio_assets)
    html_file.write_text(html_content, encoding="utf-8")
    return html_file


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


def _build_html(pres: PresentationData, theme: ThemeConfig, audio_assets: Dict[int, Dict[str, str]]) -> str:
    slides_html = []
    total_slides = len(pres.slides)

    for slide in pres.slides:
        audio_info = audio_assets.get(slide.index)
        slides_html.append(_render_slide(slide, total_slides, theme, audio_info, deck_title=pres.title))

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
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      overflow: hidden;
      user-select: none;
    }}

    #presentation-viewport {{
      position: relative;
      width: min(100vw, calc(100vh * 16 / 9));
      height: min(100vh, calc(100vw * 9 / 16));
      background-color: var(--bg-color);
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
      overflow: hidden;
    }}

    .slide {{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      display: none;
      flex-direction: column;
      padding: 5% 6%;
      background-color: var(--bg-color);
      opacity: 0;
      transition: opacity 0.25s ease-in-out;
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
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 0.95rem;
      font-weight: 600;
      margin-bottom: 24px;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }}

    .slide-main-title {{
      font-family: var(--title-font);
      font-size: clamp(2.2rem, 4.5vw, 3.8rem);
      font-weight: 800;
      line-height: 1.15;
      color: var(--primary-text);
      margin-bottom: 24px;
    }}

    .slide-author {{
      font-size: clamp(1.2rem, 2vw, 1.6rem);
      font-weight: 500;
      color: var(--secondary-text);
      display: flex;
      align-items: center;
      gap: 12px;
    }}

    .slide-author::before {{
      content: "";
      display: inline-block;
      width: 32px;
      height: 4px;
      background: var(--accent);
      border-radius: 2px;
    }}

    /* Header for Content Slides */
    .slide-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 4%;
    }}

    .header-left {{
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}

    .slide-category {{
      font-size: 0.85rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--accent);
    }}

    .slide-heading {{
      font-family: var(--title-font);
      font-size: clamp(1.8rem, 3vw, 2.5rem);
      font-weight: 700;
      line-height: 1.2;
      color: var(--primary-text);
    }}

    .slide-content {{
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: center;
    }}

    /* Definition Card Layout */
    .definition-card {{
      background: var(--card-bg);
      border: var(--border-width) solid var(--card-border);
      border-left: 8px solid var(--accent);
      border-radius: var(--card-radius);
      box-shadow: var(--card-shadow);
      padding: clamp(24px, 4vw, 48px);
      position: relative;
    }}

    .definition-quote-icon {{
      position: absolute;
      top: 20px;
      right: 28px;
      font-size: 3rem;
      line-height: 1;
      color: var(--accent-light);
      font-family: serif;
      pointer-events: none;
    }}

    .definition-text {{
      font-size: clamp(1.1rem, 1.8vw, 1.45rem);
      line-height: 1.6;
      color: var(--primary-text);
      font-weight: 450;
    }}

    /* Multi-Card Grid Layout */
    .cards-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: clamp(16px, 2.5vw, 32px);
      height: 100%;
    }}

    .info-card {{
      background: var(--card-bg);
      border: var(--border-width) solid var(--card-border);
      border-radius: var(--card-radius);
      box-shadow: var(--card-shadow);
      padding: clamp(20px, 3vw, 36px);
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
      gap: 14px;
      margin-bottom: 14px;
    }}

    .card-index-badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      border-radius: 8px;
      background: var(--badge-bg);
      color: var(--badge-text);
      font-size: 0.85rem;
      font-weight: 700;
      flex-shrink: 0;
      margin-top: 3px;
    }}

    .card-title {{
      font-family: var(--title-font);
      font-size: clamp(1.15rem, 1.7vw, 1.45rem);
      font-weight: 700;
      color: var(--primary-text);
      line-height: 1.25;
    }}

    .card-desc {{
      font-size: clamp(0.95rem, 1.35vw, 1.15rem);
      line-height: 1.55;
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

    /* Standard Lists */
    .content-list {{
      list-style-type: none;
      display: flex;
      flex-direction: column;
      gap: 14px;
      margin-top: 14px;
    }}

    .content-list li {{
      position: relative;
      padding-left: 28px;
      font-size: clamp(1.05rem, 1.6vw, 1.35rem);
      line-height: 1.5;
      color: var(--primary-text);
    }}

    .content-list li::before {{
      content: "";
      position: absolute;
      left: 6px;
      top: 10px;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent);
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
      padding: 8px 18px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }}

    .code-lang {{
      font-size: 0.8rem;
      text-transform: uppercase;
      font-weight: 700;
      letter-spacing: 0.08em;
      color: var(--accent);
      font-family: monospace;
    }}

    .code-block pre {{
      background: transparent;
      padding: 20px 24px;
      color: #E6EDF3;
      font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
      font-size: clamp(0.95rem, 1.4vw, 1.2rem);
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
      padding: 6px 16px 6px 8px;
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
      width: 38px;
      height: 38px;
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
      width: 18px;
      height: 18px;
      fill: currentColor;
    }}

    .audio-label {{
      display: flex;
      flex-direction: column;
      gap: 2px;
    }}

    .audio-label-title {{
      font-size: 0.82rem;
      font-weight: 600;
      color: var(--primary-text);
    }}

    .audio-label-status {{
      font-size: 0.72rem;
      color: var(--secondary-text);
    }}

    .audio-waves {{
      display: flex;
      align-items: center;
      gap: 3px;
      height: 14px;
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
      bottom: 24px;
      left: 6%;
      right: 6%;
      display: flex;
      justify-content: space-between;
      align-items: center;
      pointer-events: none;
    }}

    .nav-controls {{
      display: flex;
      gap: 8px;
      pointer-events: auto;
    }}

    .nav-btn {{
      background: var(--card-bg);
      border: var(--border-width) solid var(--card-border);
      color: var(--primary-text);
      width: 40px;
      height: 40px;
      border-radius: 10px;
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
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 0.85rem;
      font-weight: 600;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
      pointer-events: auto;
    }}

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
      font-size: clamp(1.2rem, 2vw, 1.6rem);
      line-height: 1.8;
    }}
    .archetype-editorial .definition-quote-icon {{
      display: none;
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
      #presentation-viewport {{
        width: 16in !important;
        height: auto !important;
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

    // Initial setup
    showSlide(0);
  </script>
</body>
</html>"""


def _render_slide(slide: SlideData, total_slides: int, theme: ThemeConfig, audio_info: Optional[Dict[str, str]] = None, deck_title: str = "") -> str:
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

    if slide.slide_type == SlideType.TITLE:
        main_title = render_markdown_html(slide.title)
        author_text = render_markdown_html(slide.author or slide.subtitle)
        pill_text = html.escape(deck_title) if deck_title else "PREZENTÁCIÓ"
        return f"""
        <div class="slide" id="slide-{slide.index}">
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
        <div class="slide" id="slide-{slide.index}">
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
            intro_html = f'<p class="slide-intro" style="margin-bottom: 20px; font-size: clamp(1.05rem, 1.5vw, 1.25rem); color: var(--secondary-text); line-height: 1.5;">{render_markdown_html(slide.paragraphs[0])}</p>'
            if len(slide.paragraphs) > 1:
                footer_html = f'<p class="slide-footnote" style="margin-top: 18px; font-size: clamp(0.95rem, 1.2vw, 1.05rem); color: var(--secondary-text); font-style: italic;">{render_markdown_html(slide.paragraphs[1])}</p>'

        return f"""
        <div class="slide" id="slide-{slide.index}">
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
        <div class="slide" id="slide-{slide.index}">
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
        paras_html = "".join(f"<p style='margin-bottom:16px; font-size:clamp(1.1rem, 1.6vw, 1.35rem); line-height:1.6;'>{render_markdown_html(p)}</p>" for p in slide.paragraphs)
        lists_html = ""
        if slide.list_items:
            items_str = "".join(f"<li>{render_markdown_html(item)}</li>" for item in slide.list_items)
            lists_html = f"<ul class='content-list'>{items_str}</ul>"

        heading_title = render_markdown_html(slide.title)
        return f"""
        <div class="slide" id="slide-{slide.index}">
          {audio_tag_html}
          <div class="slide-header">
            <div class="header-left">
              <span class="slide-category">{cat_label}</span>
              <h2 class="slide-heading">{heading_title}</h2>
            </div>
            {audio_widget_html}
          </div>
          <div class="slide-content">
            {paras_html}
            {lists_html}
          </div>
        </div>
        """
