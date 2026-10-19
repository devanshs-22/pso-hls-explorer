"""Web front end for the PSO explorer.

    .venv/bin/python app.py            # opens http://localhost:8000 in the browser
    .venv/bin/python app.py --port 9000 --no-browser

The browser page (web/) only draws things; every number comes from the same
psodse engine that main.py and the tests use.
"""
import argparse
import json
import os
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from psodse.cost import Evaluator
from psodse.io import OP_SYMBOL, parse_dfg, parse_library
from psodse.plots import pareto_front
from psodse.pso import PSO, PSOConfig
from psodse.registers import fu_label, register_colour

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web")
BENCHMARKS = [
    {"id": "DCT_4pt", "title": "DCT 4-point", "blurb": "Discrete cosine transform · 7 operations",
     "dfg": "inputs/DCT_4pt.txt", "lib": "inputs/DCT_4pt_lib.txt"},
    {"id": "DCT_8pt", "title": "DCT 8-point", "blurb": "Discrete cosine transform · 15 operations",
     "dfg": "inputs/DCT_8pt.txt", "lib": "inputs/DCT_8pt_lib.txt"},
    {"id": "DWT", "title": "DWT", "blurb": "Discrete wavelet transform · 17 operations",
     "dfg": "inputs/DWT_bechmark.txt", "lib": "inputs/DWT_lib.txt"},
]
MAX_DETAILED_DESIGNS = 400


def key(pos):
    return ",".join(map(str, pos))


def dfg_json(dfg):
    asap = {}
    for oid, op in dfg.ops.items():
        asap[oid] = 1 + max((asap[p] for p in op.predecessors), default=0)
    n_inputs = sum((op.operand1 == 0) + (op.operand2 == 0) for op in dfg.ops.values())
    return {
        "name": dfg.name,
        "n_inputs": n_inputs,
        "ops": [{"id": o.op_id, "type": o.op_type, "symbol": OP_SYMBOL[o.op_type], "fu": o.fu_type,
                 "operand1": o.operand1, "operand2": o.operand2, "preds": o.predecessors,
                 "succs": dfg.successors[o.op_id], "asap": asap[o.op_id]} for o in dfg.ops.values()],
    }


def library_json(lib):
    return {
        "fus": [{"name": f.name, "area": f.area, "latency": f.latency, "max": f.max_count,
                 "power": f.power} for f in lib.fus.values()],
        "register": {"area": lib.register_area, "latency": lib.register_latency},
        "mux": {"area": lib.mux_area, "latency": lib.mux_latency},
    }


def design_json(p, dfg, ev):
    s, regs = p.schedule, p.regs
    return {
        "key": key(p.position), "position": list(p.position), "alloc": p.alloc,
        "area": p.area, "latency": p.latency, "cost": p.cost,
        "area_terms": [{"fu": fu, "count": p.alloc[fu], "unit": ev.lib.fus[fu].area,
                        "total": p.alloc[fu] * ev.lib.fus[fu].area} for fu in ev.dims],
        "fu_area": p.fu_area, "reg_area": p.reg_area, "mux_area": p.mux_area,
        "mux2_count": p.mux2_count, "muxes": [list(m) for m in p.muxes],
        "n_registers": regs.n_registers, "n_steps": s.n_steps, "step_latency": s.step_latency,
        "steps": [[{"op": o, "unit": fu_label(*s.binding[o])} for o in st] for st in s.steps],
        "units": [fu_label(fu, i) for fu in ev.dims for i in range(p.alloc[fu])],
        "rat": regs.table,
        "reg_colors": [dict(zip(("name", "abbr", "hex"), register_colour(r))) for r in range(regs.n_registers)],
        "variables": [{"name": v.name, "register": v.register, "producer": v.producer,
                       "birth": v.birth, "last": v.last} for v in regs.variables.values()],
        "op_inputs": {str(o): list(v) for o, v in regs.op_inputs.items()},
        "op_output": {str(o): v for o, v in regs.op_output.items()},
    }


def load_inputs(payload):
    if payload.get("benchmark"):
        b = next((b for b in BENCHMARKS if b["id"] == payload["benchmark"]), None)
        if b is None:
            raise ValueError("unknown benchmark")
        with open(os.path.join(ROOT, b["dfg"])) as f:
            dfg_text = f.read()
        with open(os.path.join(ROOT, b["lib"])) as f:
            lib_text = f.read()
        name = b["id"]
    else:
        dfg_text, lib_text = payload.get("dfg_text", ""), payload.get("lib_text", "")
        name = payload.get("name") or "Uploaded application"
    try:
        dfg = parse_dfg(dfg_text, name, source="DFG file")
    except ValueError as e:
        raise ValueError(str(e) if "DFG file" in str(e) else f"DFG file: {e}")
    lib = parse_library(lib_text, source="library file")
    return dfg, lib


