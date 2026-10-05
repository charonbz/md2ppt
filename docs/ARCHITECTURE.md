# System Architecture & Technical Documentation

This document describes the internal architecture, technical background, and data flow of **md2ppt**.

---

## 1. System Overview

The goal of this platform is to convert plain Markdown outlines (`slides.md`) accompanied by optional slide-level audio files (`.m4a`, `.mp3`) into professional, 16:9 widescreen presentations across three first-class output formats:

1. **Microsoft PowerPoint (`presentation.pptx`)**: Standard PowerPoint file with native embedded audio shapes (click-to-play narration).
2. **Interactive Web Presentation (`index.html`)**: Fully self-contained, zero-dependency HTML5/CSS3/JavaScript slideshow with embedded Base64 audio, live duration/progress tracker, keyboard navigation, and card-based responsive layout.
3. **Vector PDF (`presentation.pdf`)**: Pixel-perfect, 16:9 widescreen printable and presentable PDF export.

---

## 2. Architecture & Data Pipeline

The generator employs a deterministic, multi-stage processing pipeline:

```mermaid
flowchart TD
    MD["slides.md<br/>(Markdown text + Metadata)"] --> Parser["parser.py<br/>(Markdown Parser & Lexer)"]
    AudioSrc["Audio Files<br/>(*.m4a, *.mp3, etc.)"] --> AudioProc["Audio Processor<br/>(ffmpeg Transcoding & Base64)"]
    
    Parser --> AST["PresentationData AST<br/>(SlideData, CardItem Objects)"]
    ThemeFiles["themes/*.json"] --> ThemeEngine["theme_engine.py<br/>(Theme Loader & Palettes)"]
    
    AST --> Pipeline["Render Engine"]
    AudioProc --> Pipeline
    ThemeEngine --> Pipeline
    
    Pipeline --> HTMLR["html_renderer.py"]
    Pipeline --> PPTXR["pptx_renderer.py"]
    
    HTMLR --> DistHTML["dist/index.html<br/>(Standalone Web Player)"]
    HTMLR --> ChromeHeadless["Headless Google Chrome<br/>(--print-to-pdf)"]
    ChromeHeadless --> DistPDF["dist/presentation.pdf<br/>(Vector 16:9 PDF)"]
    
    PPTXR --> DistPPTX["dist/presentation.pptx<br/>(PowerPoint with Embedded Audio)"]
```

---

## 3. Directory Layout & Components

```
md2ppt/
├── docs/                       # System & architectural documentation
│   ├── ARCHITECTURE.md         # Detailed technical background and components
│   └── DECISIONS.md            # Architecture Decision Records (ADRs)
├── generator/
│   ├── models.py               # AST data models (SlideData, CardItem, ThemeConfig)
│   ├── parser.py               # Markdown parser & card layout extractor
│   ├── theme_engine.py         # JSON theme loader, validator, and manager
│   ├── theme_generator.py      # AI & algorithmic theme generator engine
│   ├── themes/                 # Declarative JSON style definitions
│   │   ├── schema.json         # JSON Schema for theme validation
│   │   ├── modern_clean.json   # Default crisp light theme with blue accents
│   │   ├── dark_mode.json      # Premium slate dark theme
│   │   ├── emerald_growth.json # Natural green theme
│   │   ├── warm_academic.json  # Warm cream & burgundy academic style
│   │   └── THEME_PROMPT.md     # Prompt guidelines for generating new AI themes
│   ├── renderers/              # Format-specific rendering engines
│   │   ├── html_renderer.py    # Interactive standalone HTML5 presentation renderer
│   │   ├── pptx_renderer.py    # PowerPoint generator (python-pptx)
│   │   ├── text_fit.py         # PPTX text measurement (line wrapping, line height) with bundled fonts
│   │   └── pdf_renderer.py     # Headless Chrome vector PDF exporter
│   ├── fonts/                  # Metric-compatible fonts used only to measure PPTX text (never embedded)
│   ├── showcase.py             # --showcase: every theme x archetype on one PNG grid
│   └── cli.py                  # CLI entry point and reusable TCP web server
├── pisa/                       # Living reference example
│   ├── slides.md               # Source markdown with audio metadata
│   ├── Title.m4a, slide_*.m4a  # Recorded narration audio
│   └── dist/                   # Output artifacts (ignored by git)
├── run.py                      # Root launcher with automatic .venv detection
├── requirements.txt            # Python dependencies (python-pptx, pillow, lxml)
├── AGENTS.md                   # Guidelines and mandatory rules for AI agents
└── README.md                   # User guide and CLI instructions
```

