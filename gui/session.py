"""The six-step pipeline behind the desktop app, without any GUI code.

    1 load application (DFG)   2 load module library   3 PSO exploration
    4 list scheduling          5 register allocation   6 area / latency / design cost

Each step really runs its part of the engine, using the design chosen after step 3.
Re-running a step throws away the results of every later step.
"""
import os
import sys
from dataclasses import dataclass

from psodse.cost import Evaluator
from psodse.explore import explore
from psodse.io import parse_dfg, parse_library
from psodse.registers import allocate_registers, interconnect
from psodse.report import config_text
from psodse.scheduler import list_schedule

STEP_NAMES = {1: "Application graph", 2: "Module library", 3: "PSO exploration",
              4: "Scheduled design", 5: "Register allocation", 6: "Design cost"}


def resource_path(rel):
    """Path of a bundled file, both when run from source and inside the packaged app."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, rel)


SAMPLES = {
    "DCT_4pt": ("DCT 4-point", "inputs/DCT_4pt.txt", "inputs/DCT_4pt_lib.txt"),
    "DCT_8pt": ("DCT 8-point", "inputs/DCT_8pt.txt", "inputs/DCT_8pt_lib.txt"),
    "DWT": ("DWT", "inputs/DWT_bechmark.txt", "inputs/DWT_lib.txt"),
}


@dataclass
class Settings:
    particles: tuple = (3, 5, 7)
    max_iter: int = 50
    stall: int = 10
    f: float = 2.0
    k: object = "random"
    seed: int = 1
    t1: float = 0.5
    ac: object = None            # None -> Amax (cost always negative)
    lc: object = None            # None -> Lmax
    include_mux_area: bool = False

    def describe(self):
        return (f"f1 = f2 = {self.f}, k = {self.k}, ω 0.9→0.1, max {self.max_iter} iterations, "
                f"stop after {self.stall} without improvement, seed {self.seed}, "
                f"t1 = {self.t1:g}, t2 = {1 - self.t1:g}")


class Session:
    def __init__(self):
        self.reset()

    def reset(self):
        self.done = set()
        self.dfg = self.lib = self.ex = None
        self.dfg_source = self.lib_source = ""
        self.sample = None
        self.settings = Settings()
        self.choice = None            # (label, position) picked for steps 4-6
        self.schedule = self.regs = self.muxes = self.mux2 = None
        self.design = None            # DesignPoint after step 6

    # -- bookkeeping ---------------------------------------------------------------
    def _complete(self, step):
        self.done = {s for s in self.done if s < step} | {step}

    def next_step(self):
        for s in range(1, 7):
            if s not in self.done:
                return s
        return None

    @property
    def dims(self):
        return self.ex.dims if self.ex else None

    # -- step 1 ----------------------------------------------------------------
    def load_dfg(self, path=None, sample=None):
        if sample:
            name, dfg_rel, _ = SAMPLES[sample]
            path = resource_path(dfg_rel)
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        name = os.path.splitext(os.path.basename(path))[0].replace("_bechmark", "").replace("_benchmark", "")
        dfg = parse_dfg(text, name, source=os.path.basename(path))
        self.dfg, self.dfg_source, self.sample = dfg, path, sample
        self._complete(1)
        self.lib = self.ex = self.choice = self.design = None
        n_in = sum((op.operand1 == 0) + (op.operand2 == 0) for op in dfg.ops.values())
        sym = {"multiplier": "×", "adder": "+", "subtractor": "−"}
        kinds = {}
        for op in dfg.ops.values():
            kinds[op.fu_type] = kinds.get(op.fu_type, 0) + 1
        mix = ", ".join(f"{n} {sym[k]}" for k, n in kinds.items())
        return f"{dfg.name}: {len(dfg.ops)} operations ({mix}), {n_in} primary inputs"

    # -- step 2 ----------------------------------------------------------------
    def load_library(self, path=None, use_sample=False):
        if use_sample:
            path = resource_path(SAMPLES[self.sample][2])
        with open(path, encoding="utf-8", errors="replace") as f:
            lib = parse_library(f.read(), source=os.path.basename(path))
        probe = Evaluator(self.dfg, lib)          # raises a readable error if a unit is missing
        self.lib, self.lib_source = lib, path
        self._complete(2)
        self.ex = self.choice = self.design = None
        space = 1
        for lo, hi in zip(probe.lower, probe.upper):
            space *= hi - lo + 1
        ranges = ", ".join(f"{d}s {lo}–{hi}" for d, lo, hi in zip(probe.dims, probe.lower, probe.upper))
        return f"{ranges} → {space} possible designs"

    def library_probe(self):
        return Evaluator(self.dfg, self.lib, t1=self.settings.t1, t2=1 - self.settings.t1,
                         area_constraint=self.settings.ac, latency_constraint=self.settings.lc,
                         include_mux_area=self.settings.include_mux_area)

    # -- step 3 ----------------------------------------------------------------
    def run_pso(self, settings):
        if not settings.particles:
            raise ValueError("Choose at least one swarm size.")
        self.settings = settings
        s = settings
        self.ex = explore(self.dfg, self.lib, particles=s.particles, max_iter=s.max_iter, stall=s.stall,
                          f=s.f, k=s.k, seed=s.seed, t1=s.t1, ac=s.ac, lc=s.lc,
                          include_mux_area=s.include_mux_area)
        self._complete(3)
        n, res = self.ex.best_run
        self.choice = (f"Best overall (N = {n})", res.best.position)
        self.design = None
        return f"best: {config_text(res.best, self.dims)} · cost {res.best.cost:.4f}"

    def choices(self):
        """Designs the user can take into steps 4-6: the best of every PSO run."""
        out = []
        n, res = self.ex.best_run
        out.append((f"Best overall — {config_text(res.best, self.dims)} (cost {res.best.cost:.4f})",
                    res.best.position))
        for n, res in self.ex.runs:
            out.append((f"Best of N = {n} — {config_text(res.best, self.dims)} (cost {res.best.cost:.4f})",
                        res.best.position))
        return out

    # -- step 4 ----------------------------------------------------------------
    def make_schedule(self, choice=None):
        if choice:
            self.choice = choice
        alloc = dict(zip(self.dims, self.choice[1]))
        self.schedule = list_schedule(self.dfg, self.lib, alloc)
        self._complete(4)
        self.design = None
        return f"{self.schedule.n_steps} control steps · latency {self.schedule.latency:.2f} ps"

    # -- step 5 ----------------------------------------------------------------
    def make_rat(self):
        self.regs = allocate_registers(self.dfg, self.schedule)
        self.muxes, self.mux2 = interconnect(self.dfg, self.schedule, self.regs)
        self._complete(5)
        self.design = None
        return f"{self.regs.n_registers} registers hold {len(self.regs.variables)} values"

    # -- step 6 ----------------------------------------------------------------
    def compute_cost(self):
        p = self.ex.probe.evaluate(self.choice[1])
        # the evaluator computed the same schedule and registers internally; check they agree
        assert p.schedule.steps == self.schedule.steps and p.regs.n_registers == self.regs.n_registers
        self.design = p
        self._complete(6)
        return f"area {p.area:.2f} µm² · latency {p.latency:.2f} ps · cost {p.cost:.4f}"

    @property
    def alloc(self):
        return dict(zip(self.dims, self.choice[1]))
