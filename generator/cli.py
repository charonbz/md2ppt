import argparse
import sys
import http.server
import socketserver
import socket
import os
from pathlib import Path

from .parser import parse_slides_file
from .theme_engine import list_available_themes, load_theme, DEFAULT_THEME_ID
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
        description="Slideshow Generator - Készíts PPTX, Webes HTML és PDF prezentációkat Markdownból és audióból."
    )

    parser.add_argument(
        "slideshow_dir",
        nargs="?",
        type=str,
        help="A prezentáció forrásmappája (pl. slideshow_1), amely tartalmazza a slides.md fájlt."
    )

    parser.add_argument(
        "--theme",
        type=str,
        default=DEFAULT_THEME_ID,
        help=f"Alkalmazandó vizuális téma neve (alapértelmezett: {DEFAULT_THEME_ID})."
    )

    parser.add_argument(
        "--list-themes",
        action="store_true",
        help="Elérhető témák listázása."
    )

    parser.add_argument(
        "--ai-theme",
        type=str,
        metavar="DESCRIPTION",
        help="Új téma generálása mesterséges intelligenciával (vagy stílusszintetizálóval) a megadott leírás alapján."
    )

    parser.add_argument(
        "--format",
        type=str,
        default="all",
        help="Generálandó formátumok (vesszővel elválasztva: all, pptx, html, pdf. Alapértelmezett: all)."
    )

    parser.add_argument(
        "--serve",
        type=int,
        nargs="?",
        const=8080,
        metavar="PORT",
        help="A generálás után indítson egy helyi webszervert a megadott porton (alapértelmezett: 8080) a webes diavetítés megtekintéséhez."
    )

    args = parser.parse_args()

    # 1. Handle theme listing
    if args.list_themes:
        themes = list_available_themes()
        print("\n🎨 Elérhető témák:")
        print("--------------------------------------------------")
        for t in themes:
            print(f" • {t['id']:<18} : {t['name']}")
            if t['description']:
                print(f"   └─ {t['description']}")
        print("--------------------------------------------------\n")
        return 0

    # 2. Handle AI theme generation
    if args.ai_theme:
        print(f"\n✨ Új téma generálása leírás alapján: '{args.ai_theme}'...")
        out_path = generate_ai_theme(args.ai_theme)
        print(f"✅ Új téma sikeresen létrehozva: {out_path}")
        print(f"👉 Használat: python run.py {args.slideshow_dir or 'slideshow_1'} --theme {out_path.stem}\n")
        if not args.slideshow_dir:
            return 0

    if not args.slideshow_dir:
        parser.print_help()
        return 1

    source_dir = Path(args.slideshow_dir)
    if not source_dir.exists() or not source_dir.is_dir():
        print(f"❌ Hiba: A megadott mappa nem található: {source_dir}", file=sys.stderr)
        return 1

    slides_file = source_dir / "slides.md"
    if not slides_file.exists():
        print(f"❌ Hiba: Nem található 'slides.md' a mappában: {slides_file}", file=sys.stderr)
        return 1

    # Load theme
    try:
        theme = load_theme(args.theme)
        print(f"\n🎨 Alkalmazott téma: {theme.name} ({theme.id})")
    except Exception as e:
        print(f"❌ Hiba a téma betöltésekor: {e}", file=sys.stderr)
        return 1

    # Parse slides
    print(f"📖 Diák beolvasása: {slides_file}...")
    pres = parse_slides_file(slides_file)
    print(f"   ├─ Főcím: {pres.title}")
    print(f"   └─ Diák száma: {len(pres.slides)}")
    for s in pres.slides:
        audio_str = f"[Audió: {s.audio_filename}]" if s.audio_filename else "[Nincs audió]"
        print(f"      • Dia {s.index}: {s.title} {audio_str}")

    dist_dir = source_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    requested_formats = [f.strip().lower() for f in args.format.split(",")]
    generate_all = "all" in requested_formats

    # Render HTML
    html_path = None
    if generate_all or "html" in requested_formats or "pdf" in requested_formats:
        print(f"\n🌐 Webes prezentáció generálása...")
        html_path = render_html_presentation(pres, theme, dist_dir)
        print(f"   ✅ Elkészült: {html_path}")

    # Render PPTX
    if generate_all or "pptx" in requested_formats:
        print(f"\n📊 PowerPoint (PPTX) generálása...")
        pptx_path = render_pptx_presentation(pres, theme, dist_dir)
        print(f"   ✅ Elkészült: {pptx_path}")

    # Render PDF
    if generate_all or "pdf" in requested_formats:
        print(f"\n📄 Vektoros 16:9 PDF generálása...")
        try:
            pdf_path = render_pdf_presentation(html_path, dist_dir)
            print(f"   ✅ Elkészült: {pdf_path}")
        except Exception as e:
            print(f"   ⚠️ PDF generálás sikertelen: {e}", file=sys.stderr)

    print(f"\n🎉 Sikeres generálás! A kimenetek a(z) '{dist_dir}' mappában találhatók:\n")
    for f in sorted(dist_dir.iterdir()):
        size_kb = f.stat().st_size / 1024
        print(f"   📄 {f.name:<24} ({size_kb:8.1f} KB)")
    print()

    # Serve if requested
    if args.serve:
        port = args.serve
        print(f"🚀 Webszerver indítása a http://localhost:{port} címen...")
        print("Megszakítás: Ctrl + C")

        class DirectoryHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *handler_args, **handler_kwargs):
                super().__init__(*handler_args, directory=str(dist_dir.resolve()), **handler_kwargs)

        server = None
        try:
            server = ReusableTCPServer(("", port), DirectoryHandler)
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Webszerver azonnal leállítva, port azonnal felszabadítva.")
        finally:
            if server:
                server.server_close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
