"""All figures: DFG, scheduled DFG, RAT, convergence, area-latency trade-off, timing.

Every chart has a ``fig_*`` function that returns a matplotlib Figure (no pyplot, so the
desktop app can embed it in a window) and a ``plot_*`` wrapper that saves it to a file
(used by main.py).
"""
import matplotlib
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch

from .io import OP_SYMBOL
from .registers import fu_label, register_colour

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3de"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]           # categorical slots 1..3 (fixed order)
FU_COLOR = {"adder": SERIES[0], "multiplier": SERIES[1], "subtractor": SERIES[2]}

matplotlib.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "text.color": INK, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
    "axes.edgecolor": GRID, "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False,
})


def _style_axes(ax):
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def save(fig, path):
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())


def _draw_graph(ax, nodes, edges, n_cols, n_rows):
    """nodes: {id: (x, y, colour, label, input_labels, out_label)}; edges: [(from, to)]."""
    for a, b in edges:
        (x0, y0), (x1, y1) = nodes[a][:2], nodes[b][:2]
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=10,
                                     color=INK_2, lw=1, shrinkA=15, shrinkB=15,
                                     connectionstyle="arc3,rad=0.12" if x0 == x1 and y1 - y0 > 1 else "arc3"))
    for x, y, colour, label, ins, out in nodes.values():
        if ins:
            ax.text(x, y - 0.38, ",".join(ins), ha="center", va="bottom", fontsize=7, color=INK_2)
        if out:
            ax.text(x, y + 0.36, out, ha="center", va="top", fontsize=7, color=INK_2)
        ax.scatter([x], [y], s=620, color=colour, edgecolor=SURFACE, lw=2, zorder=3)
        ax.text(x, y, label, ha="center", va="center", color="white", fontsize=9,
                fontweight="bold", zorder=4)


def _fu_legend(ax, fus):
    handles = [Line2D([], [], marker="o", ls="", ms=9, color=FU_COLOR[fu], label=fu) for fu in fus]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=len(fus),
              frameon=False)


# ---------------------------------------------------------------------------
def fig_dfg(dfg, title=None):
    """The unscheduled data-flow graph, one row per ASAP level (earliest possible step)."""
    asap = {}
    for oid, op in dfg.ops.items():
        asap[oid] = 1 + max((asap[p] for p in op.predecessors), default=0)
    levels = {}
    for oid, lv in asap.items():
        levels.setdefault(lv, []).append(oid)
    n_cols = max(len(v) for v in levels.values())
    nodes = {}
    for lv, ids in levels.items():
        off = (n_cols - len(ids)) / 2
        for i, oid in enumerate(ids):
            op = dfg.ops[oid]
            n_in = (op.operand1 == 0) + (op.operand2 == 0)
            nodes[oid] = (off + i, lv, FU_COLOR[op.fu_type], f"{OP_SYMBOL[op.op_type]}{oid}",
                          ["in"] * n_in, None if dfg.successors[oid] else "output")
    edges = [(p, o) for o, op in dfg.ops.items() for p in op.predecessors]
    fig = Figure(figsize=(max(4.5, 0.9 * n_cols + 1.5), max(3.5, 0.95 * len(levels) + 1.4)))
    ax = fig.subplots()
    ax.set_xlim(-0.8, n_cols - 0.2)
    ax.set_ylim(len(levels) + 0.8, 0.2)
    ax.axis("off")
    _draw_graph(ax, nodes, edges, n_cols, len(levels))
    _fu_legend(ax, sorted({op.fu_type for op in dfg.ops.values()}))
    if title:
        ax.set_title(title, loc="left")
    return fig


