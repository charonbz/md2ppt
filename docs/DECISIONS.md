# Architecture Decision Records (ADRs)

This document records the key architectural and technological decisions made during the design and development of the Slideshow Generator platform.

---

## ADR-001: Deterministic Code Pipeline vs. Direct LLM Output

### Context
Consideration of whether presentations (PPTX and PDF files) should be generated directly by an AI model or by a dedicated code generation engine.

### Decision
Presentations are built by a deterministic Python code pipeline. The AI acts as the architect, code builder, template designer, and optional content structuring engine.

### Rationale
- PowerPoint (`.pptx`) is a strictly specified OpenXML package consisting of ZIP archives, XML relations (`_rels`), and binary media parts.
- PDF is a binary vector graphic stream.
- Large language models communicate through text tokens; they cannot reliably construct raw binary PPTX or PDF file streams directly.
- A deterministic code pipeline executes in fractions of a second, guarantees 100% structural validity, and provides pixel-perfect reproducibility.

---

## ADR-002: Tri-Format First-Class Support (PPTX, HTML, PDF)

### Context
The slide deck requires audio playback. While the user's initial preferred format was PDF, modern PDF viewers (web browsers, mobile viewers, Linux Evince) block embedded multimedia annotations for security reasons (supported reliably only by desktop Adobe Acrobat Reader).

### Decision
The system simultaneously generates three distinct outputs:
1. **PowerPoint (`presentation.pptx`)**: Native media playback across desktop, web, and mobile PowerPoint apps.
2. **Web Presentation (`index.html`)**: Universal, zero-dependency browser slideshow with custom audio controls.
3. **Vector PDF (`presentation.pdf`)**: Standard, printable, vector-rendered static presentation slides.

### Rationale
This covers all presentation scenarios: seamless audio-visual presentation on the web and PowerPoint, alongside an easily shareable, printable PDF.

---

## ADR-003: Standalone Web Player with Base64 Audio Embedding & MP3 Fallback

### Context
When testing local `index.html` playback via the `file:///` protocol, audio playback failed. Two factors were identified:
1. Samsung Voice Recorder saves `.m4a` files with an internal `3gp4` (3GPP) media brand, which Linux/Chromium audio pipelines often fail to demux in `<audio>` tags.
2. Modern browsers enforce strict "Local File Restrictions" (sandbox) preventing local HTML files from fetching relative media files.

### Decision
- The generator leverages `ffmpeg` to automatically transcode source audio into universal MP3 format.
- Audio data is **directly embedded into `index.html` as a Base64 data stream (`data:audio/mpeg;base64,...`)**.
- The `<audio>` element features a three-tier fallback: embedded Base64 MP3 -> relative MP3 file -> original M4A file.

### Rationale
The resulting `index.html` is completely self-contained. It can be opened from any directory, attached to an email, or loaded via `file:///` without path resolution errors or browser sandbox blocks.

---

## ADR-004: Declarative JSON Theming Engine & AI Theme Generation

### Context
Visual presentation styling (color schemes, cards, fonts) must be strictly decoupled from slide content, and users must be able to add new styles via AI prompts.

### Decision
- Themes are stored as declarative JSON files in `generator/themes/*.json` and validated by `schema.json`.
- A dedicated `theme_generator.py` and `--ai-theme "description"` CLI command allow generating new themes using Gemini API or keyword-based algorithmic synthesis.
- A prompt template (`THEME_PROMPT.md`) allows external LLMs (Claude, ChatGPT) to generate drop-in compatible theme JSONs.

### Rationale
Adding or tweaking themes requires zero Python code changes—simply creating or editing a single JSON file.

---

## ADR-005: Continuous Card Numbering Across Sequential Category Slides

**Status:** Superseded by ADR-016 (numbering continues only when the slide title matches the previous slide).

### Context
A 4-part category breakdown in `slides.md` spans two consecutive slides (2 items per slide). Previously, both slides restarted numbering from `01, 02`.

### Decision
`parser.py` maintains a persistent running card counter across consecutive `CARDS` slides. The first slide renders `01, 02`, while the subsequent slide continues with `03, 04`.

### Rationale
Clearly communicates to the audience that the cards represent a unified, multi-part categorical taxonomy.

---

## ADR-006: Instant Port Reuse for Web Server (`SO_REUSEADDR` & `SO_REUSEPORT`)

### Context
When stopping the built-in development web server (`Ctrl + C`), restarting immediately resulted in `[Errno 98] Address already in use` due to the operating system's `TIME_WAIT` socket state.

### Decision
Implemented `ReusableTCPServer` in `generator/cli.py`, which configures `SO_REUSEADDR` and `SO_REUSEPORT` on the socket and explicitly calls `server.server_close()` in the shutdown handler.

### Rationale
Eliminates socket timeout delays, allowing instant server restarts on the same port without OS lockouts.

---

## ADR-007: Universal English Language Rule for Code and Documentation

### Context
To ensure consistency across AI agents, code maintenance, and open development, the language convention must be clearly standardized.

