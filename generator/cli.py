import argparse
import sys
import http.server
import socketserver
import socket
import os
from pathlib import Path

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

    # Load theme & archetype
    try:
        theme = load_theme(args.theme, archetype_override=args.archetype)
        override_note = f" (overridden via CLI)" if args.archetype else ""
        print(f"\n🎨 Applied theme: {theme.name} [{theme.id}]")
        print(f"🏛️ Applied archetype: {theme.archetype.value}{override_note}")
    except Exception as e:
        print(f"❌ Error loading theme: {e}", file=sys.stderr)
        return 1

    # Parse slides
    print(f"📖 Reading slides from: {slides_file}...")
    pres = parse_slides_file(slides_file)
    print(f"   ├─ Title: {pres.title}")
    print(f"   └─ Total slides: {len(pres.slides)}")
    for s in pres.slides:
        audio_str = f"[Audio: {s.audio_filename}]" if s.audio_filename else "[No audio]"
        print(f"      • Slide {s.index}: {s.title} {audio_str}")

    dist_dir = source_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    requested_formats = [f.strip().lower() for f in args.format.split(",")]
    generate_all = "all" in requested_formats

    # Render HTML
    html_path = None
    if generate_all or "html" in requested_formats or "pdf" in requested_formats:
        print(f"\n🌐 Generating Web presentation...")
        html_path = render_html_presentation(pres, theme, dist_dir)
        print(f"   ✅ Created: {html_path}")

    # Render PPTX
    if generate_all or "pptx" in requested_formats:
        print(f"\n📊 Generating PowerPoint (PPTX)...")
        pptx_path = render_pptx_presentation(pres, theme, dist_dir)
        print(f"   ✅ Created: {pptx_path}")

    # Render PDF
    if generate_all or "pdf" in requested_formats:
        print(f"\n📄 Generating Vector 16:9 PDF...")
        try:
            pdf_path = render_pdf_presentation(html_path, dist_dir)
            print(f"   ✅ Created: {pdf_path}")
        except Exception as e:
            print(f"   ⚠️ PDF generation failed: {e}", file=sys.stderr)

    print(f"\n🎉 Generation complete! Artifacts available in '{dist_dir}':\n")
    for f in sorted(dist_dir.iterdir()):
        size_kb = f.stat().st_size / 1024
        print(f"   📄 {f.name:<24} ({size_kb:8.1f} KB)")
    print()

    # Serve if requested
    if args.serve:
        port = args.serve
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
            if server:
                server.server_close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
