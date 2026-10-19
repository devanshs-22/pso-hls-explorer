"""Plain-text reports shared by the command line (main.py) and the desktop app."""
import re

from .io import OP_SYMBOL
from .registers import fu_label, register_colour


def fmt_pos(pos, dims):
    return "(" + ", ".join(f"{n}{d[0].upper()}" for n, d in zip(pos, dims)) + ")"


def config_text(p, dims):
    """'1 adder, 2 multipliers' for a DesignPoint (or a bare position tuple)."""
    pos = p.position if hasattr(p, "position") else p
    return ", ".join(f"{n} {d}{'s' if n > 1 else ''}" for n, d in zip(pos, dims))


def reg_names(text):
    """Replace 'R-3' with the register's colour name ('Blue')."""
    return re.sub(r"R-(\d+)", lambda g: register_colour(int(g.group(1)))[0], text)


def design_report(p, dfg, ev):
    s, regs, lib = p.schedule, p.regs, ev.lib
    units = [(fu, i) for fu in ev.dims for i in range(p.alloc[fu])]
    L = [f"Resource configuration : {config_text(p, ev.dims)}", ""]
    L.append("SCHEDULE (control step x functional unit)")
    head = f"{'CS':<4}| " + " | ".join(f"{fu_label(*u):<5}" for u in units) + " | step latency"
    L += [head, "-" * len(head)]
    for k, ops in enumerate(s.steps, 1):
        cell = {s.binding[o]: f"{OP_SYMBOL[dfg.ops[o].op_type]}{o}" for o in ops}
        L.append(f"{k:<4}| " + " | ".join(f"{cell.get(u, '-'):<5}" for u in units)
                 + f" | {s.step_latency[k - 1]:.4f} ps")
    L += ["", "REGISTER ALLOCATION TABLE (as Table 1 of the paper: C0 = inputs, Ck = after control step k)"]
    n_cols = len(regs.table)
    L.append(f"{'':<16}" + "".join(f"{'C' + str(b):<6}" for b in range(n_cols)))
    for r in range(regs.n_registers):
        name, abbr, _ = register_colour(r)
        L.append(f"{name + ' (' + abbr + ')':<16}" + "".join(f"{(regs.table[b][r] or '–'):<6}" for b in range(n_cols)))
    L += ["", "Variables:"]
    for v in regs.variables.values():
        L.append(f"  {v.name:<4} -> {register_colour(v.register)[0]:<9} {regs.describe(v.name):<18} "
                 f"live over boundaries {v.birth}..{v.last}")
    L += ["", "INTERCONNECT (multiplexers / demultiplexers)"]
    L += [f"  {reg_names(loc):<12} {kind}" for loc, kind in p.muxes] or ["  none"]
    L.append(f"  equivalent 2:1 muxes = {p.mux2_count}  (area {p.mux_area:.4f} um^2, "
             f"{'included in' if ev.include_mux_area else 'NOT included in'} design area)")
    L += ["", "METRICS"]
    for fu in ev.dims:
        f = lib.fus[fu]
        L.append(f"  {fu:<11} {p.alloc[fu]} x {f.area} um^2 = {p.alloc[fu] * f.area:.4f} um^2")
    L.append(f"  registers   {regs.n_registers} x {lib.register_area} um^2 = {p.reg_area:.4f} um^2")
    L.append(f"  Area    = {p.area:.4f} um^2          (Amax = {ev.amax:.4f})")
    L.append(f"  Latency = {p.latency:.4f} ps  = {s.n_steps} control steps  (Lmax = {ev.lmax:.4f})")
    L.append(f"  Cost    = {ev.t1}*({p.area:.4f}-{ev.ac:.4f})/{ev.amax:.4f} + "
             f"{ev.t2}*({p.latency:.4f}-{ev.lc:.4f})/{ev.lmax:.4f} = {p.cost:.10f}")
    return "\n".join(L)


def iteration_report(res, dims):
    L = []
    for h in res.history:
        w = "  -  " if h["w"] is None else f"{h['w']:.3f}"
        parts = "  ".join(f"{fmt_pos(p, dims)}={c:.4f}" for p, c in zip(h["particles"], h["costs"]))
        L.append(f"iter {h['iteration']:>2}  w={w}  after update: {parts}")
        if h["mutated"]:
            parts = "  ".join(f"{fmt_pos(p, dims)}={c:.4f}"
                              for p, c in zip(h["mutated"], h["mutated_costs"]))
            L.append(f"{'':<17}after mutation: {parts}")
        L.append(f"{'':<17}gbest = {fmt_pos(h['gbest'], dims)} cost {h['gbest_cost']:.6f}"
                 f"   t = {h['elapsed_ms']:.3f} ms")
    L.append(f"\nStopped after {res.iterations_run} iterations: {res.stop_reason}")
    L.append(f"Converged at iteration {res.convergence_iter}: "
             f"convergence time {res.convergence_time_ms:.3f} ms, "
             f"exploration time {res.exploration_time_ms:.3f} ms")
    return "\n".join(L)


def summary_markdown(ex, cfg_text):
    """Markdown summary of an Exploration (see explore.py)."""
    dims, probe = ex.dims, ex.probe
    L = [f"# {ex.dfg.name}", "",
         f"- Operations: {len(ex.dfg.ops)}, primary inputs: {ex.n_inputs}",
         "- Search space: " + ", ".join(f"{d} {lo}–{hi}" for d, lo, hi in
                                        zip(dims, probe.lower, probe.upper)) + f" ({ex.space} designs)",
         f"- Amax = {probe.amax:.4f} µm² (max resources), Lmax = {probe.lmax:.4f} ps (min resources)",
         f"- Ac = {probe.ac:.4f} µm², Lc = {probe.lc:.4f} ps",
         f"- PSO: {cfg_text}", "",
         "| N | Best config | Area (µm²) | Latency (ps) | Registers | Cost | Iterations | Converged at | "
         "Convergence time (ms) | Exploration time (ms) | Designs visited |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, r in ex.runs:
        b = r.best
        L.append(f"| {n} | {config_text(b, dims)} | {b.area:.4f} | {b.latency:.4f} | "
                 f"{b.regs.n_registers} | {b.cost:.6f} | {r.iterations_run} | {r.convergence_iter} | "
                 f"{r.convergence_time_ms:.3f} | {r.exploration_time_ms:.3f} | "
                 f"{len(r.explored)}/{ex.space} |")
    if ex.exhaustive:
        L += ["", f"Exhaustive check (done after the runs, for validation only): the minimum-cost design "
              f"is **{config_text(ex.true_best, dims)}** with cost {ex.true_best.cost:.6f} — "
              + ("every" if ex.all_found_optimum else "NOT every") + " PSO run found it."]
    L += ["", "Pareto-optimal designs (no other design is both smaller and faster):", "",
          "| Config | Area (µm²) | Latency (ps) | Cost |", "|---|---|---|---|"]
    L += [f"| {config_text(p, dims)} | {p.area:.4f} | {p.latency:.4f} | {p.cost:.6f} |" for p in ex.pareto]
    return "\n".join(L) + "\n"