### Decision
- All source code, comments, docstrings, CLI logs, documentation (`docs/`, `README.md`, `AGENTS.md`), and Git commit messages must strictly be in **English**.
- Presentation content (`slides.md`) and user prompts may be in **Hungarian** (or any other human language); the platform, parser, and generator must gracefully handle UTF-8 and multilingual slide content.

### Rationale
English is the universal standard for software engineering and AI agent tooling, while preserving full multilingual support for user slide decks.

---

## ADR-008: Orthogonal Visual Archetypes & Palette Themes

### Context
Themes previously only modified color hex values and border radiuses, causing all presentations to produce identical card structures regardless of the theme. The user requested radical visual variety and diverse slide aesthetics without introducing runtime LLM latency, breaking the Tri-Format principle (HTML, PPTX, PDF in sync), or bloating Markdown authoring syntax.

### Decision
Decouple visual styling into two orthogonal, independently configurable dimensions:
1. **Palette Themes (`generator/themes/*.json`)**: Define color palettes and font families.
2. **Structural Archetypes (`ArchetypeType` enum)**: Six distinct visual archetypes (`editorial`, `cards`, `neubrutalism`, `terminal`, `minimal`, `corporate`) governing shapes, border widths, drop shadows, header dividers, and typographic weights across all renderers.

Themes specify their default archetype in JSON, and users can override it at generation time via the `--archetype <name>` CLI parameter.

### Rationale
- **Zero Code Duplication**: A unified rendering engine handles the visual variants conditionally, avoiding fragmented per-theme templates.
- **Tri-Format Synchronization**: PPTX shapes (hard drop shadows, hairline dividers, top accent banners) and HTML CSS classes map 1:1, ensuring presentations look structurally identical across PowerPoint, standalone Web, and Vector PDF.
- **Deterministic & Offline**: Provides dramatic visual diversity at instant build speeds without runtime LLM dependencies.

---

## ADR-009: Comprehensive Markdown Support & AST Lexer Architecture

### Context
Users authoring slide decks expect standard Markdown structures to work intuitively:
1. Standard slide delimiters (`---` and `# ` headings) without breaking legacy `# Title` and `# Slide` formats.
2. In-slide structures: Definition lists (`Term\n: Definition`), indented multi-line bullets (`- Term:\n  **Prop**: Val`), unbulleted key-value pairs, fenced code blocks (` ```python ... ``` `), blockquotes (`> `), and standard lists.
3. Inline Markdown formatting: `**bold**`, `*italic*`, `` `code` ``, `[link](url)`, and raw URLs rendered natively across HTML tags and PowerPoint `Run` objects.
4. Clean presentation titles: Titles extracted from headings or bold phrases without leaking markdown syntax (e.g. asterisks or colons) into PowerPoint and HTML titles.

### Decision
1. **Dynamic Delimiter Strategy (`split_into_raw_slides`)**:
   - If `---` or `# Slide` / `# Title` markers exist, they act as strict slide delimiters; `# ` or `## ` within slides do not create phantom slides.
   - If neither marker exists, top-level `# ` headings delimit slides.
   - Fenced code blocks are tracked with state flags so code comments (e.g. `# comment`) never trigger slide breaks.
2. **AST Lexer & Run Parser (`markdown_utils.py`)**:
   - `render_markdown_html(text)` converts inline tokens to safe HTML tags and auto-links raw URLs.
   - `parse_markdown_runs(text)` parses linear runs of `(chunk, is_bold, is_italic, is_code)` tuples for `python-pptx` native formatting without raw markup characters.
   - `strip_markdown(text)` produces pristine text strings for slide titles and header shapes.
3. **Structured Content Extraction (`_parse_content_structures`)**:
   - Automatically categorizes definition lists, indented bullets, and colon-delimited pairs into visual `CardItem` blocks.
   - Dedicated slide types (`SlideType.CODE`, `SlideType.CARDS`, `SlideType.DEFINITION`, `SlideType.STANDARD`, `SlideType.TITLE`).
4. **Dynamic Deck Branding**:
   - Presentation title (`PresentationData.title`) replaces hardcoded demo strings across title badges and category leads.

### Rationale
- Completely eliminates syntax surprises for users writing plain or extended Markdown.
- Preserves 100% backward compatibility with existing decks (`slideshow_1`).
- Delivers visually stunning, structured card and code layouts in HTML, PPTX, and PDF with zero manual configuration.

---

## ADR-010: Tables, Images, and Extended Typographic Syntax Support

