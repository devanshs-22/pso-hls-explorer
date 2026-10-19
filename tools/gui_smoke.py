"""Drive the desktop app without a screen: do all six steps, open every output window and
save a screenshot of each.   QT_QPA_PLATFORM=offscreen python tools/gui_smoke.py OUT_DIR [SAMPLE]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from gui import theme  # noqa: E402
from gui.app import make_icon_pixmap  # noqa: E402
from gui.main_window import MainWindow  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "smoke"
sample = sys.argv[2] if len(sys.argv) > 2 else "DCT_4pt"
os.makedirs(out, exist_ok=True)

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setPalette(theme.palette())
app.setFont(theme.base_font())
app.setStyleSheet(theme.STYLESHEET)
app.setWindowIcon(QIcon(make_icon_pixmap()))
QMessageBox.warning = staticmethod(lambda *a, **k: print("WARNING DIALOG:", a[1:]))  # never block

win = MainWindow()
win.resize(1440, 900)
win.show()


def shot(widget, name):
    app.processEvents()
    widget.grab().save(os.path.join(out, name))
    print("saved", name)


steps = [
    ("00_start.png", lambda: None),
    ("01_after_dfg.png", lambda: win.load_dfg(sample=sample)),
    ("02_after_lib.png", lambda: win.load_lib(sample=True)),
    ("03_after_pso.png", lambda: win.run_pso()),
    ("04_after_schedule.png", lambda: win.make_schedule()),
    ("05_after_rat.png", lambda: win.make_rat()),
    ("06_after_cost.png", lambda: win.compute_cost()),
]
for name, act in steps:
    act()
    shot(win, name)
print("done steps:", sorted(win.s.done))

for key in ["dfg", "lib", "explore", "conv", "compare", "trade", "sched", "rat", "mux", "cost"]:
    win.open_output(key)
    w = win.open_windows.get(key)
    if w is None:
        print("FAILED to open", key)
        continue
    if key == "explore":                       # step a few frames into the replay
        w.pause()
        for _ in range(5):
            w.goto(w.i + 1, animate=False)
        w.map.t = 1.0
    shot(w, f"win_{key}.png")
    if key == "explore":
        w.goto(len(w.frames) - 1, animate=False)
        shot(w, "win_explore_done.png")
win.show_help()
shot(win.open_windows["help"], "win_help.png")
QTimer.singleShot(0, app.quit)
app.exec()
print("SMOKE OK")
