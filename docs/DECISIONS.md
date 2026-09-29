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

