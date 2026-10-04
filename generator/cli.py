import argparse
import sys
import http.server
import socketserver
import socket
import os
import time
import threading
from pathlib import Path
from typing import Optional, Dict

from .parser import parse_slides_file
from .theme_engine import list_available_themes, list_available_archetypes, load_theme, DEFAULT_THEME_ID
from .theme_generator import generate_ai_theme
from .renderers import render_html_presentation, render_pptx_presentation, render_pdf_presentation


class ReusableTCPServer(socketserver.TCPServer):
    """TCPServer that enables SO_REUSEADDR and SO_REUSEPORT for instant port release."""
    allow_reuse_address = True

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        super().server_bind()


def build_presentation(
    source_dir: Path,
    theme_name: str = DEFAULT_THEME_ID,
    archetype_override: Optional[str] = None,
    bullet_style_override: Optional[str] = None,
    format_str: str = "all",
    verbose: bool = True,
) -> bool:
    """Renders the presentation across requested formats (HTML, PPTX, PDF)."""
    slides_file = source_dir / "slides.md"
    if not slides_file.exists():
        print(f"❌ Error: 'slides.md' not found in directory: {slides_file}", file=sys.stderr)
        return False

    # Load theme & archetype & bullet style
    try:
        # ponytail: pass bullet_style_override to load_theme
        theme = load_theme(
            theme_name,
            archetype_override=archetype_override,
            bullet_style_override=bullet_style_override
        )
        if verbose:
            override_note = " (overridden via CLI)" if archetype_override else ""
            bullet_note = " (overridden via CLI)" if bullet_style_override else ""
            print(f"\n🎨 Applied theme: {theme.name} [{theme.id}]")
            print(f"🏛️ Applied archetype: {theme.archetype.value}{override_note}")
            print(f"🔸 Applied bullet style: {theme.bullet_style.value}{bullet_note}")
    except Exception as e:
        print(f"❌ Error loading theme: {e}", file=sys.stderr)
        return False

    # Parse slides
    try:
        if verbose:
            print(f"📖 Reading slides from: {slides_file}...")
        pres = parse_slides_file(slides_file)
        if verbose:
            print(f"   ├─ Title: {pres.title}")
            print(f"   └─ Total slides: {len(pres.slides)}")
            for s in pres.slides:
                audio_str = f"[Audio: {s.audio_filename}]" if s.audio_filename else "[No audio]"
                print(f"      • Slide {s.index}: {s.title} {audio_str}")
    except Exception as e:
        print(f"❌ Error parsing slides: {e}", file=sys.stderr)
        return False

    dist_dir = source_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    requested_formats = [f.strip().lower() for f in format_str.split(",")]
    generate_all = "all" in requested_formats

    # Render HTML
    html_path = None
    if generate_all or "html" in requested_formats or "pdf" in requested_formats:
        if verbose:
            print(f"\n🌐 Generating Web presentation...")
        try:
            html_path = render_html_presentation(pres, theme, dist_dir)
            if verbose:
                print(f"   ✅ Created: {html_path}")
            else:
                print(f"   ├─ HTML : {html_path.name}")
        except Exception as e:
            print(f"   ❌ HTML generation failed: {e}", file=sys.stderr)
            return False

    # Render PPTX
    if generate_all or "pptx" in requested_formats:
        if verbose:
            print(f"\n📊 Generating PowerPoint (PPTX)...")
        try:
            pptx_path = render_pptx_presentation(pres, theme, dist_dir)
            if verbose:
                print(f"   ✅ Created: {pptx_path}")
            else:
                print(f"   ├─ PPTX : {pptx_path.name}")
        except Exception as e:
            print(f"   ❌ PPTX generation failed: {e}", file=sys.stderr)
            return False

    # Render PDF
    if generate_all or "pdf" in requested_formats:
        if verbose:
            print(f"\n📄 Generating Vector 16:9 PDF...")
        try:
            pdf_path = render_pdf_presentation(html_path, dist_dir)
            if verbose:
                print(f"   ✅ Created: {pdf_path}")
            else:
                print(f"   ├─ PDF  : {pdf_path.name}")
        except Exception as e:
            print(f"   ⚠️ PDF generation failed: {e}", file=sys.stderr)

    if verbose:
        print(f"\n🎉 Generation complete! Artifacts available in '{dist_dir}':\n")
        for f in sorted(dist_dir.iterdir()):
            size_kb = f.stat().st_size / 1024
            print(f"   📄 {f.name:<24} ({size_kb:8.1f} KB)")
        print()

    return True


