"""Render the app icon to assets/icon.png, assets/icon.ico (Windows) and assets/icon.icns (macOS)."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtGui import QGuiApplication  # noqa: E402

from gui.app import make_icon_pixmap  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")


def main():
    app = QGuiApplication(sys.argv)  # noqa: F841 (needed for QPixmap)
    os.makedirs(ASSETS, exist_ok=True)
    png = os.path.join(ASSETS, "icon.png")
    make_icon_pixmap(1024).save(png)
    from PIL import Image
    Image.open(png).save(os.path.join(ASSETS, "icon.ico"),
                         sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    if sys.platform == "darwin":
        iconset = os.path.join(ASSETS, "icon.iconset")
        os.makedirs(iconset, exist_ok=True)
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                name = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
                make_icon_pixmap(size * scale).save(os.path.join(iconset, name))
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", os.path.join(ASSETS, "icon.icns")], check=True)
    print("icons written to", ASSETS)


if __name__ == "__main__":
    main()
