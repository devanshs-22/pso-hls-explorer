"""Secondary windows opened from the output panel. Each one starts with a short plain-English
explanation of what it shows."""
from types import SimpleNamespace

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QHeaderView, QSlider, QSplitter, QTableWidget, QTableWidgetItem,
                               QTextBrowser, QVBoxLayout, QWidget)

from psodse.io import OP_SYMBOL
from psodse.plots import fig_convergence, fig_dfg, fig_rat, fig_schedule, fig_times, fig_tradeoff, save
from psodse.registers import build_variables, fu_label, register_colour
from psodse.replay import PHASE_TITLE, build_frames, narrate
from psodse.report import config_text, reg_names

from .spacemap import ConvergenceStrip, SpaceMap
from .widgets import FigureView, Kpi, button, card, label, table


class OutputWindow(QWidget):
    def __init__(self, parent, title, explain, size=(1000, 700)):
        super().__init__(parent, Qt.WindowType.Window)
        self.setObjectName("WinRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle(f"{title} — PSO HLS Explorer")
        self.resize(*size)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(10)
        lay.addWidget(label(title, "WinTitle"))
        if explain:
            lay.addWidget(label(explain, "WinExplain", wrap=True, rich=True))
        self.body = QVBoxLayout()
        self.body.setSpacing(12)
        lay.addLayout(self.body, 1)


def _splitter(*widgets, sizes=None):
    s = QSplitter(Qt.Orientation.Horizontal)
    for w in widgets:
        s.addWidget(w)
    if sizes:
        s.setSizes(sizes)
    s.setChildrenCollapsible(False)
    return s


def _wrap(layout_or_widget, title=None):
    f, lay = card(title)
    if isinstance(layout_or_widget, QWidget):
        lay.addWidget(layout_or_widget)
    else:
        lay.addLayout(layout_or_widget)
    return f


def _short(pos, dims):
    return "·".join(f"{n}{d[0].upper()}" for n, d in zip(pos, dims))


def _op_meaning(dfg, op):
    a = "input" if op.operand1 == 0 else f"op{op.operand1}"
    b = "input" if op.operand2 == 0 else f"op{op.operand2}"
    return f"op{op.op_id} = {a} {OP_SYMBOL[op.op_type]} {b}"


# ---------------------------------------------------------------------- step 1 / 2
class DfgWindow(OutputWindow):
    def __init__(self, parent, s):
        super().__init__(parent, "Data-flow graph (DFG)",
                         "Each circle is one <b>operation</b> (× multiply, + add). An arrow means the result of one "
                         "operation is used by another; the small stubs on top are <b>primary inputs</b>. Rows show the "
                         "earliest clock cycle in which each operation could run. The table is the input file read as "
                         "objects: <i>operation, first operand, second operand, operation number</i> (operand 0 = primary input).",
                         size=(1180, 760))
        dfg = s.dfg
        rows = [(o.op_id, (OP_SYMBOL[o.op_type], o.fu_type), o.operand1 or "input", o.operand2 or "input",
                 _op_meaning(dfg, o)) for o in dfg.ops.values()]
        t = table(["Op #", "Op", "Operand 1", "Operand 2", "Meaning"], rows, fit=False)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(_wrap(t, f"{len(rows)} operations (Operation, first operand, second operand, number)"), 1)
        self.body.addWidget(_splitter(_wrap(FigureView(fig_dfg(dfg, f"{dfg.name}"), scroll=True,
                                                       filename=f"{dfg.name}_DFG.png")),
                                      right, sizes=[640, 500]), 1)


class LibraryWindow(OutputWindow):
    def __init__(self, parent, s):
        super().__init__(parent, "Module library",
                         "The hardware units the design can be built from (15 nm open cell library). "
                         "<b>Area</b> is chip area per unit, <b>delay</b> is how long one operation takes. "
                         "<b>Available</b> limits how many units PSO may choose: at least 1 of every type the application uses.",
                         size=(860, 560))
        lib, dfg = s.lib, s.dfg
        used = {o.fu_type for o in dfg.ops.values()}
        rows = []
        for f in lib.fus.values():
            rows.append((f.name, f"{f.area:.4f}", f"{f.latency:.4f}", f"{f.power:g}",
                         f"1 – {f.max_count}" if f.name in used else str(f.max_count),
                         "yes" if f.name in used else "no"))
        rows.append(("register", f"{lib.register_area:.4f}", "ignored for latency", "–", "as many as needed", "yes"))
        rows.append(("mux 2:1", f"{lib.mux_area:.4f}", f"{lib.mux_latency:.4f}", "–", "–", "reported only"))
        self.body.addWidget(table(["Unit", "Area (µm²)", "Delay (ps)", "Power (pJ)", "Available", "Used here"], rows,
                                  align_right=(1, 2, 3)))
        probe = s.library_probe()
        space = 1
        for lo, hi in zip(probe.lower, probe.upper):
            space *= hi - lo + 1
        txt = (" × ".join(f"{hi - lo + 1} choices of {d}s ({lo}–{hi})" for d, lo, hi in zip(probe.dims, probe.lower, probe.upper))
               + f" = <b>{space} possible designs</b>.<br>A<sub>max</sub> (area with the most hardware) = {probe.amax:.2f} µm² · "
               f"L<sub>max</sub> (latency with the least hardware) = {probe.lmax:.2f} ps.")
        self.body.addWidget(_wrap(label(txt, wrap=True, rich=True), "Design space"))
        self.body.addStretch(1)


# ---------------------------------------------------------------------- step 3
class ExplorationWindow(OutputWindow):
    """Slowed-down replay of the recorded PSO runs."""

    def __init__(self, parent, s):
        super().__init__(parent, "PSO exploration — replay",
                         "Every square is one possible design; its colour is its cost once the swarm has visited it "
                         "(darker = higher cost, <b>?</b> = not visited yet). The orange dots are particles. The black frame "
                         "with ★ is the swarm's best design so far. Press ▶ or drag the slider.",
                         size=(1280, 860))
        self.s, self.ex = s, s.ex
        top = QHBoxLayout()
        self.group = QButtonGroup(self)
        for i, (n, _) in enumerate(self.ex.runs):
            b = button(f"N = {n} particles", "Seg")
            b.setCheckable(True)
            self.group.addButton(b, i)
            top.addWidget(b)
        top.addStretch(1)
        self.body.addLayout(top)

        main = QHBoxLayout()
        main.setSpacing(14)
        left_card, left = card()
        self.map = SpaceMap()
        left.addWidget(self.map, 1)
        player = QHBoxLayout()
        self.b_first = button("⏮", "Round", lambda: self.goto(0))
        self.b_prev = button("◀", "Round", lambda: self.goto(self.i - 1))
        self.b_play = button("▶", "Play", lambda: self.toggle())
        self.b_next = button("▶|", "Round", lambda: self.goto(self.i + 1))
        self.b_last = button("⏭", "Round", lambda: self.goto(len(self.frames) - 1))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.valueChanged.connect(lambda v: self.goto(v) if v != self.i else None)
        self.speed = QComboBox()
        self.speed.addItems(["slow", "normal", "fast"])
        self.speed.setCurrentIndex(1)
        for w in (self.b_first, self.b_prev, self.b_play, self.b_next, self.b_last):
            player.addWidget(w)
        player.addWidget(self.slider, 1)
        player.addWidget(self.speed)
        left.addLayout(player)
        self.replay_note = label("", "ReplayNote", wrap=True, rich=True)
        left.addWidget(self.replay_note)
        left.addWidget(label("Two dots in one square = two particles testing the same design (allowed). Big jumps are "
                             "expected: after moving, every particle is <b>mutated</b> on purpose so the swarm doesn't get stuck. "
                             "Dashed trail = mutation jump, solid trail = velocity move.", "WinExplain", wrap=True, rich=True))
        main.addWidget(left_card, 3)

        side = QVBoxLayout()
        nar_card, nar = card()
        self.badge = label("", "PhaseBadge")
        hb = QHBoxLayout()
        hb.addWidget(self.badge)
        hb.addStretch(1)
        nar.addLayout(hb)
        self.iter_line = label("", "IterLine")
        nar.addWidget(self.iter_line)
        self.stop_meter = label("", "WinExplain", rich=True, wrap=True)
        nar.addWidget(self.stop_meter)
        self.narration = label("", "Narration", wrap=True, rich=True)
        self.narration.setMinimumHeight(110)
        self.narration.setAlignment(Qt.AlignmentFlag.AlignTop)
        nar.addWidget(self.narration)
        side.addWidget(nar_card)
        gb = QFrame()
        gb.setObjectName("GBest")
        gbl = QHBoxLayout(gb)
        star = label("★")
        star.setStyleSheet("color:#eb6834; font-size:26px;")
        gbl.addWidget(star)
        self.gbest = label("", rich=True, wrap=True)
        gbl.addWidget(self.gbest, 1)
        side.addWidget(gb)
        self.ptable = table(["", "Now trying", "Cost", "Own best"], [], fit=False)
        side.addWidget(label("A = adders, M = multipliers. The highlighted particle sits on the swarm's best design.",
                             "WinExplain", wrap=True))
        side.addWidget(self.ptable, 1)
        side_w = QWidget()
        side_w.setLayout(side)
        side_w.setMinimumWidth(360)
        side_w.setMaximumWidth(430)
        main.addWidget(side_w, 2)
        self.body.addLayout(main, 1)

        conv_card, conv = card()
        self.strip = ConvergenceStrip()
        conv.addWidget(self.strip)
        self.body.addWidget(conv_card)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._advance)
        self.group.idClicked.connect(self.select_run)
        self.group.button(0).setChecked(True)
        self.select_run(0)
        self.play(first_delay=900)          # start the replay automatically

    def select_run(self, idx):
        self.pause()
        self.run_idx = idx
        self.n, self.res = self.ex.runs[idx]
        self.cfg = self.ex.configs[self.n]
        self.frames = build_frames(self.res)
        self.map.set_data(self.ex, self.frames)
        self.strip.set_run(self.res, self.cfg.max_iter, self.cfg.stall_limit)
        self.slider.blockSignals(True)
        self.slider.setRange(0, len(self.frames) - 1)
        self.slider.blockSignals(False)
        self.replay_note.setText(f"This is a slowed-down <b>replay</b>. The real search took "
                                 f"{self.res.exploration_time_ms:.2f} ms; while running, PSO never knew when it would stop — "
                                 f"only its stop rule (shown on the right).")
        self.i = 0
        self.goto(0, animate=False)

    def goto(self, i, animate=None):
        i = max(0, min(len(self.frames) - 1, i))
        if animate is None:
            animate = abs(i - self.i) == 1
        prev, self.i = self.i, i
        f = self.frames[i]
        dur = {"slow": 900, "normal": 550, "fast": 260}[self.speed.currentText()]
        self.map.show_frame(i, animate and prev != i, duration=int(dur * (0.7 if f.phase == "mutate" else 1)))
        self.slider.blockSignals(True)
        self.slider.setValue(i)
        self.slider.blockSignals(False)
        dims, stall_lim, max_iter = self.ex.dims, self.cfg.stall_limit, self.cfg.max_iter
        self.badge.setText(PHASE_TITLE[f.phase])
        if f.phase == "done":
            self.iter_line.setText(f"Stopped after iteration {self.res.iterations_run}")
        else:
            w = f"   <span style='font-size:13px;color:#4b5563;font-weight:400'>inertia ω = {f.w:.3f}</span>" if f.w else ""
            self.iter_line.setText(f"Iteration {f.iteration}{w}")
        dots = "".join("<span style='color:#eb6834'>●</span>" if k < f.stall else "<span style='color:#d5dae2'>●</span>"
                       for k in range(stall_lim))
        if f.phase == "done":
            rule = (f"hit the limit of {max_iter} iterations" if self.res.iterations_run >= max_iter
                    else f"{stall_lim} iterations in a row without improvement, so it stopped")
        else:
            rule = f"<b>{f.stall}</b> of {stall_lim} iterations without improvement · hard limit {max_iter}"
        self.stop_meter.setText(f"{dots}<br>{rule}")
        self.narration.setText(narrate(f, dims, self.res, self.cfg, self.ex.space))
        self.gbest.setText(f"<span style='color:#4b5563;font-size:12px'>Swarm's best so far</span><br>"
                           f"<b style='font-size:15px'>{config_text(f.gbest, dims)}</b>"
                           f"<span style='color:#4b5563'>  ·  cost {f.gbest_cost:.4f}</span>")
        t = self.ptable
        t.setRowCount(len(f.positions))
        for r, (pos, c) in enumerate(zip(f.positions, f.costs)):
            lb_pos, lb_cost = f.local_best[r]
            vals = [f"P{r}", _short(pos, dims), f"{c:.4f}", f"{_short(lb_pos, dims)} ({lb_cost:.3f})"]
            for col, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if pos == f.gbest:                  # this particle sits on the swarm's best design
                    it.setBackground(QColor("#fff1e8"))
                    f2 = it.font()
                    f2.setBold(True)
                    it.setFont(f2)
                    it.setToolTip("This particle is on the swarm's best design")
                t.setItem(r, col, it)
        t.resizeColumnsToContents()
        self.strip.set_position(f.iteration, f.phase == "done")

    def play(self, first_delay=250):
        if self.i >= len(self.frames) - 1:
            self.goto(0, animate=False)
        self.playing = True
        self.b_play.setText("❚❚")
        self.timer.start(first_delay)

    def pause(self):
        self.playing = False
        self.timer.stop()
        self.b_play.setText("▶")

    def toggle(self):
        self.pause() if getattr(self, "playing", False) else self.play()

    def _advance(self):
        if not self.playing:
            return
        if self.i >= len(self.frames) - 1:
            return self.pause()
        self.goto(self.i + 1)
        self.timer.start({"slow": 1500, "normal": 900, "fast": 420}[self.speed.currentText()])

    def closeEvent(self, e):
        self.pause()
        super().closeEvent(e)


