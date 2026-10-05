# Guidelines and Rules for AI Coding Agents (AGENTS.md)

This file contains mandatory guidelines and rules for all AI coding assistants (Agents) working on the **slideshowGenerator** codebase.

---

> [!CAUTION]
> ### 🚨 MANDATORY DOCUMENTATION MAINTENANCE
> **Every AI agent must keep the documentation in the `docs/` folder completely up to date!**
> 
> If you make any changes to the system:
> 1. Add new features or modify existing ones,
> 2. Change CLI parameters, data models (`models.py`), or parser behavior,
> 3. Modify the styling engine (`theme_engine.py`) or renderers (`renderers/`),
> 4. Fix bugs or introduce new formats,
> 
> **YOU ARE STRICTLY REQUIRED TO IMMEDIATELY UPDATE:**
> * [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (architecture, components, data flow), AND
> * [`docs/DECISIONS.md`](docs/DECISIONS.md) (documenting rationale as an ADR or decision entry).
> 
> **NEVER deliver code that diverges from the documentation or makes it obsolete!**

---

## 🌐 Language Policy (Code & Documentation in English)

* **Codebase & Documentation:** All source code, variable names, functions, comments, docstrings, CLI parameters, console logs, documentation (`docs/`, `README.md`, `AGENTS.md`), and Git commit messages MUST be written in **English**.
* **User Content & Prompts:** Presentation slides (`slides.md`) and user prompts are typically in **Hungarian** (or any user language). The parser, theme generator, and presentation layouts must fully accommodate Hungarian characters (accents, UTF-8), Hungarian keywords, and multilingual slide contents.

---

## 🏛️ Core Architectural Principles

1. **Tri-Format Principle (PPTX, HTML, PDF):**
   * All modifications must preserve the three first-class output formats.
   * If a new visual feature or layout is introduced, it must be consistently implemented across Web (`html_renderer.py`), PowerPoint (`pptx_renderer.py`), and PDF (`pdf_renderer.py`).

2. **Standalone Web Player (Zero-Dependency):**
   * `index.html` must remain fully operational offline without any network connectivity or external servers.
   * Audio files must be embedded directly into HTML as Base64 data streams (`data:audio/mpeg;base64,...`) to prevent `file:///` security sandbox blocks and relative path failures.
   * The `ffmpeg`-based MP3 transcoding and multi-source fallback mechanism must be preserved.

3. **Declarative JSON Themes:**
   * Presentation styling must never be hardcoded into the generation logic.
   * Themes are controlled via `generator/themes/*.json` files and validated by `schema.json`.
   * AI-powered style generation (`--ai-theme`) must remain supported, accepting both English and Hungarian prompt descriptions.

4. **Instant Port Reuse:**
   * The built-in web server must use `ReusableTCPServer` (`SO_REUSEADDR` and `SO_REUSEPORT`) so that upon `Ctrl + C` termination, the port is freed immediately without OS socket timeouts.

5. **Version Control Hygiene:**
   * The `dist/` subfolders are generated artifacts and **must never be committed to Git** (enforced via `.gitignore`).
   * The `pisa` directory serves as a living reference example; its `slides.md` must be preserved (narration audio stays local and is not committed).

---

## 🧪 Mandatory Verification Steps Before Concluding a Task

Before completing your turn, execute the following verification suite:

```bash
# 1. Verify generation
./run.py pisa

# 2. Verify PPTX structure and embedded media
.venv/bin/python -c "from pptx import Presentation; prs = Presentation('pisa/dist/presentation.pptx'); assert len(prs.slides) == 7"

# 3. Verify theme listing and generation with an alternative theme
./run.py --list-themes
./run.py pisa --theme dark_mode

# 4. Verify documentation maintenance
git status
```
