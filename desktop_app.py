"""PSO HLS Explorer — desktop app.

    .venv/bin/python desktop_app.py          (macOS / Linux)
    .venv\\Scripts\\python desktop_app.py      (Windows)
"""
import sys

from gui.app import main

if __name__ == "__main__":
    sys.exit(main())
