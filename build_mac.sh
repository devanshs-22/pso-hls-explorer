#!/bin/bash
# Build "PSO HLS Explorer.app" for macOS into dist/.  Run from the project folder:  ./build_mac.sh
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt -r requirements-app.txt
.venv/bin/python tools/make_icons.py
.venv/bin/pyinstaller --noconfirm --clean --windowed \
  --name "PSO HLS Explorer" \
  --icon assets/icon.icns \
  --osx-bundle-identifier com.psohls.explorer \
  --add-data "inputs:inputs" \
  --exclude-module tkinter \
  desktop_app.py
echo
echo "Built: dist/PSO HLS Explorer.app   (open it with:  open \"dist/PSO HLS Explorer.app\")"
