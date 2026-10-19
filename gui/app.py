"""Start the desktop app."""
import os
import sys

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from . import theme
from .main_window import MainWindow


def make_icon_pixmap(size=512):
    """App icon: a blue rounded square with a small swarm (drawn, so no image file is needed)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 32
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(theme.ACCENT))
    p.drawRoundedRect(QRectF(1 * s, 1 * s, 30 * s, 30 * s), 7 * s, 7 * s)
    p.setBrush(QColor("#ffffff"))
    for x, y, r in ((10, 11, 3), (21, 9, 3), (24, 20, 2.2)):
        p.drawEllipse(QRectF((x - r) * s, (y - r) * s, 2 * r * s, 2 * r * s))
    p.setBrush(QColor(theme.MULT))
    p.drawEllipse(QRectF(12 * s, 17 * s, 9 * s, 9 * s))
    p.end()
    return pm


def main():
    QApplication.setApplicationName("PSO HLS Explorer")
    QApplication.setOrganizationName("PSO HLS Explorer")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(theme.palette())
    app.setFont(theme.base_font())
    app.setStyleSheet(theme.STYLESHEET)
    app.setWindowIcon(QIcon(make_icon_pixmap()))
    win = MainWindow()
    win.show()
    if os.environ.get("PSO_HLS_SELFTEST"):          # used to check a packaged build
        out = os.environ["PSO_HLS_SELFTEST"]
        _report(out, "SELFTEST STARTED")
        QTimer.singleShot(300, lambda: _selftest(app, win, out))
    return app.exec()


def _selftest(app, win, out_dir):
    """Do all six steps with a sample, open every output window, export, then quit."""
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    try:
        win.load_dfg(sample="DWT")
        win.load_lib(sample=True)
        win.run_pso()
        win.make_schedule()
        win.make_rat()
        win.compute_cost()
        assert win.s.done == {1, 2, 3, 4, 5, 6}, win.s.done
        for key in ("dfg", "lib", "explore", "conv", "compare", "trade", "sched", "rat", "mux", "cost"):
            win.open_output(key)
            assert key in win.open_windows, key
        QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: out_dir)
        QMessageBox.exec = lambda self: 0
        win.export()
        assert os.path.exists(os.path.join(out_dir, "DWT_PSO_results", "summary.md"))
        _report(out_dir, "SELFTEST OK")
        app.exit(0)
    except Exception:
        import traceback
        _report(out_dir, "SELFTEST FAILED\n" + traceback.format_exc())
        app.exit(1)


def _report(out_dir, text):
    print(text, flush=True)
    with open(os.path.join(out_dir, "selftest.txt"), "w") as f:
        f.write(text + "\n")