### Context
To achieve full parity with modern Markdown feature sets (e.g., Markdown Guide Cheat Sheet) while maintaining the Tri-Format Principle (HTML, PPTX, PDF) and Zero-Dependency standalone player requirements:
1. **Tables**: Users need Markdown tables (`| Col 1 | Col 2 |`) with column alignment (`:---`, `:---:`, `---:`) rendered as native presentation tables across Web and PowerPoint.
2. **Images**: Presentations require both standalone hero illustrations (`SlideType.IMAGE`) and split side-by-side layouts (`SlideType.STANDARD`) where text appears on the left and an image appears on the right. In the Web player, images must remain 100% portable and offline-capable without browser sandbox restrictions (`file:///`).
3. **Extended Typography**: Users need task lists (`- [x]`, `- [ ]`), strikethrough (`~~text~~`), highlight (`==text==`), subscript (`~text~`), and superscript (`^text^`).

### Decision
1. **Data Models (`generator/models.py`)**:
   - Introduced `TableData(headers: List[str], rows: List[List[str]], alignments: List[str])`.
   - Introduced `ImageData(alt: str, src: str, resolved_path: Optional[Path])`.
   - Added `SlideType.TABLE` and `SlideType.IMAGE`.
   - Added `table: Optional[TableData]` and `images: List[ImageData]` fields to `SlideData`.
2. **Lexer & Markdown Parser (`generator/markdown_utils.py`, `generator/parser.py`)**:
   - Upgraded `TextRun` to a dataclass supporting `is_strike`, `is_highlight`, `is_sub`, `is_sup`, `is_link`, and `link_url` while retaining tuple unpack compatibility.
   - Enhanced `render_markdown_html` to output `<del class="md-strike">`, `<mark class="md-highlight">`, `<sub>`, and `<sup>`.
   - Enhanced `strip_markdown` to clean extended tokens for header shapes.
   - Enhanced `_parse_content_structures` to parse markdown tables into `TableData` and images into `ImageData`.
   - Added task list extraction (`- [x]`, `- [ ]`), tagging list items for checkbox rendering.
3. **Standalone Web Player & PDF (`generator/renderers/html_renderer.py`)**:
   - Automatic Base64 embedding of images (`data:image/...;base64,...`) into `dist/index.html`, eliminating `file:///` sandbox blocks and preserving offline portability.
   - Styled `.slide-table`, `.task-item`, `.task-checkbox`, `.slide-hero-image`, and `.split-layout` across all 6 archetypes.
4. **Native PowerPoint OpenXML Rendering (`generator/renderers/pptx_renderer.py`)**:
   - Tables rendered via `slide.shapes.add_table()` with theme-aware fills, header styling, and column alignment.
   - Images rendered via `slide.shapes.add_picture()` with aspect-ratio calculation via Pillow (`_add_picture_fit`) to prevent image distortion.
   - Side-by-side split layout: when a content slide includes an image, text occupies the left half and the fitted picture occupies the right half.
   - Low-level DrawingML OpenXML formatting for `sngStrike`, `<a:highlight>`, and baseline shift (`30000` / `-25000`) for superscript and subscript.
   - Task list items formatted with native checkmark symbols (`☑` / `☐`).

### Rationale
- Maintains 100% Tri-Format parity across HTML, PPTX, and PDF.
- Preserves the Zero-Dependency offline architecture for HTML and PDF exports.
- Delivers native, editable PowerPoint tables and properly proportioned media assets.

---

## ADR-011: Virtual Canvas Scale-to-Fit and Adaptive Density Tiers

### Context
User feedback highlighted two critical usability and presentation quality issues:
1. **Mobile Viewport Clipping**: On smartphones (especially in portrait mode, e.g. 390x844px), slides forced a rigid `height: min(100vh, calc(100vw * 9 / 16))` (around ~219px tall). Content cards, padded headings, and lists exceeded 219px inside the letterbox, and `overflow: hidden` truncated the bottom of every slide on mobile screens.
2. **Typography Density Mismatch**: Slides with minimal content (1–2 cards or 2 bullets) suffered from tiny, underwhelming fonts (`clamp(...)` evaluated down to 14–16px), making presentation slides feel empty and unreadable from a distance. The user explicitly requested: *"If there isn't much content on a slide, it shouldn't be tiny. If there is a lot of content, keep it on one slide with smaller fonts, but light slides must be big and readable."*

### Decision
1. **Virtual Coordinate Canvas (`1600 × 900 px`) & CSS Scale-to-Fit**:
   - The HTML slideshow uses a stage container (`#presentation-stage`, `100vw × 100dvh`, with a `100vh` fallback) with flex centering. Using the dynamic viewport height keeps the nav footer above collapsible mobile browser toolbars.
   - The presentation viewport (`#presentation-viewport`) is defined as a fixed coordinate space of `1600 × 900 px`.
   - On window resize or device orientation changes, JavaScript computes:
     $$\text{scale} = \min\left(\frac{W_{\text{window}}}{1600}, \frac{H_{\text{window}}}{900}\right)$$
     and applies `transform: scale(scale)` with `transform-origin: center center`.
   - On any device (mobile portrait, mobile landscape, ultrawide desktop), the entire 16:9 slide is visible. `.slide` uses `overflow: hidden`, so content that exceeds the canvas is clipped rather than spilling under the nav controls or onto extra PDF pages; density tiers are responsible for making content fit.
   - `@media print` renders the same unscaled `1600 × 900 px` canvas (`@page { size: 1600px 900px; margin: 0 }`, `transform: none`), so PDF text wraps exactly like the web player.

