# Slideshow Generator 🎬🎙️

A presentation generation platform that transforms Markdown outlines and attached audio recordings into presentations across three first-class formats:
1. **PowerPoint (.pptx)**: 16:9 widescreen presentation with native embedded media objects (click-to-play narration) and adaptive typography.
2. **Interactive Web Presentation (.html)**: Zero-dependency, mobile-responsive HTML5 player with a virtual canvas scale-to-fit (guaranteed 100% visible on any screen with zero clipping), mobile touch swipe gestures, keyboard navigation, and embedded Base64 audio.
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

# View the presentation with the built-in server (auto-rebuilds on edits to slides.md):
./run.py slideshow_1 --serve 8080

# Or watch and auto-rebuild in the background without launching a web server:
./run.py slideshow_1 --watch
```

The output artifacts are written to the `dist/` subfolder inside the slideshow directory:
* `slideshow_1/dist/presentation.pptx`
* `slideshow_1/dist/index.html`
* `slideshow_1/dist/presentation.pdf`
* `slideshow_1/dist/slide_title.m4a` & `slide_title.mp3`

---

## 📝 Slide Markdown Format & Element Mapping (`slides.md`)

The generator translates standard Markdown text into visually rich presentation layouts across Web (`index.html`), PowerPoint (`presentation.pptx`), and PDF (`presentation.pdf`).

### 🗺️ Markdown-to-Slide Element Mapping

| Markdown Syntax | AST Element | Slide Layout / Component | Notes & Styling |
|---|---|---|---|
| `---` or `# Slide` or `# ` (H1) | Slide boundary | **Slide Transition** | Delimits slides. Delimiter mode automatically avoids phantom slides. |
| `# Title` (Slide 1) | `SlideType.TITLE` | **Title Slide** | Displays main deck title, presenter pill, and author credit. |
| `# Header` or `## Header` or `**Title**` | `slide.title` | **Slide Header** | Cleaned of asterisks/hashes. Styled with theme title font and accent colors. |
| `### Card Title`<br/>`Description` | `CardItem` | **Info Card Box** | Floating card with sequential numeric index badge (`01`, `02`). |
| `Term:`<br/>`: Definition line 1`<br/>`: Definition line 2` | `CardItem` | **Definition Card Box** | Standard Markdown definition list rendered into visual cards. |
| `- Term:`<br/>`  **Prop**: Value` | `CardItem` | **Property Card Box** | Indented multi-line bullets converted into card containers. |
| `- Title: Description`<br/>`Title: Description` | `CardItem` | **Key-Value Card Box** | Single-line colon syntax parsed into structured cards. |
| `| Col 1 | Col 2 |`<br/>`| :--- | :---: |` | `TableData` | **Table Slide** (`SlideType.TABLE`) | Formatted table with text alignments (left/center/right) across HTML, PPTX, and PDF. |
| `![Alt Text](path.png)` | `ImageData` | **Hero Image / Split Layout** | Standalone hero slide (`SlideType.IMAGE`) or split side-by-side layout alongside text. |
| `- [x] Done`<br/>`- [ ] Pending` | Task list token | **Task List** | Custom styled checkboxes (HTML) and checkmark bullets `☑` / `☐` (PPTX). |
| `> Quote or definition` | `slide.quote` | **Definition Slide** | Large decorative quotation card (`“`) with accent left border. |
| ```` ```python ````<br/>`def code():...`<br/>```` ``` ```` | `slide.code_snippet` | **Code Block Slide** | Dark IDE container with monospace code font and language badge. |
| `- Item`<br/>`* Item`<br/>`1. Item` | `slide.list_items` | **Styled Content List** | Clean bullet list with colored circular bullet points. |
| Leading / trailing paragraphs | `slide.paragraphs` | **Intro / Footnote Text** | Lead subtitle above cards or italicized note below cards. |
| `Készítette: Név`<br/>`Author: Name` | `slide.author` | **Author Line** | Presenter credit with left decorative accent bar. |
| `**bold**` or `__bold__` | Bold token | **Bold Text** | `<strong>` in HTML; native `run.font.bold` in PowerPoint. |
| `*italic*` or `_italic_` | Italic token | **Italic Text** | `<em>` in HTML; native `run.font.italic` in PowerPoint. |
| `~~strikethrough~~` | Strike token | **Strikethrough** | `<del>` in HTML; native OpenXML `sngStrike` in PowerPoint. |
| `==highlight==` | Highlight token | **Highlighted Text** | `<mark>` in HTML; native DrawingML `<a:highlight>` in PowerPoint. |
| `^superscript^` | Sup token | **Superscript** | `<sup>` in HTML; native `30000` baseline shift in PowerPoint. |
| `~subscript~` | Sub token | **Subscript** | `<sub>` in HTML; native `-25000` baseline shift in PowerPoint. |
| `` `code` `` | Code chip | **Inline Code Pill** | Rounded chip in HTML; Consolas monospace run in PowerPoint. |
| `[link](url)` or raw `https://...` | Link token | **Clickable Link** | `<a href>` in HTML; labeled hyperlink in PowerPoint. |
| `<!-- audio: file.m4a -->` | `slide.audio_filename` | **Audio Widget** | Base64 standalone player in HTML; native audio shape in PPTX. |
| `<!-- notes: ... -->` | `slide.notes` | **Speaker Notes** | Presenter notes available during delivery. |
| `<!-- type: ... -->` | `slide.slide_type` | **Layout Override** | Explicitly forces `title`, `cards`, `definition`, `code`, `table`, `image`, or `standard`. |

---

### 💡 Slide Structure Examples