def _num_or_none(v):
    """'' / None / 'auto' -> None (use Amax / Lmax), otherwise a number."""
    return None if v in (None, "", "auto") else float(v)


def evaluator_for(dfg, lib, params):
    t1 = float(params.get("t1", 0.5))
    return Evaluator(dfg, lib, t1=t1, t2=1 - t1,
                     area_constraint=_num_or_none(params.get("ac")),
                     latency_constraint=_num_or_none(params.get("lc")),
                     include_mux_area=bool(params.get("include_mux_area", False)))


def describe(payload):
    dfg, lib = load_inputs(payload)
    ev = evaluator_for(dfg, lib, payload.get("params", {}))
    space = 1
    for lo, hi in zip(ev.lower, ev.upper):
        space *= hi - lo + 1
    return {"dfg": dfg_json(dfg), "library": library_json(lib), "dims": ev.dims,
            "lower": ev.lower, "upper": ev.upper, "space": space}


def run(payload):
    dfg, lib = load_inputs(payload)
    params = payload.get("params", {})
    particles = sorted({int(n) for n in params.get("particles", [3, 5, 7]) if 1 <= int(n) <= 50})
    if not particles:
        raise ValueError("choose at least one swarm size")
    k = params.get("k", "random")
    k = "random" if k == "random" else float(k)
    probe = evaluator_for(dfg, lib, params)
    space = 1
    for lo, hi in zip(probe.lower, probe.upper):
        space *= hi - lo + 1

    runs, designs = [], {}
    for n in particles:
        ev = evaluator_for(dfg, lib, params)
        cfg = PSOConfig(n_particles=n, max_iter=int(params.get("max_iter", 50)),
                        stall_limit=int(params.get("stall", 10)), f1=float(params.get("f", 2)),
                        f2=float(params.get("f", 2)), k=k, seed=int(params.get("seed", 1)))
        res = PSO(ev, cfg).run()
        for p in res.explored:
            designs.setdefault(key(p), None)
        runs.append({
            "n": n, "best": key(res.best.position), "best_cost": res.best.cost,
            "convergence_iter": res.convergence_iter, "convergence_time_ms": res.convergence_time_ms,
            "exploration_time_ms": res.exploration_time_ms, "iterations_run": res.iterations_run,
            "stop_reason": res.stop_reason, "explored": [key(p) for p in res.explored],
            "history": [{"iteration": h["iteration"], "w": h["w"],
                         "particles": [list(p) for p in h["particles"]], "costs": h["costs"],
                         "mutated": [list(p) for p in h["mutated"]] if h["mutated"] else None,
                         "mutated_costs": h["mutated_costs"], "gbest": list(h["gbest"]),
                         "gbest_cost": h["gbest_cost"], "elapsed_ms": h["elapsed_ms"]}
                        for h in res.history],
        })

    exhaustive = space <= MAX_DETAILED_DESIGNS
    positions = probe.all_positions() if exhaustive else [tuple(map(int, s.split(","))) for s in designs]
    points = [probe.evaluate(p) for p in positions]
    optimum = min(points, key=lambda p: p.cost)
    return {
        "dfg": dfg_json(dfg), "library": library_json(lib), "dims": probe.dims,
        "lower": probe.lower, "upper": probe.upper, "space": space, "exhaustive": exhaustive,
        "amax": probe.amax, "lmax": probe.lmax, "t1": probe.t1, "t2": probe.t2,
        "ac": probe.ac, "lc": probe.lc, "include_mux_area": probe.include_mux_area,
        "params": {"max_iter": int(params.get("max_iter", 50)), "stall": int(params.get("stall", 10)),
                   "f": float(params.get("f", 2)), "k": k, "seed": int(params.get("seed", 1))},
        "runs": runs,
        "designs": {key(p.position): design_json(p, dfg, probe) for p in points},
        "pareto": [key(p.position) for p in pareto_front(points)],
        "optimum": key(optimum.position),
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WEB, **kw)

    def log_message(self, fmt, *args):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/benchmarks":
            return self._json(200, [{k: b[k] for k in ("id", "title", "blurb")} for b in BENCHMARKS])
        return super().do_GET()

    def do_POST(self):
        routes = {"/api/describe": describe, "/api/run": run}
        if self.path not in routes:
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            return self._json(200, routes[self.path](payload))
        except (ValueError, KeyError, TypeError) as e:
            return self._json(400, {"error": str(e)})


def main():
    ap = argparse.ArgumentParser(description="PSO explorer web front end")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://localhost:{args.port}"
    print(f"PSO Architecture Explorer running at {url}   (Ctrl+C to stop)")
    if not args.no_browser:
        threading.Timer(0.6, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
