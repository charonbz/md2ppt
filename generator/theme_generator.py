import json
import os
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional

THEMES_DIR = Path(__file__).parent / "themes"

SYSTEM_PROMPT = """You are a graphic and presentation designer.
Generate a valid JSON theme configuration for a slideshow presentation based on the user's description.
Output ONLY a raw JSON object conforming to this schema without any markdown blocks or explanations:
{
  "id": "short_theme_id",
  "name": "Human Readable Name",
  "description": "Short description of the theme aesthetic",
  "archetype": "cards",
  "colors": {
    "background": "#HEX",
    "card_bg": "#HEX",
    "card_border": "#HEX",
    "primary_text": "#HEX",
    "secondary_text": "#HEX",
    "accent": "#HEX",
    "accent_light": "#HEX",
    "badge_bg": "#HEX",
    "badge_text": "#HEX",
    "audio_btn_bg": "#HEX",
    "audio_btn_text": "#HEX"
  },
  "fonts": {
    "title_font": "Font family name",
    "body_font": "Font family name"
  },
  "styles": {
    "card_radius_px": 16,
    "card_shadow": "0 10px 25px -5px rgba(0, 0, 0, 0.1)",
    "title_align": "left",
    "border_width_px": 1
  }
}
"""

def generate_ai_theme(description: str, output_id: Optional[str] = None) -> Path:
    """Generate a new theme JSON using AI (Gemini API if key exists) or algorithmic designer fallback."""
    api_key = os.environ.get("GEMINI_API_KEY")
    theme_data = None

    if api_key:
        theme_data = _call_gemini_api(description, api_key)

    if not theme_data:
        theme_data = _synthesize_theme_algorithmically(description, output_id)

    theme_id = output_id or theme_data.get("id") or _slugify(description[:20])
    theme_data["id"] = theme_id
    theme_data.setdefault("archetype", "cards")

    THEMES_DIR.mkdir(parents=True, exist_ok=True)
    out_file = THEMES_DIR / f"{theme_id}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(theme_data, f, indent=2, ensure_ascii=False)

    return out_file


def _call_gemini_api(description: str, api_key: str) -> Optional[Dict[str, Any]]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [
                {"text": SYSTEM_PROMPT},
                {"text": f"User theme description: {description}"}
            ]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw_text)
    except Exception as e:
        print(f"[AI Theme Generator] Gemini API call skipped/failed ({e}), using algorithmic synthesizer.")
        return None


