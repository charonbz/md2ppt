# AI Theme Generator Guide & Prompt Template

To generate a new presentation theme using any AI (Antigravity chat, Claude, ChatGPT, Gemini), copy and customize the prompt template below:

---

```markdown
Create a new presentation theme for the slideshowGenerator system conforming to the following JSON schema.
Desired theme aesthetic: [Enter your description here, e.g., "Nordic minimalism with icy blue and slate gray tones" or "Természetközeli zöld és fehér kártyás stílus"].

Your response must contain ONLY a single valid JSON code block conforming to this schema:

{
  "id": "unique_theme_id_snake_case",
  "name": "Human-Readable Name",
  "description": "Short description of the theme aesthetic",
  "colors": {
    "background": "#HEX background color",
    "card_bg": "#HEX card background",
    "card_border": "#HEX card border",
    "primary_text": "#HEX primary text color (high contrast against card_bg)",
    "secondary_text": "#HEX secondary text color",
    "accent": "#HEX accent color (buttons, badges, highlights)",
    "accent_light": "#HEX soft/light accent color",
    "badge_bg": "#HEX category badge background",
    "badge_text": "#HEX category badge text color",
    "audio_btn_bg": "#HEX audio player button background",
    "audio_btn_text": "#HEX audio player button icon color"
  },
  "fonts": {
    "title_font": "Font family for headings (e.g. system-ui, Georgia, Montserrat)",
    "body_font": "Font family for body text (e.g. system-ui, Roboto, Open Sans)"
  },
  "styles": {
    "card_radius_px": 16,
    "card_shadow": "0 10px 25px -5px rgba(0, 0, 0, 0.08)",
    "title_align": "left",
    "border_width_px": 1
  }
}
```

Save the generated JSON file as `generator/themes/<id>.json`. The generator will immediately detect it and allow usage via `--theme <id>`.
