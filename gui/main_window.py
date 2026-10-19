"""Main window: INPUT PANEL (six locked-until-ready steps) · STATUS PANEL · OUTPUT PANEL."""
import os
import time
import traceback

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
                               QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from psodse.export import write_results
from psodse.report import design_report

from . import windows as W
from .session import SAMPLES, STEP_NAMES, Session, Settings
from .widgets import OutputButton, StatusTile, StepCard, button, label, repolish

NEXT_TEXT = {
    1: "<b>Next → Step 1:</b> load the application graph. Click <b>Load DFG file…</b> or pick a sample such as <b>DCT 4-point</b>.",
    2: "<b>Next → Step 2:</b> load the module library (the hardware units) for this application.",
    3: "<b>Next → Step 3:</b> choose the swarm sizes and click <b>Run PSO exploration</b>.",
    4: "<b>Next → Step 4:</b> generate the scheduled design. Tip: open <b>Watch PSO exploration</b> on the right to see how the swarm searched.",
    5: "<b>Next → Step 5:</b> generate the register allocation table (RAT).",
    6: "<b>Next → Step 6:</b> compute the area, latency and design cost.",
    None: "<b>All six steps are done ✓</b> — open any output on the right, or <b>Export all results</b> to a folder.",
}

# output button -> (label, tooltip, window class or action, step that unlocks it)
OUTPUTS = [
    ("Application", [
        ("dfg", "View data-flow graph (DFG)", "The application as a graph, plus its operation list", W.DfgWindow, 1),
        ("lib", "View module library", "Area, delay and availability of every hardware unit", W.LibraryWindow, 2),
    ]),
    ("PSO exploration", [
        ("explore", "Watch PSO exploration (animated)", "Replay how the particles searched the design space", W.ExplorationWindow, 3),
        ("conv", "View convergence graph", "Best design cost per iteration for every swarm size", W.ConvergenceWindow, 3),
        ("compare", "Compare swarm sizes (N = 3 · 5 · 7)", "Best design, iterations, convergence and exploration time per swarm size", W.CompareWindow, 3),
        ("trade", "View area–latency trade-off", "Every design's area against its latency, with the Pareto front", W.TradeoffWindow, 3),
    ]),
    ("Scheduling & registers", [
        ("sched", "View scheduled design", "Which operation runs in which clock cycle on which unit", W.ScheduleWindow, 4),
        ("rat", "View register allocation table (RAT)", "Which value each register holds in every control step", W.RatWindow, 5),
        ("mux", "View datapath interconnect", "Multiplexers and demultiplexers needed for unit and register reuse", W.InterconnectWindow, 5),
    ]),
    ("Results", [
        ("cost", "View area, latency & design cost", "Final metrics and the design-cost formula with numbers", W.CostWindow, 6),
        ("export", "Export all results…", "Save every chart, table and report into a folder", None, 6),
    ]),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PSO HLS Explorer — PSO-based architecture exploration for high-level synthesis")
        self.resize(1440, 900)
        self.setMinimumSize(1180, 720)
        self.s = Session()
        self.open_windows = {}
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._header())
        content = QVBoxLayout()
        content.setContentsMargins(18, 14, 18, 10)
        content.setSpacing(12)
        content.addWidget(self._next_bar())
        cols = QHBoxLayout()
        cols.setSpacing(14)
        cols.addWidget(self._input_panel(), 44)
        cols.addWidget(self._status_panel(), 24)
        cols.addWidget(self._output_panel(), 32)
        content.addLayout(cols, 1)
        self.log_box = QPlainTextEdit()
        self.log_box.setObjectName("Log")
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(92)
        content.addWidget(self.log_box)
        outer.addLayout(content, 1)
        outer.addWidget(self._footer())
        self.log("Welcome! Start with step 1 on the left. Every step unlocks the next one.")
        self.refresh()

    # ------------------------------------------------------------------ layout pieces
    def _header(self):
        h = QFrame()
        h.setObjectName("Header")
        lay = QHBoxLayout(h)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.addWidget(button("Read me!", "ReadMe", self.show_help, "How to use this tool"))
        lay.addSpacing(12)
        t = QVBoxLayout()
        t.setSpacing(0)
        t.addWidget(label("PSO HLS Explorer", "AppTitle"))
        t.addWidget(label("Particle-swarm based architecture exploration · scheduling · register allocation · area–latency trade-off",
                          "AppSub"))
        lay.addLayout(t, 1)
        lay.addWidget(button("Reset", "HeaderBtn", self.reset, "Start again from step 1"))
        return h

    def _footer(self):
        f = QFrame()
        f.setObjectName("Footer")
        lay = QHBoxLayout(f)
        lay.setContentsMargins(20, 7, 20, 7)
        lay.addStretch(1)
        lay.addWidget(label("<b>Made by</b> Devansh Singhal, Deepak Kumar, Dhristi, Kshaunish and Anshul Gupta",
                            "FooterText", rich=True))
        lay.addStretch(1)
        return f

    def _next_bar(self):
        self.next_frame = QFrame()
        self.next_frame.setObjectName("NextBar")
        lay = QHBoxLayout(self.next_frame)
        lay.setContentsMargins(14, 9, 14, 9)
        self.next_text = label("", "NextText", wrap=True, rich=True)
        lay.addWidget(self.next_text, 1)
        return self.next_frame

    def _panel(self, title, hint, scroll=False):
        """A white panel with a title. scroll=True puts the content in a scroll area so it never
        gets squashed on a small screen."""
        p = QFrame()
        p.setObjectName("Panel")
        lay = QVBoxLayout(p)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)
        lay.addWidget(label(title, "PanelTitle"))
        lay.addWidget(label(hint, "PanelHint", wrap=True))
        if not scroll:
            return p, lay
        area = QScrollArea()
        area.setObjectName("PanelScroll")
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        holder = QWidget()
        inner = QVBoxLayout(holder)
        inner.setContentsMargins(0, 0, 4, 0)
        inner.setSpacing(8)
        area.setWidget(holder)
        lay.addWidget(area, 1)
        return p, inner

    def _input_panel(self):
        p, lay = self._panel("INPUT PANEL", "Do the steps in order. A step unlocks when the one before it is done.")
        scroll = QScrollArea()
        scroll.setObjectName("PanelScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        holder = QWidget()
        col = QVBoxLayout(holder)
        col.setContentsMargins(0, 0, 6, 0)
        col.setSpacing(10)
        self.cards = {}

        # step 1
        c = StepCard(1, "Load application graph (DFG)",
                     "A list of operations such as  ×,0,0,1  (op 1 multiplies two inputs) and  +,1,2,5  "
                     "(op 5 adds the results of ops 1 and 2).")
        row = QHBoxLayout()
        row.addWidget(button("Load DFG file…", "Primary", self.load_dfg))
        row.addStretch(1)
        c.body_layout.addLayout(row)
        samples = QHBoxLayout()
        samples.addWidget(label("or try a sample:", "FieldLabel"))
        for key, (name, _, _) in SAMPLES.items():
            samples.addWidget(button(name, "Chip", lambda _=False, k=key: self.load_dfg(sample=k)))
        samples.addStretch(1)
        c.body_layout.addLayout(samples)
        self.cards[1] = c

        # step 2
        c = StepCard(2, "Load module library",
                     "Area and delay of every hardware unit (adder, multiplier, register…) and how many are available.")
        row = QHBoxLayout()
        row.addWidget(button("Load library file…", "Primary", self.load_lib))
        self.sample_lib_btn = button("Use the matching sample library", "Secondary", lambda: self.load_lib(sample=True))
        row.addWidget(self.sample_lib_btn)
        row.addStretch(1)
        c.body_layout.addLayout(row)
        self.cards[2] = c

        # step 3
        c = StepCard(3, "Explore designs with PSO",
                     "Particle swarm optimisation searches for the number of adders and multipliers with the lowest design "
                     "cost — without trying every combination.")
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(6)
        g.addWidget(label("Swarm sizes:", "FieldLabel"), 0, 0)
        sizes = QHBoxLayout()
        self.size_boxes = {}
        for n in (3, 5, 7):
            cb = button(f"{n} particles", "Chip")
            cb.setCheckable(True)
            cb.setChecked(True)
            self.size_boxes[n] = cb
            sizes.addWidget(cb)
        sizes.addStretch(1)
        g.addLayout(sizes, 0, 1, 1, 3)
        g.addWidget(label("Max iterations:", "FieldLabel"), 1, 0)
        self.max_iter = QSpinBox()
        self.max_iter.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.PlusMinus)
        self.max_iter.setRange(1, 1000)
        self.max_iter.setValue(50)
        g.addWidget(self.max_iter, 1, 1)
        g.addWidget(label("Stop if no improvement for:", "FieldLabel"), 1, 2)
        self.stall = QSpinBox()
        self.stall.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.PlusMinus)
        self.stall.setRange(1, 200)
        self.stall.setValue(10)
        self.stall.setSuffix(" iterations")
        g.addWidget(self.stall, 1, 3)
        c.body_layout.addLayout(g)
        self.adv_btn = button("▸ Advanced settings", "LinkBtn", self.toggle_advanced)
        c.body_layout.addWidget(self.adv_btn)
        self.adv = QWidget()
        ag = QGridLayout(self.adv)
        ag.setContentsMargins(0, 0, 0, 0)
        ag.setHorizontalSpacing(10)
        ag.setVerticalSpacing(6)
        self.f = QDoubleSpinBox()
        self.f.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.PlusMinus)
        self.f.setRange(0, 4)
        self.f.setSingleStep(0.1)
        self.f.setValue(2.0)
        self.k = QComboBox()
        self.k.addItems(["random 0–1", "1", "0.5"])
        self.seed = QSpinBox()
        self.seed.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.PlusMinus)
        self.seed.setRange(0, 10 ** 6)
        self.seed.setValue(1)
        self.t1 = QDoubleSpinBox()
        self.t1.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.PlusMinus)
        self.t1.setRange(0, 1)
        self.t1.setSingleStep(0.05)
        self.t1.setValue(0.5)
        self.ac = QLineEdit()
        self.ac.setPlaceholderText("auto = Amax")
        self.lc = QLineEdit()
        self.lc.setPlaceholderText("auto = Lmax")
        self.mux = QCheckBox("Add multiplexer area to the design area")
        fields = [("Social / cognitive factor f1 = f2:", self.f), ("Random factors k1 = k2:", self.k),
                  ("Random seed:", self.seed), ("Area weight t1 (latency t2 = 1 − t1):", self.t1),
                  ("Area constraint Ac (µm²):", self.ac), ("Latency constraint Lc (ps):", self.lc)]
        for i, (txt, w) in enumerate(fields):
            ag.addWidget(label(txt, "FieldLabel"), i // 2, (i % 2) * 2)
            ag.addWidget(w, i // 2, (i % 2) * 2 + 1)
        ag.addWidget(self.mux, 3, 0, 1, 4)
        self.adv.hide()
        c.body_layout.addWidget(self.adv)
        row = QHBoxLayout()
        row.addWidget(button("Run PSO exploration", "Primary", self.run_pso))
        row.addStretch(1)
        c.body_layout.addLayout(row)
        self.cards[3] = c

        # step 4
        c = StepCard(4, "Generate scheduled design",
                     "List scheduling puts every operation into a clock cycle (control step) using the chosen number of units.")
        row = QHBoxLayout()
        row.addWidget(label("Design:", "FieldLabel"))
        self.choice = QComboBox()
        self.choice.setMinimumWidth(260)
        row.addWidget(self.choice, 1)
        c.body_layout.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(button("Generate scheduled design", "Primary", self.make_schedule))
        row.addStretch(1)
        c.body_layout.addLayout(row)
        self.cards[4] = c

        # step 5
        c = StepCard(5, "Generate register allocation (RAT)",
                     "Values that are never alive at the same time share one register (register colouring).")
        row = QHBoxLayout()
        row.addWidget(button("Generate register allocation table", "Primary", self.make_rat))
        row.addStretch(1)
        c.body_layout.addLayout(row)
        self.cards[5] = c

        # step 6
        c = StepCard(6, "Compute area, latency & design cost",
                     "Area = units + registers · latency = sum of cycle lengths · cost = Eq. 5 of the paper.")
        row = QHBoxLayout()
        row.addWidget(button("Compute design cost", "Primary", self.compute_cost))
        row.addStretch(1)
        c.body_layout.addLayout(row)
        self.cards[6] = c

        for n in range(1, 7):
            col.addWidget(self.cards[n])
        col.addStretch(1)
        scroll.setWidget(holder)
        self.input_scroll = scroll
        lay.addWidget(scroll, 1)
        return p

    def _status_panel(self):
        p, lay = self._panel("STATUS PANEL", "Shows how far you are and what each step produced.", scroll=True)
        self.tiles = {}
        for n in range(1, 7):
            self.tiles[n] = StatusTile(n, STEP_NAMES[n])
            lay.addWidget(self.tiles[n])
        lay.addStretch(1)
        return p

    def _output_panel(self):
        p, lay = self._panel("OUTPUT PANEL", "Each button opens a window. Buttons unlock when their step is done.",
                             scroll=True)
        self.out_buttons = {}
        for group, items in OUTPUTS:
            lay.addWidget(label(group.upper(), "GroupLabel"))
            for key, text, tip, cls, step in items:
                b = OutputButton(text, tip)
                b.clicked.connect(lambda _=False, k=key: self.open_output(k))
                self.out_buttons[key] = (b, cls, step)
                lay.addWidget(b)
        lay.addStretch(1)
        return p

    # ------------------------------------------------------------------ state
    def refresh(self, fresh_step=None):
        nxt = self.s.next_step()
        for n, c in self.cards.items():
            if n in self.s.done:
                c.set_state("done")
            elif n == nxt:
                c.set_state("active")
            else:
                c.set_state("locked")
        for n, t in self.tiles.items():
            if n in self.s.done:
                t.set_state("done", None)
            elif n == nxt:
                t.set_state("next", "Waiting for you — see the input panel.")
            else:
                t.set_state("waiting", "")
        for key, (b, _, step) in self.out_buttons.items():
            b.set_available(step in self.s.done, fresh=(step == fresh_step))
        self.next_text.setText(NEXT_TEXT[nxt])
        self.next_frame.setProperty("done", nxt is None)
        repolish(self.next_frame)
        self.sample_lib_btn.setVisible(bool(self.s.sample))
        if self.s.sample:
            self.sample_lib_btn.setText(f"Use sample library ({os.path.basename(SAMPLES[self.s.sample][2])})")
        if nxt in self.cards:
            QTimer.singleShot(50, lambda: self.input_scroll.ensureWidgetVisible(self.cards[nxt], 0, 30))

    def log(self, msg):
        self.log_box.appendPlainText(f"[{time.strftime('%H:%M:%S')}]  {msg}")

    def _close_outputs_from(self, step):
        for key, (_, _, s) in self.out_buttons.items():
            if s >= step and key in self.open_windows:
                w = self.open_windows.pop(key)
                w.close()

    def _do(self, step, fn, success_log):
        """Run one step: amber 'running' tile, then green with a summary, or red with the error."""
        tile = self.tiles[step]
        tile.set_state("running", "Working…")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            summary = fn()
        except Exception as e:      # show any problem to the user instead of crashing
            QApplication.restoreOverrideCursor()
            msg = str(e) or e.__class__.__name__
            tile.set_state("error", msg)
            self.log(f"Step {step} failed: {msg}")
            traceback.print_exc()
            QMessageBox.warning(self, f"Step {step} — {STEP_NAMES[step]}", msg)
            return False
        QApplication.restoreOverrideCursor()
        self._close_outputs_from(step)
        self.refresh(fresh_step=step)
        self.cards[step].set_result(summary)
        self.tiles[step].set_state("done", summary)
        self.log(success_log(summary))
        return True

    # ------------------------------------------------------------------ step actions
    def load_dfg(self, sample=None):
        path = None
        if not sample:
            path, _ = QFileDialog.getOpenFileName(self, "Load application (DFG) file", "", "Text files (*.txt);;All files (*)")
            if not path:
                return
        self._do(1, lambda: self.s.load_dfg(path=path, sample=sample),
                 lambda summ: f"Step 1 done — loaded {summ}.")

    def load_lib(self, sample=False):
        path = None
        if not sample:
            path, _ = QFileDialog.getOpenFileName(self, "Load module library file", "", "Text files (*.txt);;All files (*)")
            if not path:
                return
        self._do(2, lambda: self.s.load_library(path=path, use_sample=sample),
                 lambda summ: f"Step 2 done — library loaded: {summ}.")

    def toggle_advanced(self):
        vis = not self.adv.isVisible()
        self.adv.setVisible(vis)
        self.adv_btn.setText(("▾" if vis else "▸") + " Advanced settings")

    def _settings(self):
        def num(edit, what):
            t = edit.text().strip()
            if not t or t.lower() == "auto":
                return None
            try:
                return float(t)
            except ValueError:
                raise ValueError(f"{what} must be a number, or empty for auto.")
        k = self.k.currentText()
        return Settings(particles=tuple(n for n, b in self.size_boxes.items() if b.isChecked()),
                        max_iter=self.max_iter.value(), stall=self.stall.value(), f=self.f.value(),
                        k="random" if k.startswith("random") else float(k), seed=self.seed.value(),
                        t1=self.t1.value(), ac=num(self.ac, "Area constraint Ac"), lc=num(self.lc, "Latency constraint Lc"),
                        include_mux_area=self.mux.isChecked())

    def run_pso(self):
        def go():
            summary = self.s.run_pso(self._settings())
            self.choice.clear()
            for text, pos in self.s.choices():
                self.choice.addItem(text, pos)
            return summary

        def done_log(summ):
            ex = self.s.ex
            parts = [f"N={n}: {r.iterations_run} iterations, best at iteration {r.convergence_iter} "
                     f"({r.exploration_time_ms:.2f} ms)" for n, r in ex.runs]
            return f"Step 3 done — PSO {summ}. " + "; ".join(parts) + "."
        if self._do(3, go, done_log):
            self.open_output("explore")

    def make_schedule(self):
        idx = self.choice.currentIndex()
        choice = (self.choice.currentText(), self.choice.currentData()) if idx >= 0 else None
        self._do(4, lambda: self.s.make_schedule(choice), lambda summ: f"Step 4 done — scheduled design: {summ}.")

    def make_rat(self):
        self._do(5, self.s.make_rat, lambda summ: f"Step 5 done — register allocation: {summ}.")

    def compute_cost(self):
        self._do(6, self.s.compute_cost, lambda summ: f"Step 6 done — {summ}.")

    # ------------------------------------------------------------------ outputs
    def open_output(self, key):
        b, cls, step = self.out_buttons[key]
        if step not in self.s.done:
            return
        if key == "export":
            return self.export()
        w = self.open_windows.get(key)
        if w is not None:
            w.show()
            w.raise_()
            w.activateWindow()
            return
        try:
            w = cls(self, self.s)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.warning(self, "Could not open window", str(e))
            return
        self.open_windows[key] = w
        w.destroyed.connect(lambda _=None, k=key: self.open_windows.pop(k, None))
        w.show()
        b.set_available(True, fresh=False)

    def export(self):
        base = QFileDialog.getExistingDirectory(self, "Choose a folder for the results", os.path.expanduser("~/Desktop"))
        if not base:
            return
        s = self.s
        out = os.path.join(base, f"{s.dfg.name}_PSO_results")
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            write_results(s.ex, out, s.settings.stall, s.settings.max_iter, s.settings.describe())
            with open(os.path.join(out, "chosen_design.txt"), "w") as f:
                f.write(f"{s.dfg.name} — design taken through steps 4–6: {s.choice[0]}\n\n"
                        + design_report(s.design, s.dfg, s.ex.probe) + "\n")
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Export failed", str(e))
            return
        QApplication.restoreOverrideCursor()
        self.log(f"Exported all results to {out}")
        box = QMessageBox(self)
        box.setWindowTitle("Export finished")
        box.setText(f"All charts, tables and reports were saved to:\n{out}")
        open_btn = box.addButton("Open folder", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() == open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(out))

    def show_help(self):
        w = self.open_windows.get("help")
        if w is None:
            w = W.HelpWindow(self)
            self.open_windows["help"] = w
            w.destroyed.connect(lambda _=None: self.open_windows.pop("help", None))
        w.show()
        w.raise_()

    def reset(self):
        if self.s.done and QMessageBox.question(self, "Reset", "Clear everything and start again from step 1?") \
                != QMessageBox.StandardButton.Yes:
            return
        for k in list(self.open_windows):
            if k != "help":
                self.open_windows.pop(k).close()
        self.s.reset()
        for c in self.cards.values():
            c.result.hide()
        self.refresh()
        self.log("Reset — start again with step 1.")