class ConvergenceWindow(OutputWindow):
    def __init__(self, parent, s):
        super().__init__(parent, "Convergence graph",
                         "The swarm's best design cost after every iteration, one panel per swarm size. The cost can only go "
                         "down. The dot marks where the final best design was first found (<b>convergence</b>); the shaded part "
                         "is the run of iterations without improvement that made the search stop.", size=(1200, 600))
        st = s.settings
        self.body.addWidget(_wrap(FigureView(fig_convergence(s.ex.runs, f"{s.dfg.name} — best design cost per iteration",
                                                             st.stall, st.max_iter),
                                             filename=f"{s.dfg.name}_convergence.png")), 1)


class CompareWindow(OutputWindow):
    def __init__(self, parent, s):
        super().__init__(parent, "Swarm sizes compared (N = 3, 5, 7)",
                         "Each swarm size is a separate PSO run. <b>Convergence time</b> = time until the final best design was "
                         "first found. <b>Exploration time</b> = time until the search stopped.", size=(1050, 720))
        ex, dims = s.ex, s.ex.dims
        rows = [(n, config_text(r.best, dims), f"{r.best.cost:.4f}", r.convergence_iter, r.iterations_run,
                 f"{r.convergence_time_ms:.3f}", f"{r.exploration_time_ms:.3f}", f"{len(r.explored)} of {ex.space}")
                for n, r in ex.runs]
        t = table(["N", "Best design", "Cost", "Found at iteration", "Iterations run", "Convergence time (ms)",
                   "Exploration time (ms)", "Designs visited"], rows, align_right=(2, 3, 4, 5, 6))
        self.body.addWidget(t)
        if ex.exhaustive:
            ok = ex.all_found_optimum
            msg = (f"✓ Checked afterwards against all {ex.space} designs: the true lowest-cost design is "
                   f"<b>{config_text(ex.true_best, dims)}</b> — " + ("every PSO run found it." if ok else
                                                                     "NOT every run found it; try more particles or another seed."))
            note = label(msg, wrap=True, rich=True)
            note.setStyleSheet(f"background:{'#e7f6ec' if ok else '#fdecec'}; border-radius:8px; padding:8px 10px;")
            self.body.addWidget(note)
        self.body.addWidget(_wrap(FigureView(fig_times(ex.runs, f"{s.dfg.name} — convergence vs exploration time"),
                                             filename=f"{s.dfg.name}_times.png")), 1)


