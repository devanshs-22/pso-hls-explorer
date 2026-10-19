"""One complete exploration: PSO for every swarm size, plus the post-run analysis.

Used by both main.py and the desktop app so they always produce the same numbers.
"""
from dataclasses import dataclass, field

from .cost import Evaluator
from .plots import pareto_front
from .pso import PSO, PSOConfig

MAX_EXHAUSTIVE = 400          # check every design afterwards only if the space is this small


@dataclass
class Exploration:
    dfg: object
    lib: object
    probe: Evaluator          # evaluator used for the post-run analysis
    runs: list                # [(n_particles, PSOResult)]
    all_points: list          # every design (exhaustive) or every visited design
    exhaustive: bool
    configs: dict = field(default_factory=dict)   # n -> PSOConfig

    @property
    def dims(self):
        return self.probe.dims

    @property
    def space(self):
        s = 1
        for lo, hi in zip(self.probe.lower, self.probe.upper):
            s *= hi - lo + 1
        return s

    @property
    def n_inputs(self):
        return sum((op.operand1 == 0) + (op.operand2 == 0) for op in self.dfg.ops.values())

    @property
    def visited(self):
        return set().union(*(r.explored for _, r in self.runs))

    @property
    def true_best(self):
        return min(self.all_points, key=lambda p: p.cost)

    @property
    def best_run(self):
        """(n, PSOResult) with the lowest cost; ties go to the smaller swarm."""
        return min(self.runs, key=lambda nr: (nr[1].best.cost, nr[0]))

    @property
    def all_found_optimum(self):
        return all(abs(r.best.cost - self.true_best.cost) < 1e-12 for _, r in self.runs)

    @property
    def pareto(self):
        return pareto_front(self.all_points)


def explore(dfg, lib, particles=(3, 5, 7), max_iter=50, stall=10, f=2.0, k="random", seed=1,
            t1=0.5, ac=None, lc=None, include_mux_area=False):
    ev_kwargs = dict(t1=t1, t2=1 - t1, area_constraint=ac, latency_constraint=lc,
                     include_mux_area=include_mux_area)
    probe = Evaluator(dfg, lib, **ev_kwargs)
    runs, configs = [], {}
    for n in particles:
        ev = Evaluator(dfg, lib, **ev_kwargs)            # fresh cache -> fair timing per N
        cfg = PSOConfig(n_particles=n, max_iter=max_iter, stall_limit=stall, f1=f, f2=f, k=k, seed=seed)
        configs[n] = cfg
        runs.append((n, PSO(ev, cfg).run()))
    space = 1
    for lo, hi in zip(probe.lower, probe.upper):
        space *= hi - lo + 1
    exhaustive = space <= MAX_EXHAUSTIVE
    if exhaustive:
        positions = probe.all_positions()
    else:
        positions = sorted(set().union(*(r.explored for _, r in runs)))
    points = [probe.evaluate(p) for p in positions]
    return Exploration(dfg, lib, probe, runs, points, exhaustive, configs)
