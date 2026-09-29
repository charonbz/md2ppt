import subprocess
import shutil
from pathlib import Path


def render_pdf_presentation(html_path: Path, dist_dir: Path) -> Path:
    dist_dir.mkdir(parents=True, exist_ok=True)
    pdf_out = dist_dir / "presentation.pdf"

    # Find chrome or chromium executable
    chrome_bin = None
    for candidate in [
        "google-chrome-stable",
        "google-chrome",
        "chromium",
        "chromium-browser",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium"
    ]:
        found = shutil.which(candidate)
        if found:
            chrome_bin = found
            break

    if not chrome_bin:
        raise RuntimeError("Google Chrome or Chromium is required to export PDF, but was not found in PATH.")

    cmd = [
        chrome_bin,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_out.resolve()}",
        str(html_path.resolve())
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if not pdf_out.exists() or pdf_out.stat().st_size == 0:
        raise RuntimeError(f"PDF export failed: {result.stderr or result.stdout}")

    return pdf_out