2. **Mobile Touch Swipe Navigation**:
   - Added `touchstart` and `touchend` swipe gesture listeners in `html_renderer.py` allowing mobile viewers to swipe left to advance or right to go back. A gesture during which more than one finger touched the screen (pinch-zoom) never changes slides.

3. **Discrete Density Tiers (`spacious`, `balanced`, `compact`)**:
   - Rather than unpredictable floating-point font equations per slide, implemented a discrete 3-tier heuristic classifier in `generator/models.py` (`calculate_density_tier`):
     - **`spacious`**: 1–2 cards, $\le 3$ bullets, or short quotes. Sets bold typography (headings 46–64px / 32pt, body 24–28px / 24pt, spacious card paddings).
     - **`balanced`**: 3–4 cards, 4–5 bullets. Confident presentation typography (~30% larger than legacy defaults).
     - **`compact`**: 5+ cards, 6+ bullets, dense tables or long code, or cards whose estimated wrapped line count exceeds the balanced budget (see ADR-015).
   - In `html_renderer.py`, `.slide` is tagged with `.density-{slide.density_tier.value}` and styled via semantic classes (`.slide-para`, `.slide-intro`, `.slide-footnote`).
   - In `pptx_renderer.py`, `slide.density_tier` drives title `Pt(...)`, body `Pt(...)`, card labels, and paragraph spacing.

### Rationale
- Completely solves mobile responsiveness with zero layout breaks across portrait and landscape orientations.
- Provides visual rhythm and punchy typography without artificially splitting user-authored slides.
- Synchronized 1:1 across Web player, PowerPoint, and PDF exports.

---

## ADR-012: Presentation Typography Scale-Up and Readability Standards

