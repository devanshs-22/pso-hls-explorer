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
    """Do all six steps with a sample, open every output window, export, then quit.
    Every step is logged to selftest.txt; pop-ups are logged instead of waiting for a click,
    and a watchdog ends the test after 3 minutes so a build machine can never hang on it."""
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    def log(msg):
        _report(out_dir, msg, append=True)

    QMessageBox.warning = staticmethod(lambda parent, title, text, *a, **k:
                                       log(f"POP-UP '{title}': {text}") or QMessageBox.StandardButton.Ok)
    QMessageBox.information = QMessageBox.critical = QMessageBox.warning
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QMessageBox.exec = lambda self: 0
    QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: out_dir)
    QTimer.singleShot(180_000, lambda: (log("SELFTEST TIMEOUT after 3 minutes"), app.exit(2)))
    try:
        steps = [("1 load DFG", lambda: win.load_dfg(sample="DWT")),
                 ("2 load library", lambda: win.load_lib(sample=True)),
                 ("3 run PSO", win.run_pso), ("4 schedule", win.make_schedule),
                 ("5 RAT", win.make_rat), ("6 cost", win.compute_cost)]
        for n, (name, act) in enumerate(steps, 1):
            act()
            assert n in win.s.done, f"step {name} did not finish"
            log(f"step {name}: ok")
        for key in ("dfg", "lib", "explore", "conv", "compare", "trade", "sched", "rat", "mux", "cost"):
            win.open_output(key)
            assert key in win.open_windows, f"window {key} did not open"
            log(f"window {key}: ok")
        win.export()
        assert os.path.exists(os.path.join(out_dir, "DWT_PSO_results", "summary.md")), "export missing"
        log("export: ok")
        log("SELFTEST OK")
        app.exit(0)
    except Exception:
        import traceback
        log("SELFTEST FAILED\n" + traceback.format_exc())
        app.exit(1)


def _report(out_dir, text, append=False):
    if sys.stdout:                                   # None in a windowed Windows build
        print(text, flush=True)
    with open(os.path.join(out_dir, "selftest.txt"), "a" if append else "w", encoding="utf-8") as f:
        f.write(text + "\n")
