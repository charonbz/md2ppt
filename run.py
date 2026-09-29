#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# Self-bootstrap virtualenv if available
ROOT_DIR = Path(__file__).parent.resolve()
VENV_PYTHON = ROOT_DIR / ".venv" / "bin" / "python"

if VENV_PYTHON.exists() and sys.executable != str(VENV_PYTHON):
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

from generator.cli import main

if __name__ == "__main__":
    sys.exit(main())