---

## 4. Component Details

### 4.1. Parser & Internal AST (`generator/parser.py`, `models.py`, `markdown_utils.py`)
- **Slide Delimiter Strategies**:
  - **Explicit Rules Mode**: If a document uses `---` horizontal rules or legacy `# Slide` / `# Title` markers, slides split strictly at these markers. In-slide `# ` and `## ` headings belong to the slide as titles or subtitles without triggering unwanted slide splits.
  - **Standard Markdown H1 Mode**: If a document contains neither `---` nor `# Slide`, top-level `# Heading` (H1) tags delimit slides.
  - **Fenced Code Safety**: Fenced code blocks (```` ```python ... ``` ````) track state so internal `#` code comments are never misidentified as slide boundaries.
- **Title Extraction & Sanitization (`markdown_utils.strip_markdown`)**:
  - Automatically identifies titles from `# `, `## `, bold markers `**Title**`, or leading terms (excluding structural prefixes `#`, `- `, `* `, `• `, `>`, ` ``` `, `: `, `|`, `![` to protect card headings and content blocks).
  - Slide headings and card titles keep inline Markdown (rendered as markup); `PresentationData.title` (deck title used for category labels, title pills, `<title>` and PPTX badges) is plain text via `strip_markdown`.
  - Trailing colons are removed by `_strip_trailing_colon`, which also handles colons inside closing emphasis markers (`_Részei:_` -> `_Részei_`).
- **In-Slide Markdown Structures**:
  - **Definition Lists**: Pandoc/PHP Markdown Extra format (`Term\n: Definition line`) parsed directly into visual `CardItem` blocks.
  - **Structured Bullet Cards**: Multi-line bullets with indented sub-properties (`- Term:\n  **Prop**: Val`) or single-line colon items (`Term: Description`) converted to `CardItem` objects. A colon inside a leading emphasis marker (`- **Term:** desc`) is handled; otherwise the split happens at the first colon outside inline tokens (code spans, links, raw URLs). When cards are demoted back into list items on non-card slides, the title is wrapped in `**` only if it has no markup of its own.
  - **Visual Cards (`### ` or `## `)**: Sub-headings within content lines create structured card blocks.
  - **Blockquotes (`> `)**: Rendered as prominent definition / quote cards.
  - **Fenced Code Blocks**: Highlighted monospace dark code container in PPTX and HTML.
  - **Lists & Auto-Linking**: Bullet lists, numbered lists, and raw URL auto-linking.
  - **Multi-Line & Line Break Handling**: Multi-line card descriptions and definition entries preserve internal newlines (`\n`) in the AST. In HTML, both `\n` and explicit `<br>` / `<br/>` render as unescaped `<br/>` elements; in PPTX, they are serialized to native DrawingML `<a:br/>` soft breaks.
- **Dynamic Deck Branding**:
  - Category lead tags and title pill badges dynamically display the presentation title (`PresentationData.title`) instead of hardcoded demo labels.
- **Metadata Extraction**:
  - `<!-- audio: filename.m4a -->`: Associates an audio track with the slide.
  - `<!-- notes: ... -->`: Speaker notes.
  - `<!-- type: ... -->`: Manual layout type override (`title`, `cards`, `definition`, `code`, `standard`).
  - All other HTML comments (including multi-line ones) outside fenced code are removed before content parsing.
- **Link Text**: Link text is parsed recursively for inline markup in both renderers; HTML renders link text without link tokens so anchors never nest.
- **Title-Scoped Card Numbering**: Card numbering continues (`01, 02` -> `03, 04`) strictly when a slide continues the previous slide's title (e.g., matching title or `(folytatás)` / `(part 2)` suffix). When a slide introduces a new title, card numbering restarts from `01`.
- **Card Titles Inline Markdown Preservation**: Card titles retain inline Markdown (e.g., `*italic*`, `**bold**`). Titles are rendered via `render_markdown_html()` into `<em>` and `<strong>` tags in HTML/PDF and via `parse_markdown_runs()` into styled PowerPoint runs (`run.font.italic = True`, `run.font.bold = True`).

#### Markdown-to-Slide Element Mapping Reference:
| Markdown Syntax | AST Element | Slide Layout / Component | Notes & Styling |
|---|---|---|---|
| `---` or `# Slide` or `# ` (H1) | Slide boundary | **Slide Transition** | Delimits slides. Delimiter mode automatically avoids phantom slides. |
| `# Title` (Slide 1) | `SlideType.TITLE` | **Title Slide** | Displays main deck title, presenter pill, and author credit. |
| `# Header` or `## Header` or `**Title**` | `slide.title` | **Slide Header** | Cleaned of asterisks/hashes. Styled with theme title font and accent colors. |
| `### Card Title`<br/>`Description` | `CardItem` | **Info Card Box** | Floating card with sequential numeric index badge (`01`, `02`). Blank lines between the heading and its body are allowed; the body ends at the next blank line, heading, quote, code fence, table or image. |
| `Term:`<br/>`: Definition line 1`<br/>`: Definition line 2` | `CardItem` | **Definition Card Box** | Standard Markdown definition list rendered into visual cards. |
| `- Term:`<br/>`  **Prop**: Value` | `CardItem` | **Property Card Box** | Indented multi-line bullets converted into card containers. |
| `- Title: Description`<br/>`Title: Description` | `CardItem` | **Key-Value Card Box** | Single-line colon syntax parsed into structured cards. |
| `| Col 1 | Col 2 |`<br/>`| :--- | :---: |` | `TableData` | **Table Slide** (`SlideType.TABLE`) | Formatted table with text alignments (left/center/right) across HTML, PPTX, and PDF. |
| `![Alt Text](path.png)` | `ImageData` | **Hero Image / Split Layout** | Standalone hero slide (`SlideType.IMAGE`) or split side-by-side layout alongside text. |
| `- [x] Done`<br/>`- [ ] Pending` | Task list token | **Task List** | Custom styled checkboxes (HTML) and checkmark bullets `☑` / `☐` (PPTX). |
| `> Quote or definition` | `slide.quote` | **Definition Slide** | Large decorative quotation card (`“`) with accent left border. |
| ```` ```python ````<br/>`def code():...`<br/>```` ``` ```` | `slide.code_snippet` | **Code Block Slide** | Dark IDE container with monospace code font and language badge. |
| `- Item`<br/>`* Item`<br/>`1. Item` | `slide.list_items` | **Styled Content List** | Clean bullet list with theme bullet markers (chevron / en-dash / dot). |
| Leading / trailing paragraphs | `slide.paragraphs` | **Intro / Footnote Text** | Lead subtitle above cards or italicized note below cards. |
| `Készítette: Név`<br/>`Author: Name` | `slide.author` | **Author Line** | Presenter credit with left decorative accent bar. |
| `**bold**` or `__bold__` | Bold token | **Bold Text** | `<strong>` in HTML; native `run.font.bold` in PowerPoint. |
| `*italic*` or `_italic_` | Italic token | **Italic Text** | `<em>` in HTML; native `run.font.italic` in PowerPoint. |
| `~~strikethrough~~` | Strike token | **Strikethrough** | `<del>` in HTML; native OpenXML `sngStrike` in PowerPoint. |
| `==highlight==` | Highlight token | **Highlighted Text** | `<mark>` in HTML; native DrawingML `<a:highlight>` in PowerPoint. |
| `^superscript^` | Sup token | **Superscript** | `<sup>` in HTML; native `30000` baseline shift in PowerPoint. |
| `~subscript~` | Sub token | **Subscript** | `<sub>` in HTML; native `-25000` baseline shift in PowerPoint. |
| `` `code` `` | Code chip | **Inline Code Pill** | Rounded chip in HTML; Consolas monospace run in PowerPoint. |
| `[link](url)` or raw `https://...` | Link token | **Clickable Link** | `<a href>` in HTML; native PowerPoint hyperlink (`run.hyperlink.address`, underlined italic) showing only the link text. |
| `->` / `-->` or `<-` / `<--` | Arrow token | **Theme-Colored Arrow (`→` / `←`)** | `<span class="md-arrow">→</span>` (or `←`) with theme `var(--accent)` in HTML/PDF; native run with `accent_rgb` in PowerPoint. `<->` / `<-->` stay literal. |
| `<!-- audio: file.m4a -->` | `slide.audio_filename` | **Audio Widget** | Base64 standalone player in HTML; native audio shape in PPTX. |
| `<!-- notes: ... -->` | `slide.notes` | **Speaker Notes** | Presenter notes available during delivery. |
| `<!-- type: ... -->` | `slide.slide_type` | **Layout Override** | Explicitly forces `title`, `cards`, `definition`, `code`, `table`, `image`, or `standard`. |

### 4.2. Theming & Structural Archetypes (`generator/themes/`, `theme_engine.py`)
Visual appearance is governed by two orthogonal dimensions:
1. **Color Palette (Themes)**: Configured in `generator/themes/*.json` (e.g. `warm_academic.json`, `bold_neubrutalism.json`, `dark_terminal.json`). Controls color tokens (`background`, `card_bg`, `card_border`, `primary_text`, `secondary_text`, `accent`, `badge_bg`, `badge_text`).
2. **Structural Styling (Archetypes)**: Defined by the `ArchetypeType` enum (`editorial`, `cards`, `neubrutalism`, `terminal`, `minimal`, `corporate`). Dictates card framing, border thickness, drop shadows, typography hierarchy, and shape geometry across all renderers.

#### The 6 Visual Archetypes:
- **`editorial`**: Refined academic/book/magazine aesthetic. Transparent cards with fine hairline dividing rules or subtle vertical left-accent lines, elegant Georgia serif typography, no heavy card boxes.
- **`cards`**: Elevated modern floating UI. Rounded corners (12–16px), soft ambient drop-shadows, subtle border strokes, modern SaaS feel.
- **`neubrutalism`**: High-contrast pop-art aesthetic. Thick solid black borders (2.5–3px), hard unblurred black offset drop shadows (`5px 5px 0px #000`), geometric sharp corners, bold punchy badges.
- **`terminal`**: Hacker / developer console aesthetic. Monospace typography (`JetBrains Mono`, `Consolas`), dark surface, console prompt prefixes (`root@slides:~# `, `>_`), sharp geometry, and subtle grid feel.
- **`minimal`**: Swiss International Typographic Style. Zero borders, zero shadows, transparent cards, oversized numeric indices (`01`, `02`), maximum whitespace, stark typographic contrast.
- **`corporate`**: Executive consulting style (McKinsey / BCG slide archetype). Crisp geometry, solid color top header banner on cards, structured business layout.

#### Orthogonal Mixing & CLI Overrides:
Each theme JSON declares an optional `"archetype"` (defaulting to `"cards"` for backwards compatibility). Users can override the structural style on the command line:
```bash
# Default pairing (warm_academic with editorial):
./run.py pisa --theme warm_academic

# Orthogonal override (warm_academic palette with neubrutalism structure):
./run.py pisa --theme warm_academic --archetype neubrutalism

# Configure bullet point style:
./run.py pisa --theme warm_academic --archetype editorial --bullet-style editorial

# Discover all archetypes & themes:
./run.py --list-archetypes
./run.py --list-themes

# Render the example slide in every theme x archetype combination into one PNG grid:
./run.py --showcase                  # -> dist/showcase.png
./run.py --showcase /tmp/themes.png --bullet-style refined
```

- **Configurable Bullet Styles (`BulletStyle`, `--bullet-style`, `--bullets`)**:
  - `chevron` (default): Dynamic directional arrow (`›`) in accent color.
  - `editorial`: Literary typography en-dash (`–`) in accent color.
  - `refined`: Centered geometric round dot (`•`) in accent color.
  - Card bullet lines (Markdown lines starting with `- `, `* `, `• `) are automatically structured into `.card-bullets` lists with density tier scaling, rendered natively in HTML/PDF and with colored runs in PowerPoint.
  - **Midline Alignment**: Markers are inline-block `::before` elements hung into the li's padding (`--bullet-indent` per density tier). Chevron and en-dash keep the li's font-size and line-height (enlarged with `transform: scale(...)`), so they share the first line's baseline; the refined dot uses `vertical-align: middle` (x-height midline). No per-tier pixel offsets.
  - In mixed task lists, plain items keep their bullet marker (`li:not(.task-item)`), matching PPTX.
  - Arrows and bold text inside accent-colored table headers inherit the header text color.
  - **Arrow Optical Midline Lift**: `.md-arrow` (`→`) uses `vertical-align: 0.12em;` to lift the arrow shaft directly into the optical midline of adjacent lowercase and uppercase characters.

- **AI Theme Generation (`theme_generator.py`)**: When `GEMINI_API_KEY` is present, queries Gemini; otherwise, an algorithmic palette synthesizer analyzes keywords (e.g. "dark", "sötét", "green", "zöld", "nordic", "cyberpunk") to immediately produce a valid theme JSON with `"archetype": "cards"`. The prompt includes the top-level `bullet_style`; invalid `archetype` / `bullet_style` values fall back to `cards` / `chevron`.
- **Single `bullet_style` location**: Themes set `bullet_style` at the top level only (`schema.json`); the CLI `--bullet-style` overrides it.

### 4.3. Adaptive Density Tiers (`generator/models.py`, `generator/parser.py`)
To prevent sparse slides from having tiny fonts while ensuring content-heavy slides never overflow the 16:9 canvas, the parser automatically assigns every slide a discrete density tier:
- **`DensityTier.SPACIOUS`**: For light slides (1–2 cards, $\le 3$ short bullets, or concise quotes). Features bold, dominant hero typography (main cover titles up to 76px / Pt(58), body/bullets up to 34px / Pt(28), definitions up to 40px / Pt(30), and generous padding).
- **`DensityTier.BALANCED`**: For standard content (3–4 cards, 4–5 bullets). Provides confident, high-impact presentation typography (main cover titles 64px / Pt(50), body/bullets 28px / Pt(22), definitions 32px / Pt(24)).
- **`DensityTier.COMPACT`**: For dense slides (5+ cards, 6+ list items, tables, code). Maintains strict presentation readability thresholds (body/bullets 24px / Pt(18)) rather than shrinking into illegible document text.
- **Constant Slide Heading Typography**: To prevent visual jumping when navigating across slides of varying density, content slide headings (`.slide-heading`) are fixed at a constant **48 px** (PowerPoint: **32 pt**) across all density tiers.
- **Wrapped-Line Aware Card Density**: The `CARDS` classifier estimates each card's wrapped line count (title + description, chars-per-line by card count, derived from PPTX card widths). `BALANCED` requires ≤ 4 cards, < 750 characters **and** ≤ 10 estimated lines per card; otherwise `COMPACT`.

### 4.4. HTML Renderer (`generator/renderers/html_renderer.py`)
- **Zero-Dependency Standalone HTML**: Audio tracks are embedded directly into the HTML as Base64 data streams (`data:audio/mpeg;base64,...`). This bypasses browser `file:///` sandbox restrictions and makes the HTML completely portable.
- **Automatic MP3 Transcoding**: If `ffmpeg` is present, proprietary or container-specific audio formats (such as Samsung `3gp4` M4A files) are converted to standard MP3.
- **Multi-Source Audio Fallback**: The `<audio>` element provides three fallback sources: embedded Base64 MP3, relative MP3 file, and original file.
- **Virtual 16:9 Scale-to-Fit Canvas (`1600 × 900 px`)**:
  - The viewport is designed as a fixed virtual canvas of `1600 × 900 px` centered inside `#presentation-stage`.
  - On resize or orientation changes, JavaScript dynamically calculates `scale = Math.min(window.innerWidth / 1600, window.innerHeight / 900)` and applies `transform: scale(scale)` to `#presentation-viewport`.
  - The stage uses `100dvh` (with a `100vh` fallback) so collapsible mobile toolbars don't cover the nav footer.
  - `.slide` uses `overflow: hidden`; content that exceeds the canvas is clipped rather than spilling under the nav controls or onto extra PDF pages.
- **Mobile Touch Swipe Gestures**: Supports native touch navigation (`touchstart` / `touchend`) allowing users on mobile phones or tablets to swipe left/right to change slides. Multi-touch gestures (pinch-zoom) never change slides.
- **Interactive Controls**: Keyboard navigation (arrow keys, spacebar, PgUp/PgDown, `F` for fullscreen), live time tracking (`Playing (0:02 / 0:07)`), and animated wave bars.

### 4.5. PowerPoint Renderer (`generator/renderers/pptx_renderer.py`)
- Uses `python-pptx` to build 16:9 widescreen slides (`13.333 × 7.5` inches).
- Synchronized with `slide.density_tier`: dynamically scales title `Pt(...)`, body text, card labels, and paragraph spacing across spacious, balanced, and compact tiers.
- **Measured card text fit**: on cards slides the density tier only gives the starting sizes. `text_fit.py` wraps every card title and description with real glyph widths (`generator/fonts/`: Carlito for Calibri, Liberation Sans for Arial / Arial Black, Gelasio for Georgia, Liberation Mono for Consolas), and `_fit_card_text` lowers one common title/description size per slide until every title fits without a mid-word break and title + description fit the card. Each title box is as tall as its measured text and the description starts right below it. Descriptions stop at 12 pt; if that still does not fit, generation prints `[PPTX] Warning: slide N: ...`. Card text insets per archetype live in `_CARD_TEXT_GEOMETRY`.
- **Header title**: on slides with narration the title box ends before the audio widget, and the title shrinks from 32 pt (minimum 20 pt, with a warning) until it fits two lines without a mid-word break.
- Renders cards and content blocks as native vector rounded shapes colored according to the selected theme. A trailing paragraph on a cards slide renders as an italic footnote below the grid (parity with HTML `.slide-footnote`).
- Line breaks use `paragraph.add_line_break()` (`<a:br/>`).
- Embeds audio directly into the `.pptx` ZIP package (`ppt/media/media1.m4a`) as a native media shape (`<p14:media>` and `<a:hlinkClick action="ppaction://media">`), triggering playback on click.

### 4.6. PDF Renderer (`generator/renderers/pdf_renderer.py`)
- Leverages the print stylesheet in the HTML (`@media print { @page { size: 1600px 900px; margin: 0; } }`).
- Resets stage and viewport transforms (`transform: none`) and sizes every slide to the same `1600 × 900 px` canvas as the web player, so text wraps identically in HTML and PDF (pages are 1200 × 675 pt).
- Executes Headless Google Chrome:
  ```bash
  google-chrome-stable --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf=dist/presentation.pdf dist/index.html
  ```
- Produces clean, vector-rendered, 16:9 widescreen PDF slides.

### 4.7. Reusable TCP Web Server & Source Watcher (`generator/cli.py`)
- **Instant Port Reuse**: Implements `ReusableTCPServer` with `SO_REUSEADDR` and `SO_REUSEPORT`, ensuring that on `Ctrl + C`, the socket descriptor is immediately closed without lingering in Linux `TIME_WAIT`.
- **Zero-Dependency Background Watcher (`watch_and_rebuild`)**:
  - Automatically runs when `--serve` is active (or standalone via `--watch`). `--no-watch` disables it and takes precedence over both.
  - Built strictly using Python's standard library (`threading`, `pathlib.Path.stat`, `time`, `os.walk`) without requiring external packages like `watchdog`.
  - Tracks filesystem modification times (`st_mtime`) for `slides.md`, audio files, images, and the applied theme JSON (while strictly ignoring generated files in `dist/`).
  - **Debounced Rebuilds**: Features a 300ms debounce buffer to handle multi-file editor flushes or rapid successive saves smoothly.
  - Automatically re-executes the build pipeline with the exact flags originally provided (`--theme`, `--archetype`, `--format`).
  - Catches build exceptions gracefully so partial/invalid editor saves do not crash the running development server; a failed rebuild is reported as `❌ Rebuild failed` on stderr.
  - Allows instant previewing on browser refresh (`F5`) without restarting the server.
- **Showcase (`--showcase [PNG]`, `generator/showcase.py`)**: Renders a built-in example slide through the HTML renderer for every theme x archetype combination, embeds them as scaled iframes in one grid page, and screenshots it with a single headless Chrome process (one browser for all combinations keeps memory flat). Default output `dist/showcase.png`.
