"""PSO based architecture exploration for HLS — run it on one or all benchmarks.

    python main.py                                   # all 3 benchmarks, N = 3, 5, 7
    python main.py --dfg inputs/DCT_4pt.txt --lib inputs/DCT_4pt_lib.txt
    python main.py --particles 3 5 7 --seed 7 --stall 15
"""
import argparse
import os

from psodse.explore import explore
from psodse.export import write_results
from psodse.io import read_dfg, read_library
from psodse.report import config_text, fmt_pos

BENCHMARKS = [("inputs/DCT_4pt.txt", "inputs/DCT_4pt_lib.txt"),
              ("inputs/DCT_8pt.txt", "inputs/DCT_8pt_lib.txt"),
              ("inputs/DWT_bechmark.txt", "inputs/DWT_lib.txt")]


def run_benchmark(dfg_path, lib_path, args):
    dfg, lib = read_dfg(dfg_path), read_library(lib_path)
    ex = explore(dfg, lib, particles=args.particles, max_iter=args.max_iter, stall=args.stall,
                 f=args.f, k=args.k, seed=args.seed, t1=args.t1, ac=args.ac, lc=args.lc,
                 include_mux_area=args.include_mux_area)
    dims, probe = ex.dims, ex.probe
    print(f"\n=== {dfg.name}: {len(dfg.ops)} ops, {ex.n_inputs} inputs | search space "
          + " x ".join(f"{d} {lo}..{hi}" for d, lo, hi in zip(dims, probe.lower, probe.upper))
          + f" = {ex.space} designs")
    for n, res in ex.runs:
        b = res.best
        print(f"  N={n}: best {fmt_pos(b.position, dims):<10} area {b.area:9.4f} um^2  "
              f"latency {b.latency:9.4f} ps  cost {b.cost:.6f}  | "
              f"{res.iterations_run} iters, converged @ {res.convergence_iter}, "
              f"conv {res.convergence_time_ms:.3f} ms, expl {res.exploration_time_ms:.3f} ms, "
              f"{len(res.explored)}/{ex.space} designs visited")
    out = os.path.join(args.out, dfg.name)
    cfg_text = (f"f1 = f2 = {args.f}, k = {args.k}, ω 0.9→0.1, max {args.max_iter} iterations, "
                f"stop after {args.stall} without improvement, seed {args.seed}")
    write_results(ex, out, args.stall, args.max_iter, cfg_text)
    if ex.exhaustive:
        print(f"  exhaustive optimum {fmt_pos(ex.true_best.position, dims)} cost {ex.true_best.cost:.6f}"
              f"  -> results in {out}/")
    return dfg.name, ex.runs, dims


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dfg", help="application DFG file (default: run all benchmarks in inputs/)")
    ap.add_argument("--lib", help="module library file for --dfg")
    ap.add_argument("--particles", type=int, nargs="+", default=[3, 5, 7])
    ap.add_argument("--max-iter", type=int, default=50)
    ap.add_argument("--stall", type=int, default=10, help="stop after this many iterations w/o improvement")
    ap.add_argument("--f", type=float, default=2.0, help="social & cognitive factor f1 = f2")
    ap.add_argument("--k", default="random", help="'random' (U(0,1)) or a fixed value for k1 = k2")
    ap.add_argument("--t1", type=float, default=0.5, help="area weight (latency weight t2 = 1 - t1)")
    ap.add_argument("--ac", type=float, default=None,
                    help="area constraint Ac in um^2 (default: Amax, which makes every cost negative)")
    ap.add_argument("--lc", type=float, default=None,
                    help="latency constraint Lc in ps (default: Lmax)")
    ap.add_argument("--include-mux-area", action="store_true", help="add 2:1 mux area to design area")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="results")
    args = ap.parse_args()
    if args.k != "random":
        args.k = float(args.k)

    if bool(args.dfg) != bool(args.lib):
        ap.error("--dfg and --lib go together")
    benches = [(args.dfg, args.lib)] if args.dfg else BENCHMARKS
    rows = [run_benchmark(d, l, args) for d, l in benches]

    L = ["# PSO architecture exploration — all benchmarks", "",
         "| Benchmark | N | Best config | Area (µm²) | Latency (ps) | Cost | Conv. iter | "
         "Conv. time (ms) | Expl. time (ms) |", "|---|---|---|---|---|---|---|---|---|"]
    for name, runs, dims in rows:
        for n, r in runs:
            b = r.best
            L.append(f"| {name} | {n} | {config_text(b, dims)} | {b.area:.4f} | {b.latency:.4f} | "
                     f"{b.cost:.6f} | {r.convergence_iter} | {r.convergence_time_ms:.3f} | "
                     f"{r.exploration_time_ms:.3f} |")
    with open(os.path.join(args.out, "SUMMARY.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"\nOverall summary: {args.out}/SUMMARY.md")


if __name__ == "__main__":
    main()