class TradeoffWindow(OutputWindow):
    def __init__(self, parent, s):
        super().__init__(parent, "Area vs latency trade-off",
                         "More hardware makes a design faster but bigger. Designs on the dashed <b>Pareto front</b> cannot get "
                         "smaller without getting slower. The ★ is the design with the lowest cost (the best balance).",
                         size=(1250, 720))
        ex, dims = s.ex, s.ex.dims
        best = ex.probe.evaluate(ex.best_run[1].best.position)
        fig = fig_tradeoff(ex.all_points, ex.visited, best, dims, f"{s.dfg.name} — area vs latency")
        rows = [(config_text(p, dims), f"{p.area:.2f}", f"{p.latency:.2f}", f"{p.cost:.4f}") for p in ex.pareto]
        t = table(["Pareto design", "Area (µm²)", "Latency (ps)", "Cost"], rows, align_right=(1, 2, 3))
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(_wrap(t, "Pareto-optimal designs"))
        rl.addStretch(1)
        self.body.addWidget(_splitter(_wrap(FigureView(fig, filename=f"{s.dfg.name}_tradeoff.png")), right,
                                      sizes=[820, 380]), 1)


# ---------------------------------------------------------------------- step 4 / 5 / 6
def _sched_point(s):
    _, op_inputs, op_output = build_variables(s.dfg)
    return SimpleNamespace(schedule=s.schedule, alloc=s.alloc,
                           regs=SimpleNamespace(op_inputs=op_inputs, op_output=op_output))


