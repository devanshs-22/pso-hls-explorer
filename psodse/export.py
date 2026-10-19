"""Write every figure and report of an Exploration into a folder (CLI and desktop app)."""
import os

from .plots import plot_convergence, plot_dfg, plot_rat, plot_schedule, plot_times, plot_tradeoff
from .report import config_text, design_report, iteration_report, summary_markdown


def write_results(ex, out, stall, max_iter, cfg_text):
    """Write every figure and report of an Exploration into folder `out`."""
    dfg, dims, probe = ex.dfg, ex.dims, ex.probe
    os.makedirs(out, exist_ok=True)
    plot_dfg(dfg, os.path.join(out, "dfg.png"), f"{dfg.name} — data-flow graph")
    for n, res in ex.runs:
        b = res.best
        d = os.path.join(out, f"N{n}")
        os.makedirs(d, exist_ok=True)
        title = f"{dfg.name} · {config_text(b, dims)} · N={n}"
        plot_schedule(b, dfg, dims, os.path.join(d, "schedule.png"),
                      f"Scheduled DFG — {title}\nlatency {b.latency:.3f} ps in "
                      f"{b.schedule.n_steps} control steps")
        plot_rat(b, dfg, os.path.join(d, "rat.png"),
                 f"Register allocation table — {title} ({b.regs.n_registers} registers)")
        with open(os.path.join(d, "design.txt"), "w") as f:
            f.write(f"{dfg.name}   PSO with N = {n} particles\n\n" + design_report(b, dfg, probe) + "\n")
        with open(os.path.join(d, "iterations.txt"), "w") as f:
            f.write(iteration_report(res, dims) + "\n")
    best = probe.evaluate(ex.best_run[1].best.position)
    plot_convergence(ex.runs, os.path.join(out, "convergence.png"),
                     f"{dfg.name} — global best design cost per iteration",
                     stall_limit=stall, max_iter=max_iter)
    plot_tradeoff(ex.all_points, ex.visited, best, dims, os.path.join(out, "tradeoff.png"),
                  f"{dfg.name} — area vs latency trade-off")
    plot_times(ex.runs, os.path.join(out, "times.png"), f"{dfg.name} — convergence vs exploration time")
    with open(os.path.join(out, "summary.md"), "w") as f:
        f.write(summary_markdown(ex, cfg_text))
