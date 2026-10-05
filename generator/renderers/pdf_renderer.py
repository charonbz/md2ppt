import subprocess
import shutil
from pathlib import Path


CHROME_CANDIDATES = [
    "google-chrome-stable",
    "google-chrome",
    "chromium",
    "chromium-browser",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
]


def find_chrome_binary(purpose: str) -> str:
    """Returns the first Chrome/Chromium executable found in PATH; raises if none is installed."""
    for candidate in CHROME_CANDIDATES:
        found = shutil.which(candidate)
        if found:
            return found
    raise RuntimeError(f"Google Chrome or Chromium is required to {purpose}, but was not found in PATH.")


def render_pdf_presentation(html_path: Path, dist_dir: Path) -> Path:
    dist_dir.mkdir(parents=True, exist_ok=True)
    pdf_out = dist_dir / "presentation.pdf"

    chrome_bin = find_chrome_binary("export PDF")

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