class ScheduleWindow(OutputWindow):
    def __init__(self, parent, s):
        sch = s.schedule
        super().__init__(parent, "Scheduled design",
                         f"List scheduling of <b>{config_text(s.choice[1], s.dims)}</b>. Rows are clock cycles (control steps), "
                         "columns are the hardware units. A cycle lasts as long as its slowest operation; register delay is "
                         "ignored. <b>Latency</b> = the sum of all cycle lengths.", size=(1250, 820))
        dims = s.dims
        units = [(fu, i) for fu in dims for i in range(s.alloc[fu])]
        rows = []
        for k, ops in enumerate(sch.steps, 1):
            cell = {sch.binding[o]: f"{OP_SYMBOL[s.dfg.ops[o].op_type]}{o}" for o in ops}
            rows.append([f"CS{k}"] + [cell.get(u, "–") for u in units] + [f"{sch.step_latency[k - 1]:.4f}"])
        rows.append(["Total"] + [""] * len(units) + [f"{sch.latency:.4f}"])
        t = table(["Cycle"] + [fu_label(*u) for u in units] + ["Cycle length (ps)"], rows, align_right=(len(units) + 1,))
        busy = []
        for u in units:
            n = sum(1 for st in sch.steps if any(sch.binding[o] == u for o in st))
            busy.append(f"{fu_label(*u)} busy {n}/{sch.n_steps} cycles")
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(_wrap(t, f"{sch.n_steps} control steps · latency {sch.latency:.2f} ps"))
        rl.addWidget(_wrap(label("Unit reuse: " + " · ".join(busy) + ". One unit used in several cycles is "
                                 "functional-unit reuse.", wrap=True), "Reuse"))
        rl.addStretch(1)
        fig = fig_schedule(_sched_point(s), s.dfg, dims, f"{s.dfg.name} · {config_text(s.choice[1], dims)}")
        self.body.addWidget(_splitter(_wrap(FigureView(fig, scroll=True, filename=f"{s.dfg.name}_schedule.png")), right,
                                      sizes=[720, 480]), 1)