def _synthesize_theme_algorithmically(description: str, custom_id: Optional[str]) -> Dict[str, Any]:
    """Generates an aesthetically pleasing color palette based on keyword analysis."""
    desc_lower = description.lower()
    theme_id = custom_id or _slugify(description[:25])
    
    # Defaults: modern dark vs light
    is_dark = any(w in desc_lower for w in ["dark", "sötét", "fekete", "black", "night", "cyber", "neon"])
    
    if "cyber" in desc_lower or "neon" in desc_lower:
        return {
            "id": theme_id,
            "name": f"Cyber Neon ({description[:30]})",
            "description": f"AI által generált cyberpunk neon stílus: {description}",
            "colors": {
                "background": "#0B0F19",
                "card_bg": "#111827",
                "card_border": "#06B6D4",
                "primary_text": "#F9FAFB",
                "secondary_text": "#9CA3AF",
                "accent": "#06B6D4",
                "accent_light": "#164E63",
                "badge_bg": "#1E1B4B",
                "badge_text": "#A5B4FC",
                "audio_btn_bg": "#EC4899",
                "audio_btn_text": "#FFFFFF"
            },
            "fonts": {
                "title_font": "'Courier New', monospace, sans-serif",
                "body_font": "system-ui, sans-serif"
            },
            "styles": {
                "card_radius_px": 12,
                "card_shadow": "0 0 20px rgba(6, 182, 212, 0.2)",
                "title_align": "left",
                "border_width_px": 2
            }
        }
    elif any(w in desc_lower for w in ["zöld", "green", "természet", "nature", "forest", "bio"]):
        return {
            "id": theme_id,
            "name": f"Organic Forest ({description[:30]})",
            "description": f"AI által generált természetközeli zöld stílus: {description}",
            "colors": {
                "background": "#F2FBF5" if not is_dark else "#062315",
                "card_bg": "#FFFFFF" if not is_dark else "#0B3822",
                "card_border": "#A7F3D0" if not is_dark else "#10B981",
                "primary_text": "#064E3B" if not is_dark else "#ECFDF5",
                "secondary_text": "#047857" if not is_dark else "#A7F3D0",
                "accent": "#059669",
                "accent_light": "#D1FAE5" if not is_dark else "#047857",
                "badge_bg": "#ECFDF5",
                "badge_text": "#065F46",
                "audio_btn_bg": "#059669",
                "audio_btn_text": "#FFFFFF"
            },
            "fonts": {
                "title_font": "system-ui, -apple-system, sans-serif",
                "body_font": "system-ui, -apple-system, sans-serif"
            },
            "styles": {
                "card_radius_px": 16,
                "card_shadow": "0 8px 24px -4px rgba(5, 150, 105, 0.12)",
                "title_align": "left",
                "border_width_px": 1
            }
        }
    elif any(w in desc_lower for w in ["nordic", "skandináv", "minimal", "jeges", "ice", "frost"]):
        return {
            "id": theme_id,
            "name": f"Nordic Ice ({description[:30]})",
            "description": f"AI által generált skandináv minimalista stílus: {description}",
            "colors": {
                "background": "#F0F4F8",
                "card_bg": "#FFFFFF",
                "card_border": "#CBD5E1",
                "primary_text": "#1E293B",
                "secondary_text": "#475569",
                "accent": "#0284C7",
                "accent_light": "#E0F2FE",
                "badge_bg": "#E2E8F0",
                "badge_text": "#0F172A",
                "audio_btn_bg": "#0284C7",
                "audio_btn_text": "#FFFFFF"
            },
            "fonts": {
                "title_font": "system-ui, -apple-system, sans-serif",
                "body_font": "system-ui, -apple-system, sans-serif"
            },
            "styles": {
                "card_radius_px": 14,
                "card_shadow": "0 6px 18px rgba(30, 41, 59, 0.05)",
                "title_align": "left",
                "border_width_px": 1
            }
        }
    elif is_dark:
        return {
            "id": theme_id,
            "name": f"Deep Slate ({description[:30]})",
            "description": f"AI által generált sötét elegáns stílus: {description}",
            "colors": {
                "background": "#090D16",
                "card_bg": "#151B2B",
                "card_border": "#28344E",
                "primary_text": "#F1F5F9",
                "secondary_text": "#94A3B8",
                "accent": "#38BDF8",
                "accent_light": "#0C4A6E",
                "badge_bg": "#1E293B",
                "badge_text": "#7DD3FC",
                "audio_btn_bg": "#38BDF8",
                "audio_btn_text": "#090D16"
            },
            "fonts": {
                "title_font": "system-ui, -apple-system, sans-serif",
                "body_font": "system-ui, -apple-system, sans-serif"
            },
            "styles": {
                "card_radius_px": 16,
                "card_shadow": "0 10px 25px rgba(0, 0, 0, 0.5)",
                "title_align": "left",
                "border_width_px": 1
            }
        }
    else:
        return {
            "id": theme_id,
            "name": f"Custom Palette ({description[:30]})",
            "description": f"AI által generált egyedi stílus: {description}",
            "colors": {
                "background": "#FAF5FF",
                "card_bg": "#FFFFFF",
                "card_border": "#E9D5FF",
                "primary_text": "#3B0764",
                "secondary_text": "#6B21A8",
                "accent": "#9333EA",
                "accent_light": "#F3E8FF",
                "badge_bg": "#F3E8FF",
                "badge_text": "#581C87",
                "audio_btn_bg": "#9333EA",
                "audio_btn_text": "#FFFFFF"
            },
            "fonts": {
                "title_font": "system-ui, -apple-system, sans-serif",
                "body_font": "system-ui, -apple-system, sans-serif"
            },
            "styles": {
                "card_radius_px": 16,
                "card_shadow": "0 10px 25px rgba(147, 51, 234, 0.08)",
                "title_align": "left",
                "border_width_px": 1
            }
        }


def _slugify(text: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "_", s)
    return s.strip("_") or "custom_theme"
