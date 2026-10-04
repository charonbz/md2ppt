import json
from pathlib import Path
from typing import Dict, List, Optional
from .models import ThemeConfig, ArchetypeType, BulletStyle

THEMES_DIR = Path(__file__).parent / "themes"

DEFAULT_THEME_ID = "modern_clean"

ARCHETYPES_INFO: Dict[str, Dict[str, str]] = {
    "editorial": {
        "name": "Editorial (Academic / Literary)",
        "description": "Refined serif typography, transparent cards with divider rules, no heavy boxes.",
        "best_for": "Academic papers, literary topics, essays, research presentations."
    },
    "cards": {
        "name": "Modern Cards (Elevated Floating UI)",
        "description": "Soft rounded corners, subtle ambient drop shadows, clean borders, modern SaaS aesthetic.",
        "best_for": "General business presentations, product overviews, modern summaries."
    },
    "neubrutalism": {
        "name": "Neubrutalism (Bold Pop & Hard Shadows)",
        "description": "Thick solid black borders, hard unblurred drop-shadows, geometric high contrast.",
        "best_for": "Design agencies, tech startups, creative pitches, bold workshops."
    },
    "terminal": {
        "name": "Terminal (Developer Console / Dark Grid)",
        "description": "Monospace typography, dark surface, console prompt prefixes, sharp corners.",
        "best_for": "Software engineering, DevOps, infrastructure, cybersecurity, technical talks."
    },
    "minimal": {
        "name": "Swiss Minimal (Pure Typographic Hierarchy)",
        "description": "Zero borders, zero shadows, oversized numeric indices (01, 02), maximum whitespace.",
        "best_for": "High-end design, architecture, minimal executive briefings, clean statistics."
    },
    "corporate": {
        "name": "Corporate (Executive Consulting / Top Banners)",
        "description": "Crisp geometric layout, solid color top header banner on cards, structured business look.",
        "best_for": "Corporate consulting (McKinsey/BCG style), executive reviews, quarterly reports."
    }
}


def list_available_archetypes() -> List[Dict[str, str]]:
    """Return all supported visual archetypes with descriptions and target aesthetics."""
    return [
        {
            "id": arch_id,
            "name": info["name"],
            "description": info["description"],
            "best_for": info["best_for"]
        }
        for arch_id, info in ARCHETYPES_INFO.items()
    ]


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
                    "archetype": data.get("archetype", "cards"),
                    "description": data.get("description", "")
                })
        except Exception:
            continue
    return themes


def load_theme(
    theme_id: str,
    archetype_override: Optional[str] = None,
    bullet_style_override: Optional[str] = None
) -> ThemeConfig:
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

    # Determine archetype
    selected_archetype_str = archetype_override or data.get("archetype", "cards")
    try:
        archetype_enum = ArchetypeType(selected_archetype_str.lower().strip())
    except ValueError:
        valid_archs = ", ".join(ARCHETYPES_INFO.keys())
        raise ValueError(
            f"Unknown archetype '{selected_archetype_str}'. Available archetypes: {valid_archs}"
        )

    # Determine bullet style (chevron, editorial, refined)
    selected_bullet_str = bullet_style_override or data.get("bullet_style") or "chevron"
    try:
        bullet_style_enum = BulletStyle(selected_bullet_str.lower().strip())
    except ValueError:
        valid_bullets = ", ".join([b.value for b in BulletStyle])
        raise ValueError(
            f"Unknown bullet style '{selected_bullet_str}'. Available bullet styles: {valid_bullets}"
        )

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

    # Archetype-influenced default fonts if not explicitly overridden
    default_title_font = "system-ui, -apple-system, sans-serif"
    default_body_font = "system-ui, -apple-system, sans-serif"

    if archetype_enum == ArchetypeType.EDITORIAL:
        default_title_font = "Georgia, 'Times New Roman', serif"
        default_body_font = "Charter, Georgia, 'Times New Roman', serif"
    elif archetype_enum == ArchetypeType.TERMINAL:
        default_title_font = "'JetBrains Mono', 'Fira Code', 'Courier New', monospace"
        default_body_font = "'JetBrains Mono', 'Fira Code', 'Courier New', monospace"
    elif archetype_enum == ArchetypeType.NEUBRUTALISM:
        default_title_font = "Impact, 'Arial Black', -apple-system, sans-serif"

    fonts = {
        "title_font": default_title_font,
        "body_font": default_body_font,
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
        styles=styles,
        archetype=archetype_enum,
        bullet_style=bullet_style_enum
    )
