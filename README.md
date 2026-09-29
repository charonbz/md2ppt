# Slideshow Generator 🎬🎙️

A presentation generation platform that transforms Markdown outlines and attached audio recordings into presentations across three first-class formats:
1. **PowerPoint (.pptx)**: 16:9 widescreen presentation with native embedded media objects (click-to-play narration).
2. **Interactive Web Presentation (.html)**: Zero-dependency, responsive HTML5 player with card-based layouts, keyboard navigation, and embedded Base64 audio with real-time playback tracking.
3. **Vector PDF (.pdf)**: Pixel-perfect, 16:9 widescreen printable and presentable vector PDF.

---

## 🚀 Quickstart

The generator automatically manages its Python virtual environment (`.venv`), so it can be executed directly:

```bash
# Generate slideshow_1 using the default (modern_clean) theme:
./run.py slideshow_1

# Generate using an alternative theme:
./run.py slideshow_1 --theme dark_mode

# Generate only specific formats (e.g., PPTX and PDF only):
./run.py slideshow_1 --format pptx,pdf

# View the generated presentation with the built-in web server:
./run.py slideshow_1 --serve 8080
```

The output artifacts are written to the `dist/` subfolder inside the slideshow directory:
* `slideshow_1/dist/presentation.pptx`
* `slideshow_1/dist/index.html`
* `slideshow_1/dist/presentation.pdf`
* `slideshow_1/dist/slide_title.m4a` & `slide_title.mp3`

---

## 📝 Slide Markdown Format (`slides.md`)

Slides are separated by `# Title`, `# Slide`, or `---` horizontal rules. Audio tracks are associated using HTML comments:

```markdown
# Title
<!-- audio: slide_title.m4a -->
A pisa meres eredmenyenek ertekelese.

Boncz Zoltan

# Slide
A PISA-vizsgálat értelmezésében a matematikai műveltség...

# Slide
A mérés a matematikai ismereteket négy átfogó kategóriába csoportosítja:

- Mennyiség (Quantity): számolás, mértékegységek, arányok...
- Változás és összefüggések (Change and relationships): függvények, modellezés...
```

* **Title Slide**: Automatically detects title, subtitle, and author.
* **Definition Slide**: Formats continuous descriptive text as an elegant, highlighted definition card.
* **Card Slide**: Formats `- Title: Description` bullets into modern cards with numbered badges (`01`, `02`, `03`, `04`).
* **Multilingual Content**: Slides can be written in Hungarian or any other language with full UTF-8 support.

---

## 🎨 Modular Themes & AI Theme Generation

Presentation styling is decoupled from content. Themes are stored as declarative JSON files in `generator/themes/`.

### List Available Themes:
```bash
./run.py --list-themes
```

Built-in themes:
- `modern_clean`: Crisp light card layout with blue accents (default)
- `dark_mode`: Premium slate dark background with indigo accents
- `emerald_growth`: Natural, fresh emerald green theme
- `warm_academic`: Classic cream and burgundy editorial style

### Generate a New Theme with AI:
Create a new theme via natural language prompt (in English or Hungarian):
```bash
./run.py --ai-theme "Cyberpunk neon dark theme with purple and cyan"
```
The generator creates the theme in `generator/themes/`, ready for immediate use:
```bash
./run.py slideshow_1 --theme cyberpunk_neon_dark_theme
```

To create themes with external LLMs (Claude, ChatGPT), see [`generator/themes/THEME_PROMPT.md`](generator/themes/THEME_PROMPT.md).

---

## ⌨️ Web Slideshow Controls

When viewing `dist/index.html`:
* **Next Slide**: `Right Arrow` (`→`), `Spacebar`, or `PageDown`
* **Previous Slide**: `Left Arrow` (`←`) or `PageUp`
* **First / Last Slide**: `Home` / `End`
* **Fullscreen**: `F` key
* **Audio Playback**: Click the **Narration** button in the slide header to play or pause.