def get_source_fingerprint(source_dir: Path, theme_name: str) -> Dict[Path, float]:
    """Collects modification timestamps for all relevant source files and theme."""
    fingerprint: Dict[Path, float] = {}

    if source_dir.exists() and source_dir.is_dir():
        dist_resolved = (source_dir / "dist").resolve()
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".") and (Path(root) / d).resolve() != dist_resolved
            ]
            for file in files:
                if file.startswith("."):
                    continue
                p = Path(root) / file
                try:
                    fingerprint[p] = p.stat().st_mtime
                except OSError:
                    pass

    # Track theme file if present in generator/themes/
    themes_dir = Path(__file__).parent / "themes"
    theme_file = themes_dir / f"{theme_name}.json"
    if theme_file.exists():
        try:
            fingerprint[theme_file] = theme_file.stat().st_mtime
        except OSError:
            pass

    return fingerprint


def watch_and_rebuild(
    source_dir: Path,
    theme_name: str,
    archetype_override: Optional[str],
    format_str: str,
    stop_event: threading.Event,
    poll_interval: float = 0.5,
    bullet_style_override: Optional[str] = None,
):
    """Background watcher that monitors source files and rebuilds the presentation on modification."""
    last_fingerprint = get_source_fingerprint(source_dir, theme_name)

    while not stop_event.is_set():
        stop_event.wait(poll_interval)
        if stop_event.is_set():
            break

        current_fingerprint = get_source_fingerprint(source_dir, theme_name)
        if current_fingerprint != last_fingerprint:
            changed_names = []
            for path, mtime in current_fingerprint.items():
                if path not in last_fingerprint or last_fingerprint[path] != mtime:
                    changed_names.append(path.name)
            for path in last_fingerprint:
                if path not in current_fingerprint:
                    changed_names.append(f"{path.name} (removed)")

            # Debounce briefly to allow multi-file saves or editor flushes
            stop_event.wait(0.3)
            if stop_event.is_set():
                break

            current_fingerprint = get_source_fingerprint(source_dir, theme_name)
            last_fingerprint = current_fingerprint

            changed_desc = ", ".join(changed_names[:3])
            if len(changed_names) > 3:
                changed_desc += f" and {len(changed_names) - 3} more"

            print(f"\n🔄 Detected change in [{changed_desc}]. Rebuilding presentation...")
            start_time = time.time()
            try:
                success = build_presentation(
                    source_dir=source_dir,
                    theme_name=theme_name,
                    archetype_override=archetype_override,
                    bullet_style_override=bullet_style_override,
                    format_str=format_str,
                    verbose=False,
                )
                elapsed = time.time() - start_time
                if success:
                    print(f"✅ Rebuild completed in {elapsed:.2f}s! Refresh browser to view changes.")
                else:
                    print(f"⚠️ Rebuild completed with warnings in {elapsed:.2f}s.")
            except Exception as e:
                print(f"❌ Rebuild error: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Slideshow Generator - Build PPTX, Web HTML, and Vector PDF presentations from Markdown and audio."
    )

    parser.add_argument(
        "slideshow_dir",
        nargs="?",
        type=str,
        help="The source slideshow directory (e.g. slideshow_1) containing slides.md."
    )

    parser.add_argument(
        "--theme",
        type=str,
        default=DEFAULT_THEME_ID,
        help=f"Visual color theme to apply (default: {DEFAULT_THEME_ID})."
    )

    parser.add_argument(
        "--archetype",
        type=str,
        choices=["editorial", "cards", "neubrutalism", "terminal", "minimal", "corporate"],
        help="Override the visual structural archetype (editorial, cards, neubrutalism, terminal, minimal, corporate)."
    )

    parser.add_argument(
        "--bullet-style",
        "--bullets",
        type=str,
        choices=["chevron", "editorial", "refined"],
        help="Bullet point style: chevron (default: ›), editorial (–), refined (•)."
    )

    parser.add_argument(
        "--list-themes",
        action="store_true",
        help="List all available presentation themes and their default archetypes."
    )

    parser.add_argument(
        "--list-archetypes",
        action="store_true",
        help="List all 6 visual structural archetypes with their styling characteristics."
    )

    parser.add_argument(
        "--ai-theme",
        type=str,
        metavar="DESCRIPTION",
        help="Generate a new theme using AI (or algorithmic palette synthesizer) based on a description."
    )

    parser.add_argument(
        "--format",
        type=str,
        default="all",
        help="Comma-separated formats to generate: all, pptx, html, pdf (default: all)."
    )

    parser.add_argument(
        "--serve",
        type=int,
        nargs="?",
        const=8080,
        metavar="PORT",
        help="Launch a local development web server on the specified port (default: 8080) to preview the slideshow."
    )

    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch source files for changes and automatically rebuild (active by default with --serve)."
    )

    parser.add_argument(
        "--no-watch",
        action="store_true",
        help="Disable automatic file watching when running --serve."
    )

    args = parser.parse_args()

    # 1. Handle archetype listing
    if args.list_archetypes:
        archetypes = list_available_archetypes()
        print("\n🏛️ Available visual archetypes (structural styling):")
        print("=" * 64)
        for a in archetypes:
            print(f" • {a['id']:<14} : {a['name']}")
            print(f"   ├─ Style    : {a['description']}")
            print(f"   └─ Best for : {a['best_for']}")
        print("=" * 64)
        print("💡 Use with: ./run.py <dir> --theme <theme> --archetype <archetype>\n")
        return 0

    # 2. Handle theme listing
    if args.list_themes:
        themes = list_available_themes()
        print("\n🎨 Available themes (color palettes):")
        print("=" * 64)
        for t in themes:
            arch_badge = f"[{t.get('archetype', 'cards')}]"
            print(f" • {t['id']:<18} {arch_badge:<14} : {t['name']}")
            if t['description']:
                print(f"   └─ {t['description']}")
        print("=" * 64)
        print("💡 Override structural style with: --archetype <name>\n")
        return 0

    # 3. Handle AI theme generation
    if args.ai_theme:
        print(f"\n✨ Generating new theme based on description: '{args.ai_theme}'...")
        out_path = generate_ai_theme(args.ai_theme)
        print(f"✅ New theme successfully created: {out_path}")
        print(f"👉 Usage: ./run.py {args.slideshow_dir or 'slideshow_1'} --theme {out_path.stem}\n")
        if not args.slideshow_dir:
            return 0

    if not args.slideshow_dir:
        parser.print_help()
        return 1

    source_dir = Path(args.slideshow_dir)
    if not source_dir.exists() or not source_dir.is_dir():
        print(f"❌ Error: Directory not found: {source_dir}", file=sys.stderr)
        return 1

    slides_file = source_dir / "slides.md"
    if not slides_file.exists():
        print(f"❌ Error: 'slides.md' not found in directory: {slides_file}", file=sys.stderr)
        return 1

    dist_dir = source_dir / "dist"

    # Initial build
    success = build_presentation(
        source_dir=source_dir,
        theme_name=args.theme,
        archetype_override=args.archetype,
        bullet_style_override=args.bullet_style,
        format_str=args.format,
        verbose=True,
    )
    if not success:
        return 1

    # Check if watching should be activated
    should_watch = (args.serve is not None and not args.no_watch) or args.watch

    # Standalone watch mode (without --serve)
    if args.watch and args.serve is None:
        print(f"👀 Watching '{source_dir}' for changes (theme: {args.theme}). Press Ctrl + C to stop.")
        stop_event = threading.Event()
        try:
            watch_and_rebuild(
                source_dir,
                args.theme,
                args.archetype,
                args.format,
                stop_event,
                bullet_style_override=args.bullet_style
            )
        except KeyboardInterrupt:
            print("\n🛑 Watcher stopped.")
        return 0

    # Serve if requested
    if args.serve is not None:
        port = args.serve
        stop_event = threading.Event()
        watcher_thread = None

        if should_watch:
            watcher_thread = threading.Thread(
                target=watch_and_rebuild,
                args=(source_dir, args.theme, args.archetype, args.format, stop_event),
                kwargs={"bullet_style_override": args.bullet_style},
                daemon=True,
            )
            watcher_thread.start()
            print(f"👀 Auto-rebuild active: watching '{source_dir}' for changes.")

        print(f"🚀 Starting development web server at http://localhost:{port}...")
        print("Press Ctrl + C to stop.")

        class DirectoryHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *handler_args, **handler_kwargs):
                super().__init__(*handler_args, directory=str(dist_dir.resolve()), **handler_kwargs)

        server = None
        try:
            server = ReusableTCPServer(("", port), DirectoryHandler)
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Web server stopped, port released immediately.")
        finally:
            stop_event.set()
            if server:
                server.server_close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