#### 1. Title Slide (`SlideType.TITLE`)
The first slide automatically formats as the title cover deck.
```markdown
# Title
<!-- audio: intro.m4a -->
A keringési rendszer

Készítette: Jámbor Dorián
```

#### 2. Visual Cards Slide (`SlideType.CARDS`)
Multiple syntax styles naturally map to cards with sequential numbering badges (`01`, `02`):
```markdown
---
## A vér alkotórészei

Egy felnőtt emberben átlagosan 5 liter vér kering:

- Vörösvérsejtek:
  **Feladata**: Légzési gázok és tápanyagok szállítása
  **Mennyiségük**: 1 mm³ kb. 4-5 millió
- Fehérvérsejtek:
  **Feladata**: Kórokozók elpusztítása
  **Számuk**: 1 mm³ kb. 6-8 ezer
```

*Alternatively, using Definition Lists:*
```markdown
---
## A vér alakos elemei

Vérlemezek:
: Feladata: Sebek képződése
: Számuk: 1 mm3 kb 150-350 ezer

Vérplazma:
: Feladata: Tápanyagokat és hormonokat szállít
: Átlátszó, vizet és fehérjéket tartalmaz
```

#### 3. Highlighted Definition / Quote Slide (`SlideType.DEFINITION`)
Blockquotes create an elegant quote card:
```markdown
---
## A Tudás Alapjai

> A tudás nem más, mint a valóság **pontos és strukturált** megértése, amely a tapasztalatokból és a folyamatos *kísérletezésből* táplálkozik.
```

#### 4. Fenced Code Slide (`SlideType.CODE`)
Code blocks render as dark IDE syntax blocks with language badge:
````markdown
---
## Algoritmus Példa

```python
def generate_slides(markdown_path: str) -> None:
    deck = parse_slides_file(markdown_path)
    render_tri_format(deck)
```
````

#### 5. Markdown Tables Slide (`SlideType.TABLE`)
Markdown tables with header rows, column alignment (`:---`, `:---:`, `---:`), and zebra striping:
```markdown
---
## Formátum-összehasonlítás

| Formátum | Motor / Technológia | Hangkíséret | Függőségmentes |
| :--- | :---: | :---: | ---: |
| HTML5 Player | Natív ES6 + Web Audio | Base64 MP3 | 100% Önálló |
| PowerPoint (.pptx) | OpenXML / python-pptx | Beágyazott média | Szerkeszthető |
| Vektoros PDF | Headless Chromium (16:9) | Nem releváns | Nyomtatható |
```

#### 6. Image Slides (Hero & Split-Screen) (`SlideType.IMAGE` / `SlideType.STANDARD`)
Images are automatically embedded as Base64 data URIs in HTML and scaled natively in PowerPoint preserving aspect ratio:
```markdown
---
## Rendszerarchitektúra Áttekintés

![Tri-Format Architektúra Diagram](architecture.png)
```

*Split layout (text on left, illustration on right):*
```markdown
---
## Tervezési Alapelvek

A generátor szigorú specifikáció szerint működik:
- **Tri-Format paritás**: Minden megjelenítési forma azonos élményt ad.
- *Gyors fordítás*: Pár másodperc alatt elkészül az összes kimenet.

![Moduláris Felépítés](architecture.png)
```

#### 7. Task Lists & Typographic Extensions
Task list checkboxes and extended typography (strikethrough, highlight, sub/superscript):
```markdown
---
## Feladatlista és Rendszerstátusz

A rendszer támogatja a legújabb tipográfiai elemeket:
- ~~Elavult monolitikus felépítés~~ helyett modern moduláris motor
- ==Kiemelt fontosságú== fókuszpontok
- Kémiai jelölések: H~2~O és hatványok: E = mc^2^
- [x] Tri-Format paritás biztosítása (HTML, PPTX, PDF)
- [x] Képek és táblázatok natív renderelése
- [ ] További témasablonok készítése
```

#### 8. Standard List Slide (`SlideType.STANDARD`)
Plain bullets, numbered items, and sources:
```markdown
---
## A vér betegségei

- Vérszegénység (anémia)
- Fehérvérűség (leukémia)
- Vérzékenység (hemofília)
```

---

## 🎨 Modular Themes & Visual Archetypes

Presentation styling is governed by two orthogonal dimensions:
1. **Color Themes (`--theme`)**: Colors and palettes stored as declarative JSON in `generator/themes/`.
2. **Structural Archetypes (`--archetype`)**: Layout, shapes, borders, and typography styles (`editorial`, `cards`, `neubrutalism`, `terminal`, `minimal`, `corporate`).

### List Available Themes & Archetypes:
```bash
# List all 6 visual archetypes (structural styles):
./run.py --list-archetypes

# List all available themes (color palettes) and their default archetypes:
./run.py --list-themes
```

### Orthogonal Combination & Overrides:
```bash
# Generate using a curated theme (uses the theme's default archetype):
./run.py slideshow_1 --theme warm_academic

# Override the structural archetype (e.g. apply neubrutalism structure to warm_academic colors):
./run.py slideshow_1 --theme warm_academic --archetype neubrutalism

# Try different archetypes:
./run.py slideshow_1 --theme dark_terminal
./run.py slideshow_1 --theme swiss_minimal
./run.py slideshow_1 --theme corporate_navy
./run.py slideshow_1 --theme bold_neubrutalism
```

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
* **Next Slide**: `Right Arrow` (`→`), `Spacebar`, `PageDown`, or **Swipe Left** on touch devices.
* **Previous Slide**: `Left Arrow` (`←`), `PageUp`, or **Swipe Right** on touch devices.
* **First / Last Slide**: `Home` / `End`
* **Fullscreen**: `F` key
* **Audio Playback**: Click the **Narration** button in the slide header to play or pause.