### Context
User feedback emphasized that presentation slides must follow the "less is more" rule rather than functioning as dense reading documents:
> *"A slideon a betuk eleg kicsik. Egy jo slideon nincs sok tartalom, ugy erzem egy kicsit sok mindent akarsz razsufolni."*
*(The fonts on the slide are rather small. On a good slide there isn't much content, I feel like you want to cram too much stuff onto it.)*

Previous baseline font sizes on the 1600×900 canvas (18px–22px body, 15px card descriptions, Pt(11)–Pt(14) in PPTX) were too small when scaled on mobile or viewed from a distance, producing an overly dense document look instead of a confident, bold presentation feel.

### Decision
1. **Scaled Baseline Typography Across All Density Tiers (HTML & PPTX Parity)**:
   - **Spacious Tier**:
     - Main titles: 76px / Pt(58) (previously 64px / Pt(50)).
     - Slide headings: 56px / Pt(38) (previously 46px / Pt(32)).
     - Body text & list items: 34px / Pt(28) (previously 28px / Pt(24)).
     - Definitions & quotes: 40px / Pt(30) (previously 34px / Pt(26)).
     - Cards: titles 36px / Pt(28), descriptions 26px / Pt(20).
   - **Balanced Tier**:
     - Main titles: 64px / Pt(50) (previously 52px / Pt(44)).
     - Slide headings: 48px / Pt(32) (previously 38px / Pt(27)).
     - Body text & list items: 28px / Pt(22) (previously 22px / Pt(18)).
     - Definitions & quotes: 32px / Pt(24) (previously 26px / Pt(20)).
     - Cards: titles 30px / Pt(23), descriptions 22px / Pt(17).
   - **Compact Tier (Strict Readability Floor)**:
     - Established a firm presentation readability floor: body text never drops below 24px in HTML / Pt(18) in PPTX.
     - Main titles 54px / Pt(42), headings 40px / Pt(26), card descriptions 18px / Pt(14).
2. **Generous Spacing & Breathing Room**:
   - Expanded grid gaps, card padding, paragraph margins, and bullet gaps across all archetypes to give content room to breathe and eliminate the crammed feel.

### Rationale
- Slide content is instantly readable from distance, on smartphones, and on conference projectors.
- Reinforces the presentation philosophy that slides are high-impact visual anchors rather than dense reading matter.
- Fully synchronized across HTML5, PowerPoint OpenXML, and headless Chromium PDF exports.

---

## ADR-013: Zero-Dependency Background Watcher for Live Rebuilds on Edit

### Context
When testing and developing presentations via the built-in web server (`--serve`), users iterate frequently by editing `slides.md` or changing audio/image assets. Previously, the CLI built the presentation once and launched a static HTTP server. Edits in the source directory were not detected, requiring users to terminate the server (`Ctrl + C`), re-run the CLI command, and reload the browser. The user requested:
> *"szeretnem ha server eszlelne a modositasokat a forrasfileban. ujrageneralna a hasznalt kapcsolokkal es egy bongeszo refresh mar az ujat mutatna"*
*(I would like the server to detect modifications in the source file, regenerate with the used flags, and a browser refresh would show the new version.)*

### Decision
1. **Zero-Dependency Polling Watcher (`watch_and_rebuild`)**:
   - Implemented a lightweight daemon background thread in `generator/cli.py` using strictly Python standard library components (`threading`, `time`, `pathlib.Path.stat`, `os.walk`).
   - Collects a filesystem fingerprint (`Path -> st_mtime`) tracking `slides.md`, audio files, images, and the applied theme JSON.
   - Strictly ignores generated output files in `dist/` and hidden paths to prevent recursive rebuild loops.
2. **Debounce Buffer & Safe Rebuilding**:
   - Applies a 300ms debounce buffer upon detecting file timestamp changes to accommodate multi-file editor flushes or rapid successive typing saves.
   - Automatically preserves and reapplies all original CLI flags (`--theme`, `--archetype`, `--format`).
   - Catches syntax/parser exceptions during rebuilds without terminating the server, allowing authors to fix mistakes and re-save safely.
3. **CLI Integration**:
   - Watching is active by default whenever `--serve` is used, providing immediate live feedback for web previews.
   - Added `--watch` to allow running the watcher in standalone mode without a web server (e.g., auto-rebuilding PPTX/PDF on file saves).
   - Added `--no-watch` flag to explicitly disable the background watcher when running `--serve` in static/read-only mode.
4. **Cache Control**:
   - Left untouched per user explicit instruction (`"cache controlt hagyjuk egyelore"`), retaining standard `SimpleHTTPRequestHandler` caching behaviors.

### Rationale
- Dramatically accelerates presentation development: authoring in Markdown is reflected in the web presentation with a single browser refresh (`F5`).
- Eliminates the need for external package dependencies (such as `watchdog`), preserving the platform's zero-dependency philosophy.

---

## ADR-014: First-Class Line Break Support in Markdown and Tri-Format Renderers

### Context
User reported that line breaks within slide content (such as multi-line card descriptions, indented sub-bullets, or explicit `<br>` tags) rendered as literal `<br>` text on the slides rather than creating actual line breaks:
> *"a sortoresek valodi sortoresek legyenek, <br> jelenik meg a slideokban helyette most"*
*(Line breaks should be real line breaks, <br> appears in the slides instead right now)*

Investigation revealed:
1. `generator/parser.py` joined multi-line body lines, definition lines, and sub-bullets with `"<br/>".join(...)`.
2. When passed through `render_markdown_html()`, `html.escape()` turned `"<br/>"` into `&lt;br/&gt;`, causing web browsers to display `<br/>` as raw visible text.
3. In `pptx_renderer.py`, `_add_formatted_runs()` treated `"<br/>"` as literal run text, printing raw `<br/>` into PowerPoint shape text frames.

### Decision
1. **AST Representation via Standard Newlines (`\n`)**:
   - `generator/parser.py` joins multi-line card descriptions and definition items using standard `\n` instead of `"<br/>"`.
2. **HTML Rendering (`render_markdown_html`)**:
   - Extended `INLINE_TOKEN_RE` to match explicit `<br\s*/?>` HTML tags.
   - Generates unescaped `<br/>` tags for both matched `<br>` tokens and escaped newlines (`\n` -> `<br/>`).
3. **PowerPoint Rendering (`pptx_renderer.py`)**:
   - Extended `parse_markdown_runs()` with `TextRun(text="", is_break=True)` emitted on newlines or `<br>` tags.
   - `_add_formatted_runs()` intercepts `is_break` and appends native DrawingML `<a:br/>` elements (DrawingML soft break / Shift+Enter).
4. **Title Sanitization (`strip_markdown`)**:
   - Strips `<br>` tags to clean spaces to prevent raw HTML in slide header titles.

### Rationale
- Restores natural, expected line break formatting across all three first-class presentation formats (Web, PowerPoint, and PDF).
- Users can naturally format card descriptions across multiple lines in Markdown without raw HTML tags leaking onto the presentation.

---

## ADR-015: Constant Slide Heading Typography and Line-Aware Card Density Classification

### Context
User feedback on presentation navigation and card density highlighted two inconsistencies:
> *"a slide title ne valtoztasson meretet. lehet tobb karakter van rajta, de a sorok szama is szamitson, a 3. slide kartyai eleg szellosek alul, tobb is elferne ott."*
*(The slide title should not change size. There may be more characters, but the number of lines should also matter; the cards on the 3rd slide are fairly spacious at the bottom, more would fit there.)*

1. **Jumping Slide Titles**: Variable heading sizes across density tiers (56px in `SPACIOUS`, 48px in `BALANCED`, 40px in `COMPACT`) caused jarring visual jumping and inconsistent anchor points when navigating from slide to slide.
2. **False Downscaling of 4-Card Grids**: The previous density heuristic classified any 4-card slide exceeding 550 characters into `COMPACT`. For cards containing 3-line prose sentences (e.g. 613 characters total), this caused fonts to shrink to 18px and left large empty areas at the bottom of the 1600×900 canvas.

### Decision
1. **Constant Slide Heading Typography (Tri-Format Parity)**:
   - Content slide headings (`.slide-heading`) are fixed at a constant **48 px** (line-height: 1.22) in HTML/PDF and **32 pt** in PowerPoint across all density tiers.
   - Category leads (`.slide-category`) are uniform at 18 px (PPTX: 12 pt).
2. **Wrapped-Line Aware Card Density Classification**:
   - `calculate_density_tier()` in `generator/models.py` estimates the wrapped line count of each card (title lines plus description lines, after `strip_markdown`), using a chars-per-line width that depends on the card count (`{1: 70, 2: 34, 3: 22, 4: 16}`, derived from PPTX card widths; titles use 0.75× of that width for their larger font):
     ```python
     if num_cards <= 2 and total_card_text < 320:
         return DensityTier.SPACIOUS
     elif num_cards <= 4 and total_card_text < 750 and max_card_lines <= _CARD_LINE_BUDGET:  # 10
         return DensityTier.BALANCED
     else:
         return DensityTier.COMPACT
     ```
   - Both the character budget and the line budget must hold. The first version of this rule combined them with `or` and counted raw `\n` characters, which kept 4-card slides with long single-line descriptions in `BALANCED` and made them overflow the canvas (PISA slides 2–4).

### Rationale
- Slide headings remain rock-solid and stable during navigation.
- Prevents premature downscaling on slides that have ample vertical space, maintaining optimal readability without awkward whitespace.

---

## ADR-016: Title-Scoped Card Numbering Continuation

### Context
Card numbering (`01`, `02`, `03`...) previously accumulated across all consecutive `CARDS` slides regardless of topic. On presentations with multiple distinct card topics (such as PISA slide 2 "Matematikai ismeretek" followed by slide 3 "Matematikai folyamatok és gondolkodás"), slide 3 started counting at `05, 06, 07, 08` instead of restarting. The user requested:
> *"a kartyaszamozas csak akkor folytatodjon ha a title megegyezik az elozo slide-al"*
*(Card numbering should only continue if the title matches the previous slide.)*

### Decision
1. **Title-Scoped Continuation (`generator/parser.py`)**:
   - `parse_slides_file` tracks `prev_title`.
   - `parse_single_slide` resolves `final_title` before card numbering.
   - Normalizes titles by stripping continuation suffixes (`(folytatás)`, `(continuation)`, `(part X)`).
   - If normalized titles match, card numbering increments `global_card_counter`.
   - If titles differ, card numbering resets to 1 for the new slide.

### Rationale
- Each distinct topic begins cleanly with card index `01`.
- Multi-slide split topics (e.g. "A mérés tartalmi kategóriái" and "(folytatás)") preserve continuous numbering (`01, 02` -> `03, 04`).

---

## ADR-017: Preservation of Inline Markdown Formatting in Card Titles

### Context
User feedback highlighted that italic formatting in card titles was ignored:
> *"kártyák cimeben nem érvényesül az italic"*
*(Italic formatting is not applied in card titles)*

In `pisa/slides.md`, the card title `### Matematikai érvelés *(Reasoning)*` rendered as plain `Matematikai érvelés (Reasoning)`. The parser called `strip_markdown(...)` when extracting card titles and definition terms, stripping `*` and `_` markup before storing them in `CardItem.title`. While `html_renderer.py` and `pptx_renderer.py` already had native inline Markdown token parsers for card titles, there were no remaining tokens to format.

### Decision
1. **Preserve Inline Markdown in `CardItem.title` (`generator/parser.py`)**:
   - Ceased wrapping card title extraction in `strip_markdown(...)` across:
     - Heading-based cards (`### ` / `## `)
     - Definition list terms (`Term\n: desc`)
     - Multi-line indented bullet cards (`- Term:\n  desc`)
     - Single-line bullet / colon cards (`_try_parse_card_from_bullet`)
     - Unbulleted key-value cards
   - Trailing colons (`:`) and hash markers (`#`) continue to be stripped, but inline syntax (`*italic*`, `**bold**`, `_italic_`, `` `code` ``) is preserved.
2. **Tri-Format Formatting Verification**:
   - **HTML (`html_renderer.py`)**: `render_markdown_html(card.title)` converts tokens into `<em>` and `<strong>`. Global CSS renders `em { font-style: italic; }` inside `.card-title`.
   - **PowerPoint (`pptx_renderer.py`)**: `_add_formatted_runs()` parses `parse_markdown_runs()` and sets `run.font.italic = is_italic`, combining with `run.font.bold = is_bold or is_title`.
   - **PDF (`pdf_renderer.py`)**: Renders directly from HTML, preserving font styling.

### Rationale
- Authors can freely emphasize, annotate translations, or format secondary terms in card titles without markdown syntax being stripped.
- Preserves full tri-format visual consistency with minimal, non-invasive code changes.

---

## ADR-018: Configurable Presentation Bullet Styles (chevron, editorial, refined)

### Context
Following review of PISA slide mockups, the user requested configurable bullet styles with `chevron` as the default alongside `editorial` and `refined`:
> *"make it an option: editorial, refined, chevron (default)"*

Previously:
- Card descriptions containing bullet items (`- item`) were rendered as unstructured text paragraphs with literal `- ` hyphens joined by `<br/>`.
- Standard list slides were hardcoded to solid black/accent circles (`• `).

### Decision
1. **Model & Theme Integration (`models.py`, `theme_engine.py`, `schema.json`)**:
   - Added `BulletStyle` enum: `CHEVRON = "chevron"`, `EDITORIAL = "editorial"`, `REFINED = "refined"`.
   - Added `bullet_style: BulletStyle = BulletStyle.CHEVRON` to `ThemeConfig`.
   - Updated `schema.json` to validate an optional top-level `"bullet_style"` property in themes. This is the only location; `styles.bullet_style` is not accepted.
   - `theme_generator.SYSTEM_PROMPT` and `THEME_PROMPT.md` list `bullet_style`, and `--ai-theme` output falls back to `chevron` (and archetype `cards`) when the model returns an invalid value.
2. **CLI Parameterization (`cli.py`)**:
   - Added `--bullet-style` (alias `--bullets`) supporting `chevron`, `editorial`, `refined`.
   - CLI defaults to theme specification (or `chevron` if theme does not specify). CLI flag overrides theme default.
3. **Tri-Format Implementation**:
   - **HTML (`html_renderer.py`)**:
     - `_render_card_description_html()` parses bullet lines in cards into structured `<ul class="card-bullets"><li>...</li></ul>`.
     - `_build_bullet_css()` injects responsive, density-scaled CSS pseudo-element markers (`›`, `–`, or `•`) in the theme's accent color (`var(--accent)`).
     - Standard `.content-list li:not(.task-item)` bullet markers also synchronize with the selected bullet style, so plain items in a mixed task list keep their bullet (as in PPTX).
   - **PowerPoint (`pptx_renderer.py`)**:
     - `_render_card_description_pptx()` formats bullet lines in card text frames with accent-colored bullet runs (`› `, `– `, `• `) and clean line spacing.
     - Standard slide lists apply matching accent bullet markers.
   - **PDF (`pdf_renderer.py`)**: Vector PDF rendered from HTML inherits identical styling.

### Rationale
- Provides cohesive, publication-quality bullet styling across all presentations.
- Default `chevron` gives high visual energy and reading momentum, while `editorial` provides dignified literary quietness and `refined` offers classical geometric order.

---

## ADR-019: Automatic Arrow Replacement (`->` to `→`) with Theme Color Styling

### Context
Slide titles, card titles, bullet lists, and paragraphs frequently use `->` as transition indicators (e.g. `# Tárgyi tudás -> Kompetencia *(fejtudás -> kéztudás)*`).
The user requested:
> *"a -> karaktereket nyilra cserelje, ismet commit (nyil az temaszin)"*
*(replace `->` characters with an arrow, arrow in theme color)*

Previously:
- `->` was rendered as raw ASCII characters (`-` followed by `>`).
- Slide titles stripped inline formatting (such as `*italic*` or `_italic_`), flattening rich titles into plain text.

### Decision
1. **Preserve Inline Formatting in Slide Titles (`generator/parser.py`)**:
   - Updated heading regex parsing to preserve inline markdown (italic, bold, code, arrows) in `slide.title`, paralleling the earlier card title enhancement (ADR-017).
2. **Inline Arrow Tokenization & Recursive Markdown (`generator/markdown_utils.py`)**:
   - Added `(?P<arrow>(?<![<!-])(?:-->|->)|→)` to `INLINE_TOKEN_RE`.
   - Enabled recursive inline markdown parsing inside formatting tokens (`*italic*`, `**bold**`, `~~strike~~`, `==highlight==`, `^sup^`, `~sub~`), allowing arrows inside italic parentheticals (e.g. `*(fejtudás -> kéztudás)*`) to be recognized and styled appropriately.
   - Code spans (`` `code` ``) and code blocks remain completely unaffected.
   - `strip_markdown()` converts `->` and `-->` to the clean Unicode character `→` for plain text outputs and window titles.
3. **Tri-Format Parity**:
   - **HTML (`html_renderer.py`)**: Renders `<span class="md-arrow">→</span>` with CSS `color: var(--accent); font-style: normal; font-weight: 700; display: inline-block; padding: 0 0.08em;`.
   - **PowerPoint (`pptx_renderer.py`)**: `_add_formatted_runs()` checks `item.is_arrow` and generates native PowerPoint runs with `font.color.rgb = accent_color` and `font.bold = True`. All slide renderers pass `accent_color=accent_rgb`.
   - **PDF (`pdf_renderer.py`)**: Inherits HTML styling directly with pixel-perfect accent-colored vector arrows.

### Rationale
- Elevates typography from raw ASCII code conventions (`->`) to typographic presentation arrows (`→`) highlighted in the theme's signature accent color.
- Respects code blocks and inline code literals without unintended mutations.

---

## ADR-020: Typographic Character Midline Vertical Centering for Arrows and Bullets

### Context
User observed that both arrows and bullet markers were not centered on the text character line:
> *"bullet meg nyil az miert nem a karaktervonal kozepen van"*
*(Why aren't bullet and arrow in the middle of character line?)*

Investigation revealed:
1. **Arrow Baseline Sagging**: `.md-arrow` was `display: inline-block` with default `vertical-align: baseline`. The Unicode arrow glyph (`→`) rests on the font baseline, causing the arrow shaft to sit below the optical midline (x-height / cap-height center) of uppercase and lowercase letters.
2. **Bullet Sagging**: Bullet markers (`::before`) used hardcoded pixel offsets (`top: 8px`, `top: 10px`, `top: 12px`, and density tier rules with `top: 15px` / `top: 18px`). Because these pixel offsets did not scale with font sizes and line heights, bullets hung noticeably below the first line's visual center.
3. **Card Heading Parsing Ambiguity**: In `parser.py`, fallback plain slide title extraction did not blacklist `#` prefixes, causing `### Card Heading` on slide 6 to be mistakenly consumed as a standalone slide title.

### Decision
1. **Arrow Optical Midline Lift (`html_renderer.py`)**:
   - Added `vertical-align: 0.12em;` to `.md-arrow`. This shifts the arrow shaft upward into the visual character midline across all font sizes.
2. **Bullet Markers in the Text Flow (`html_renderer.py`)**:
   - The first attempt (flex box with `height: 1.5em`, an enlarged marker `font-size`, and `translateY` fudges per style) still sagged 2–3 px on 22 px / 18 px card bullets: the `em` resolved against the enlarged marker, and the box never followed the per-tier line heights (1.6/1.55/1.5 for lists, 1.5/1.45/1.4 for card bullets).
   - Markers are now inline-block `::before` elements in the normal text flow, hung into the li's left padding with `margin-left: calc(L - var(--bullet-indent))` and a matching negative `margin-right`. Density tiers set `--bullet-indent` instead of `padding-left`.
   - Chevron and en-dash keep the li's font-size and line-height, so they share the first line's baseline; they are enlarged with `transform: scale(1.15)` / `scale(1.05)`, which does not affect layout.
   - The refined dot uses `vertical-align: middle` (baseline + half the x-height, i.e. the x-height midline by CSS definition), sized by a per-tier `--bullet-dot` variable (9/8/7 px).
   - No per-tier or per-style vertical offsets remain. Measured in headless Chromium: marker centre within 1 px of the x-height midline for every style, tier, list type and bundled font.
3. **Card Heading Title Disambiguation (`parser.py`)**:
   - Added `"#"` to excluded prefixes in `first_s.startswith(...)` during candidate title selection, ensuring card headings (`### `) are preserved as card components.

### Rationale
- Guarantees visual harmony: arrows and bullet markers sit on the horizontal axis of text.
- Multi-line wrapped bullet items remain anchored to the first line's midline.
- Maintains Tri-Format parity across HTML and vector PDF.

---

## ADR-021: Plain-Text Deck Title and Markup-Safe Card Title Extraction

### Context
ADR-017 and ADR-019 keep inline markdown in card titles and slide headings. Several code paths still assumed plain text, which made literal markdown show up on slides:
- Card titles demoted back into list items were wrapped in `**` again (`****Tri-Format paritás****`).
- The deck title (category label on every slide, title pill, `<title>`, PPTX badges) showed raw `**`/`->`.
- `- **Kulcs:** érték` split at the colon inside the bold marker, giving the title `**Kulcs`.
- `.rstrip(":")` missed colons inside emphasis (`_Részei:_`).
- Multi-line HTML comments inside card bodies leaked onto slides, with `-->` turned into an arrow.

### Decision
1. `PresentationData.title` is plain text (`strip_markdown` of the title slide heading); slide headings keep their markdown. HTML escapes it everywhere, including `<title>`.
2. Card titles are split from bullets by first matching a leading emphasis marker that contains the colon (`**T:**`, `__T:__`, `*T:*`, `_T:_`), otherwise at the first colon outside any inline token (code, links, raw URLs, emphasis). The title keeps its markup.
3. A single `_strip_trailing_colon` helper removes trailing colons before or after closing emphasis markers at every title site.
4. Demoting a card into a list item wraps the title in `**` only when it has no markup of its own.
5. HTML comments outside fenced code are removed in the parser; the inline comment token also matches across newlines.
6. Link text is parsed recursively in both renderers (`parse_markdown_runs` and `render_markdown_html`); HTML renders link text without link tokens so anchors never nest.

### Rationale
Text that is shown as markdown is rendered as markdown, and text used as a plain label is stripped once at the source, so the three formats can't drift apart.