def fig_schedule(point, dfg, dims, title):
    """Scheduled DFG: one column per FU instance, one row per control step."""
    sched, regs = point.schedule, point.regs
    columns = [(fu, i) for fu in dims for i in range(point.alloc[fu])
               if any(b == (fu, i) for b in sched.binding.values())]
    col_x = {c: k for k, c in enumerate(columns)}
    fig = Figure(figsize=(max(5.0, 1.25 * len(columns) + 3.2), max(3.5, 0.95 * sched.n_steps + 1.8)))
    ax = fig.subplots()
    ax.set_xlim(-1.2, len(columns) + 0.4)
    ax.set_ylim(sched.n_steps + 0.9, 0.1)
    ax.axis("off")
    for s in range(1, sched.n_steps + 1):
        ax.axhspan(s - 0.5, s + 0.5, color=GRID if s % 2 else SURFACE, alpha=0.35, lw=0)
        ax.text(-1.1, s, f"CS{s}", va="center", ha="left", color=INK_2, fontweight="bold")
        ax.text(len(columns) - 0.35, s, f"{sched.step_latency[s - 1]:.2f} ps",
                va="center", ha="left", color=INK_2, fontsize=9)
    for c, k in col_x.items():
        busy = sum(1 for st in sched.steps if any(sched.binding[o] == c for o in st))
        ax.text(k, 0.22, fu_label(*c), ha="center", va="center", fontweight="bold", color=INK)
        ax.text(k, 0.42, f"busy {busy}/{sched.n_steps}", ha="center", va="center", fontsize=7.5, color=INK_2)
    nodes = {}
    for o, op in dfg.ops.items():
        ins = [v for v, operand in zip(regs.op_inputs[o], (op.operand1, op.operand2)) if operand == 0]
        nodes[o] = (col_x[sched.binding[o]], sched.op_step[o], FU_COLOR[op.fu_type],
                    f"{OP_SYMBOL[op.op_type]}{o}", ins,
                    None if dfg.successors[o] else f"out {regs.op_output[o]}")
    edges = [(p, o) for o, op in dfg.ops.items() for p in op.predecessors]
    _draw_graph(ax, nodes, edges, len(columns), sched.n_steps)
    _fu_legend(ax, dims)
    ax.set_title(title, loc="left")
    return fig


def fig_rat(point, dfg, title):
    """RAT exactly in the format of Table 1 of the paper: one row per register named by
    its colour ("Red (R)", "Green (G)", ...), one column per control step C0..Cn, each cell
    the storage variable held by that register in that step, "–" when it holds nothing."""
    table, n_regs = point.regs.table, point.regs.n_registers
    n_cols = len(table)
    rows = [f"{name} ({abbr})" for name, abbr, _ in (register_colour(r) for r in range(n_regs))]
    cells = [[table[b][r] or "–" for b in range(n_cols)] for r in range(n_regs)]
    fig = Figure(figsize=(max(5.0, 0.62 * n_cols + 1.6), 0.27 * (n_regs + 1) + 0.4), facecolor="white")
    ax = fig.subplots()
    ax.axis("off")
    t = ax.table(cellText=cells, rowLabels=rows, colLabels=[f"C{b}" for b in range(n_cols)],
                 cellLoc="center", rowLoc="left", bbox=[0, 0, 1, 1])
    t.auto_set_font_size(False)
    t.set_fontsize(9)
    for (i, j), c in t.get_celld().items():
        c.set_facecolor("white")
        c.set_edgecolor("#c9c8c2")
        c.set_linewidth(0.6)
        c.get_text().set_color(INK)
        if i == 0:
            c.set_text_props(fontweight="bold")
    ax.set_title(title, pad=8, fontsize=11)
    n_in = sum((op.operand1 == 0) + (op.operand2 == 0) for op in dfg.ops.values())
    ax.text(0, -0.02, f"V0–V{n_in - 1}: primary inputs · V{n_in}–V{n_in + len(dfg.ops) - 1}: outputs of "
            f"op1–op{len(dfg.ops)}.  C0 = inputs, Ck = values held after control step k.",
            fontsize=7.5, color=INK_2, transform=ax.transAxes, va="top")
    return fig