class RatWindow(OutputWindow):
    """The RAT in the paper's format (rows = registers named by colour, columns = C0..Cn),
    with a plain-language guide and hover highlighting."""

    def __init__(self, parent, s):
        super().__init__(parent, "Register allocation table (RAT)", None, size=(1100, 760))
        self.s = s
        regs, dfg = s.regs, s.dfg
        n_cols, n_regs = len(regs.table), regs.n_registers
        n_in = sum((op.operand1 == 0) + (op.operand2 == 0) for op in dfg.ops.values())
        step_of = s.schedule.op_step

        guide = label(
            "<b>How to read it</b><br>"
            "• Each <b>row</b> is one register — a small storage box in the chip. Registers are named by colour, as in the paper.<br>"
            "• Each <b>column</b> is a moment in time: <b>C0</b> = the start, <b>C1</b> = after clock cycle 1, <b>C2</b> = after cycle 2, …<br>"
            "• A <b>cell</b> shows which value that register is holding at that moment. <b>–</b> means it is empty.<br>"
            "• If a row holds <b>different values</b> over time, that one register is <b>reused</b> — this saves chip area.<br>"
            f"• <b>V0–V{n_in - 1}</b> are the {n_in} input values. <b>V{n_in}</b> is the result of operation 1, "
            f"<b>V{n_in + 1}</b> of operation 2, and so on.  Hover over a value to see where it is stored.",
            "WinExplain", wrap=True, rich=True)
        guide.setStyleSheet("background:#f3f6fb; border:1px solid #dbe3ef; border-radius:10px; padding:10px 12px;")
        self.body.addWidget(guide)

        t = QTableWidget(n_regs, n_cols)
        t.setHorizontalHeaderLabels([f"C{b}\n{'start' if b == 0 else f'cycle {b}'}" for b in range(n_cols)])
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        t.setMouseTracking(True)
        big = t.font()
        big.setPixelSize(14)
        for r in range(n_regs):
            name, abbr, hx = register_colour(r)
            sw = QPixmap(14, 14)
            sw.fill(QColor(hx))
            head = QTableWidgetItem(QIcon(sw), f"  {name} ({abbr})")
            t.setVerticalHeaderItem(r, head)
            for b in range(n_cols):
                v = regs.table[b][r]
                it = QTableWidgetItem(v or "–")
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it.setFont(big)
                if v:
                    info = regs.variables[v]
                    what = (f"the result of operation {info.producer} (computed in cycle {step_of[info.producer]})"
                            if info.producer else "an input value")
                    when = f"C{info.birth}" if info.birth == info.last else f"C{info.birth} to C{info.last}"
                    it.setToolTip(f"{v} is {what}.\nIt is stored in register {name} from {when}.")
                else:
                    it.setForeground(QColor("#b8bec9"))
                t.setItem(r, b, it)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        t.verticalHeader().setDefaultSectionSize(34)
        t.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        t.cellEntered.connect(self._highlight)
        self.table = t
        if n_regs <= 20:                                # only as tall as its rows, no empty space
            t.setFixedHeight(t.horizontalHeader().sizeHint().height() + 34 * n_regs + 2 * t.frameWidth() + 4)
            self.body.addWidget(t)
        else:
            self.body.addWidget(t, 1)

        # one worked example and one summary line, generated from the data
        counts = [len({regs.table[b][r] for b in range(n_cols) if regs.table[b][r]}) for r in range(n_regs)]
        r_ex = max(range(n_regs), key=lambda r: counts[r])
        seq = []
        for b in range(n_cols):
            v = regs.table[b][r_ex]
            if v and (not seq or seq[-1] != v):
                seq.append(v)
        name_ex = register_colour(r_ex)[0]
        shown = ", then ".join(seq[:5]) + (", …" if len(seq) > 5 else "")
        reused = sum(1 for c in counts if c > 1)
        summary = label(
            f"<b>Example:</b> register <b>{name_ex}</b> holds {shown} — {len(seq)} different values in one register.<br>"
            f"<b>Result:</b> only <b>{n_regs} registers</b> are needed to store all <b>{len(regs.variables)} values</b>, "
            f"because values that are not needed at the same time share a register ({reused} registers are reused).",
            "WinExplain", wrap=True, rich=True)
        self.body.addWidget(summary)
        self.body.addStretch(1)
        bar = QHBoxLayout()
        bar.addStretch(1)
        bar.addWidget(button("Save RAT as image…", "Secondary", self.save_image))
        self.body.addLayout(bar)

    def _highlight(self, row, col):
        """Highlight every cell that holds the same value as the one under the mouse."""
        t = self.table
        v = t.item(row, col).text()
        for r in range(t.rowCount()):
            for c in range(t.columnCount()):
                it = t.item(r, c)
                same = v != "–" and it.text() == v
                it.setBackground(QColor("#ffe7d6") if same else QColor("#ffffff"))
                f = it.font()
                f.setBold(same)
                it.setFont(f)

    def save_image(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save RAT image", f"{self.s.dfg.name}_RAT.png", "PNG image (*.png)")
        if path:
            save(fig_rat(SimpleNamespace(regs=self.s.regs), self.s.dfg,
                         f"Register allocation table — {self.s.dfg.name} · {config_text(self.s.choice[1], self.s.dims)}"), path)


class InterconnectWindow(OutputWindow):
    def __init__(self, parent, s):
        super().__init__(parent, "Datapath interconnect (multiplexers)",
                         "Reusing a unit or a register has a price: if an input receives data from several places it needs a "
                         "<b>multiplexer</b> (k:1 mux); if an output feeds several places it needs a <b>demultiplexer</b> (1:k). "
                         "A k:1 mux is built from k−1 two-input muxes.", size=(820, 640))
        expl = {"mux": "chooses one of several sources", "demux": "sends the value to one of several places"}
        rows = []
        for loc, kind in s.muxes:
            loc_n = reg_names(loc)
            part = "input" if loc.endswith((".in", ".in1", ".in2")) else "output"
            rows.append((loc_n, kind, f"{part} — {expl['demux' if 'demux' in kind else 'mux']}"))
        self.body.addWidget(table(["Where", "Type", "What it does"], rows, fit=False), 1)
        lib = s.lib
        self.body.addWidget(label(f"Equivalent 2:1 multiplexers: <b>{s.mux2}</b> × {lib.mux_area:.4f} µm² = "
                                  f"{s.mux2 * lib.mux_area:.2f} µm² — " +
                                  ("included in the design area." if s.settings.include_mux_area else
                                   "reported only, not added to the design area (as in the reference tool)."),
                                  wrap=True, rich=True))


class CostWindow(OutputWindow):
    def __init__(self, parent, s):
        p, ev = s.design, s.ex.probe
        super().__init__(parent, "Area, latency & design cost",
                         f"Final metrics of <b>{config_text(p, s.dims)}</b>. Design cost is Eq. 5 of the paper; "
                         "it combines area and latency into one number, and <b>more negative is better</b>.", size=(1100, 760))
        kp = QGridLayout()
        kp.setSpacing(10)
        tiles = [Kpi("Design cost", f"{p.cost:.4f}", "more negative is better", hero=True)]
        tiles += [Kpi(f"{d.capitalize()}s", str(n), f"of {lo}–{hi} available")
                  for d, n, lo, hi in zip(s.dims, p.position, ev.lower, ev.upper)]
        tiles += [Kpi("Registers", str(p.regs.n_registers), "after register sharing"),
                  Kpi("Area", f"{p.area:.2f}", "µm²"),
                  Kpi("Latency", f"{p.latency:.2f}", f"ps · {p.schedule.n_steps} clock cycles")]
        for i, t in enumerate(tiles):
            kp.addWidget(t, i // 4, i % 4)
        self.body.addLayout(kp)
        lib = s.lib
        area_rows = [(f"{fu}", p.alloc[fu], f"{lib.fus[fu].area:.4f}", f"{p.alloc[fu] * lib.fus[fu].area:.4f}") for fu in s.dims]
        area_rows.append(("register", p.regs.n_registers, f"{lib.register_area:.4f}", f"{p.reg_area:.4f}"))
        if ev.include_mux_area:
            area_rows.append(("2:1 mux", p.mux2_count, f"{lib.mux_area:.4f}", f"{p.mux_area:.4f}"))
        area_rows.append(("Total area", "", "", f"{p.area:.4f}"))
        at = table(["Unit", "Count", "Area each (µm²)", "Area (µm²)"], area_rows, align_right=(1, 2, 3))
        lat_rows = []
        for k, ops in enumerate(p.schedule.steps, 1):
            slow = max(ops, key=lambda o: lib.fus[s.dfg.ops[o].fu_type].latency)
            lat_rows.append((f"CS{k}", " ".join(f"{OP_SYMBOL[s.dfg.ops[o].op_type]}{o}" for o in ops),
                             s.dfg.ops[slow].fu_type, f"{p.schedule.step_latency[k - 1]:.4f}"))
        lat_rows.append(("Total latency", "", "", f"{p.latency:.4f}"))
        lt = table(["Cycle", "Operations", "Slowest unit", "Length (ps)"], lat_rows, align_right=(3,), fit=False)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(_wrap(at, "Area breakdown"))
        ll.addStretch(1)
        self.body.addWidget(_splitter(left, _wrap(lt, "Latency: slowest operation of each cycle"),
                                      sizes=[480, 560]), 1)
        a_term = ev.t1 * (p.area - ev.ac) / ev.amax
        l_term = ev.t2 * (p.latency - ev.lc) / ev.lmax
        auto = abs(ev.ac - ev.amax) < 1e-9 and abs(ev.lc - ev.lmax) < 1e-9
        f = (f"<b>Design cost</b> = t1·(A − A<sub>c</sub>)/A<sub>max</sub> + t2·(L − L<sub>c</sub>)/L<sub>max</sub><br>"
             f"= {ev.t1:g} × ({p.area:.2f} − {ev.ac:.2f}) / {ev.amax:.2f} + {ev.t2:g} × ({p.latency:.2f} − {ev.lc:.2f}) / {ev.lmax:.2f}<br>"
             f"= {a_term:.4f} + {l_term:.4f} = <b>{p.cost:.4f}</b><br>"
             f"<span style='color:#4b5563'>A<sub>max</sub> = area with the most hardware, L<sub>max</sub> = latency with the least "
             f"hardware. Constraints A<sub>c</sub>, L<sub>c</sub> " +
             ("are set to A<sub>max</sub>, L<sub>max</sub>, so every design's cost is negative." if auto else "were set by you.") +
             "</span>")
        self.body.addWidget(_wrap(label(f, wrap=True, rich=True), "How the cost is computed"))


class HelpWindow(OutputWindow):
    def __init__(self, parent):
        super().__init__(parent, "How to use PSO HLS Explorer", None, size=(880, 820))
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setStyleSheet("QTextBrowser { background: #ffffff; border: 1px solid #dde2ea; border-radius: 12px; padding: 14px; }")
        tb.setHtml("""
<h2 style="color:#14213d">PSO HLS Explorer</h2>
<p><b>Made by</b> Devansh Singhal, Deepak Kumar, Dhristi, Kshaunish and Anshul Gupta.</p>
<p>The tool takes an algorithm written as a <b>data-flow graph</b> (additions and multiplications) and a <b>library</b>
of hardware units, and finds how many adders and multipliers the chip should have so that <b>chip area</b> and
<b>speed (latency)</b> are best balanced. The search uses <b>particle swarm optimisation (PSO)</b> as described in
A. Anshul &amp; A. Sengupta, <i>Expert Systems with Applications</i> 223 (2023), with the 15 nm open cell library.</p>

<h3>Top bar</h3>
<ul>
<li><b>Read me!</b> opens this guide.</li>
<li><b>Reset</b> clears everything and starts again from step 1.</li>
<li>The blue <b>Next →</b> banner always tells you what to do next. It turns green when all steps are done.</li>
</ul>

<h3>Input panel (left): do the steps in order</h3>
<p>A step is <b>greyed out and locked</b> until the step before it is done. Doing an earlier step again clears the later ones.</p>
<ol>
<li><b>Load DFG file…</b> chooses your application file. <b>DCT 4-point / DCT 8-point / DWT</b> load a sample instead.</li>
<li><b>Load library file…</b> chooses the module library. <b>Use sample library</b> loads the library that belongs to the sample.</li>
<li><b>3 / 5 / 7 particles</b> choose which swarm sizes to run (each is a separate run). <b>Max iterations</b> is the hard
 limit (50) and <b>Stop if no improvement for</b> ends a run early (10). <b>Advanced settings</b> hold the PSO factors
 f1 = f2, k1 = k2, the random seed, the area weight t1, the constraints Ac / Lc (empty = automatic) and the mux-area
 option. <b>Run PSO exploration</b> starts the search and opens the animated replay.</li>
<li><b>Design</b> picks which result to continue with (the best overall, or the best of one swarm size).
 <b>Generate scheduled design</b> puts every operation into a clock cycle.</li>
<li><b>Generate register allocation table</b> decides which register stores each value.</li>
<li><b>Compute design cost</b> works out area, latency and the design cost.</li>
</ol>

<h3>Status panel (middle)</h3>
<p>One tile per step: grey = waiting · <span style="color:#2563eb"><b>blue = do this next</b></span> ·
<span style="color:#b45309"><b>amber = running</b></span> · <span style="color:#15803d"><b>green = done</b></span> (with the result) ·
<span style="color:#c62828"><b>red = error</b></span> (the message says what is wrong with the file or setting).</p>

<h3>Output panel (right): every button opens a window</h3>
<p>A button shows a lock until the step that produces it is done. The newest outputs get a blue outline.</p>
<ul>
<li><b>View data-flow graph</b> shows the application as a graph and the file as a table (operation, operand 1, operand 2, number).</li>
<li><b>View module library</b> shows the area, delay and number available of each unit, and how many designs are possible.</li>
<li><b>Watch PSO exploration</b> is an animated replay of the search. Each square is a design; orange dots are particles;
 the black frame with ★ is the best design so far. Use ▶, the arrows or the slider. The panel on the right explains every step.</li>
<li><b>View convergence graph</b> plots the best cost after every iteration for each swarm size.</li>
<li><b>Compare swarm sizes</b> shows a table and a chart of iterations, convergence time and exploration time for N = 3, 5, 7.</li>
<li><b>View area–latency trade-off</b> plots every design's area against its latency, with the Pareto front and the chosen design.</li>
<li><b>View scheduled design</b> shows which operation runs in which clock cycle on which unit, and how long each cycle is.</li>
<li><b>View register allocation table</b> is the RAT in the format of Table 1 of the paper, with a short guide to reading it.</li>
<li><b>View datapath interconnect</b> lists the multiplexers and demultiplexers needed because units and registers are reused.</li>
<li><b>View area, latency &amp; design cost</b> shows the final numbers and the cost formula filled in step by step.</li>
<li><b>Export all results…</b> saves every chart, table and text report into a folder of your choice.</li>
</ul>
<p>Chart windows have a <b>Save image…</b> button (PNG, PDF or SVG). The <b>activity log</b> at the bottom of the main window records every step.</p>

<h3>Words used</h3>
<ul>
<li><b>Control step / clock cycle</b>: one time slot of the schedule; it lasts as long as its slowest operation.</li>
<li><b>Latency</b>: total time of all cycles (register delay is ignored).</li>
<li><b>Area</b>: area of all units plus registers.</li>
<li><b>Design cost</b>: t1·(A−Ac)/Amax + t2·(L−Lc)/Lmax; more negative is better.</li>
<li><b>Convergence time</b>: time until the final best design was first found. <b>Exploration time</b>: total search time.</li>
<li><b>Pareto front</b>: designs that cannot get smaller without getting slower.</li>
</ul>

<h3>Input file formats</h3>
<p><b>DFG:</b> groups of four values <code>operation, operand 1, operand 2, operation number</code>; operations
<code>+ - *</code>; operand 0 = primary input. Example: <code>*,0,0,1,*,0,0,2,+,1,2,3</code><br>
<b>Library:</b> one line per unit, e.g. <code>adder(16),0.739pj,18.8744um,66.2428ps,18.6um,70.0ps,4</code>
(the last number is how many are available) and <code>register,0.7864um,25.9108ps</code>.</p>
""")

        self.body.addWidget(tb, 1)
