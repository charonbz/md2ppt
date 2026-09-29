import json
from pathlib import Path
from typing import Dict, List, Optional
from .models import ThemeConfig

THEMES_DIR = Path(__file__).parent / "themes"

DEFAULT_THEME_ID = "modern_clean"


def list_available_themes() -> List[Dict[str, str]]:
    themes = []
    if not THEMES_DIR.exists():
        return themes

    for json_file in sorted(THEMES_DIR.glob("*.json")):
        if json_file.name == "schema.json":
            continue
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                themes.append({
                    "id": data.get("id", json_file.stem),
                    "name": data.get("name", json_file.stem),
                    "description": data.get("description", "")
                })
        except Exception:
            continue
    return themes


def load_theme(theme_id: str) -> ThemeConfig:
    theme_file = THEMES_DIR / f"{theme_id}.json"
    if not theme_file.exists():
        # Fallback to default
        fallback_file = THEMES_DIR / f"{DEFAULT_THEME_ID}.json"
        if fallback_file.exists():
            theme_file = fallback_file
        else:
            raise FileNotFoundError(f"Theme '{theme_id}' not found and default theme missing.")

    with open(theme_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Defaults
    colors = {
        "background": "#F8FAFC",
        "card_bg": "#FFFFFF",
        "card_border": "#E2E8F0",
        "primary_text": "#0F172A",
        "secondary_text": "#475569",
        "accent": "#2563EB",
        "accent_light": "#EFF6FF",
        "badge_bg": "#DBEAFE",
        "badge_text": "#1E40AF",
        "audio_btn_bg": "#2563EB",
        "audio_btn_text": "#FFFFFF",
        **data.get("colors", {})
    }

    fonts = {
        "title_font": "system-ui, -apple-system, sans-serif",
        "body_font": "system-ui, -apple-system, sans-serif",
        **data.get("fonts", {})
    }

    styles = {
        "card_radius_px": 16,
        "card_shadow": "0 10px 25px -5px rgba(0, 0, 0, 0.05)",
        "title_align": "left",
        "border_width_px": 1,
        **data.get("styles", {})
    }

    return ThemeConfig(
        id=data.get("id", theme_file.stem),
        name=data.get("name", theme_file.stem.replace("_", " ").title()),
        description=data.get("description", ""),
        colors=colors,
        fonts=fonts,
        styles=styles
    )