def fig_convergence(runs, title, stall_limit=10, max_iter=50):
    """runs: list of (n_particles, PSOResult). One panel per swarm size, x axis up to the
    hard iteration limit, with the 'stalled for N iterations -> stop' window marked."""
    fig = Figure(figsize=(3.6 * len(runs) + 0.6, 3.8))
    axes = fig.subplots(1, len(runs), sharey=True, squeeze=False)[0]
    for k, (ax, (n, res)) in enumerate(zip(axes, runs)):
        _style_axes(ax)
        colour = SERIES[k % len(SERIES)]
        xs = [h["iteration"] for h in res.history]
        ys = [h["gbest_cost"] for h in res.history]
        ax.step(xs, ys, where="post", color=colour, lw=2)
        ci, last = res.convergence_iter, res.iterations_run
        ax.plot([ci], [res.best.cost], "o", ms=8, color=colour, mec=SURFACE, mew=2, zorder=3)
        if last > ci:
            ax.axvspan(ci, last, color=GRID, alpha=0.6, lw=0)
            ax.text((ci + last) / 2, 0.97, f"{last - ci} without\nimprovement → stop",
                    transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=7.5, color=INK_2)
        ax.annotate(f"best found at iteration {ci}", (ci, res.best.cost), xytext=(6, -16),
                    textcoords="offset points", fontsize=7.5, color=INK_2)
        ax.axvline(max_iter, color=INK_2, ls=":", lw=1)
        ax.set_xlim(-0.5, max(max_iter, last) + 1)
        ax.set_title(f"N = {n} particles", fontsize=10, loc="left")
        ax.set_xlabel("Iteration")
    axes[0].set_ylabel("Global best design cost")
    fig.suptitle(title, x=0.01, ha="left", fontweight="bold")
    fig.text(0.01, 0.005, f"Dotted line = hard limit of {max_iter} iterations. Shaded = the {stall_limit} "
             "iterations without improvement that triggered the stop.", fontsize=7.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def pareto_front(points):
    """Non-dominated points in (latency, area), both minimised."""
    front = [p for p in points
             if not any((q.latency <= p.latency and q.area <= p.area)
                        and (q.latency < p.latency or q.area < p.area) for q in points)]
    return sorted(front, key=lambda p: p.latency)


def fig_tradeoff(all_points, visited, best, dims, title):
    fig = Figure(figsize=(7.5, 5))
    ax = fig.subplots()
    _style_axes(ax)
    unvisited = [p for p in all_points if p.position not in visited]
    seen = [p for p in all_points if p.position in visited]
    front = pareto_front(all_points)
    ax.plot([p.latency for p in front], [p.area for p in front], color=INK_2, lw=1.2, ls="--",
            label="Pareto front (area vs latency)", zorder=1)
    if unvisited:
        ax.scatter([p.latency for p in unvisited], [p.area for p in unvisited], s=46,
                   facecolor="none", edgecolor="#a3a29c", lw=1.5,
                   label="design not visited by PSO", zorder=2)
    ax.scatter([p.latency for p in seen], [p.area for p in seen], s=46, color=SERIES[0],
               edgecolor=SURFACE, lw=1.5, label="design visited by PSO", zorder=3)
    ax.scatter([best.latency], [best.area], s=240, marker="*", color=SERIES[1],
               edgecolor=SURFACE, lw=1.5, label="chosen design (min cost)", zorder=4)
    abbrev = ", ".join(f"#{d}s" for d in dims)
    for p in all_points:
        ax.annotate(",".join(map(str, p.position)), (p.latency, p.area), xytext=(5, 4),
                    textcoords="offset points", fontsize=7, color=INK_2)
    ax.set_xlabel("Latency (ps)  →  slower")
    ax.set_ylabel("Area (µm²)  →  bigger")
    ax.set_title(title, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    note = f"Point labels = resource configuration ({abbrev})."
    if unvisited:
        note += " Grey points were never visited by PSO; they are evaluated afterwards only for this plot."
    fig.text(0.01, 0.005, note, fontsize=8, color=INK_2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    return fig


def fig_times(runs, title):
    fig = Figure(figsize=(6.5, 4))
    ax = fig.subplots()
    _style_axes(ax)
    ax.grid(axis="x", visible=False)
    xs = range(len(runs))
    wdt = 0.36
    ax.bar([x - wdt / 2 - 0.01 for x in xs], [r.convergence_time_ms for _, r in runs], wdt,
           color=SERIES[0], label="Convergence time")
    ax.bar([x + wdt / 2 + 0.01 for x in xs], [r.exploration_time_ms for _, r in runs], wdt,
           color=SERIES[1], label="Exploration time")
    ax.set_xticks(list(xs), [f"N = {n}" for n, _ in runs])
    ax.set_ylabel("Time (ms)")
    ax.set_title(title, loc="left", pad=30)
    ax.legend(frameon=False, ncol=2, loc="lower left", bbox_to_anchor=(0, 1.0), borderaxespad=0.2)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# file-saving wrappers used by main.py
def plot_dfg(dfg, path, title=None):
    save(fig_dfg(dfg, title), path)


def plot_schedule(point, dfg, dims, path, title):
    save(fig_schedule(point, dfg, dims, title), path)


def plot_rat(point, dfg, path, title):
    save(fig_rat(point, dfg, title), path)


def plot_convergence(runs, path, title, stall_limit=10, max_iter=50):
    save(fig_convergence(runs, title, stall_limit, max_iter), path)


def plot_tradeoff(all_points, visited, best, dims, path, title):
    save(fig_tradeoff(all_points, visited, best, dims, title), path)


def plot_times(runs, path, title):
    save(fig_times(runs, title), path)
