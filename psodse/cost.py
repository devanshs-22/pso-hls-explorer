"""Design metrics and the design cost (fitness) of Eq. (5) of the paper.

    Area    A = sum_i area(FU_i) * count(FU_i) + #registers * area(register)      Eq. (3)
    Latency L = sum over control steps of the slowest op in that step             Eq. (4)
    Cost      = t1 * (A - Ac) / Amax + t2 * (L - Lc) / Lmax                      Eq. (5)

Amax = area of the design built with the MAXIMUM resources of the library,
Lmax = latency of the design built with the MINIMUM resources (1 of each type).

Ac, Lc (IP-vendor area / latency constraints) default to Amax and Lmax, i.e. the
worst-case design. Then every term is <= 0 and the cost lies in [-1, 0): negative,
as in Table 3 of the paper; more negative is better. This is the Ac = Lc = 0 cost
minus exactly 1, so it ranks designs identically.

With Ac = Lc = 0 the numbers reproduce the HarDMark reference tool exactly: DCT-4pt
with 1 adder + 2 multipliers -> A = 176.1608 um^2, L = 662.428 ps, cost = 0.56334822818.
"""
from dataclasses import dataclass

from .registers import allocate_registers, interconnect
from .scheduler import list_schedule


@dataclass
class DesignPoint:
    position: tuple        # resource counts, in the order of Evaluator.dims
    alloc: dict
    schedule: object
    regs: object
    muxes: list
    mux2_count: int
    fu_area: float
    reg_area: float
    mux_area: float
    area: float
    latency: float
    cost: float = 0.0

    def label(self, dims):
        return ", ".join(f"{n}({d[0].upper()})" for n, d in zip(self.position, dims))


class Evaluator:
    def __init__(self, dfg, library, t1=0.5, t2=0.5, area_constraint=None,
                 latency_constraint=None, include_mux_area=False):
        """area_constraint / latency_constraint: None -> Amax / Lmax (cost always negative)."""
        self.dfg, self.lib = dfg, library
        self.t1, self.t2 = t1, t2
        self.include_mux_area = include_mux_area
        self.dims = dfg.fu_types_used                    # e.g. ['adder', 'multiplier']
        for fu in self.dims:
            if fu not in library.fus or library.fus[fu].max_count < 1:
                raise ValueError(f"library has no {fu} available but {dfg.name} needs one")
        self.lower = [1] * len(self.dims)
        self.upper = [library.fus[fu].max_count for fu in self.dims]
        self.cache = {}
        self.amax = self._build(tuple(self.upper)).area
        self.lmax = self._build(tuple(self.lower)).latency
        self.ac = self.amax if area_constraint is None else float(area_constraint)
        self.lc = self.lmax if latency_constraint is None else float(latency_constraint)

    def _build(self, position):
        alloc = dict(zip(self.dims, position))
        sched = list_schedule(self.dfg, self.lib, alloc)
        regs = allocate_registers(self.dfg, sched)
        muxes, mux2 = interconnect(self.dfg, sched, regs)
        fu_area = sum(self.lib.fus[fu].area * n for fu, n in alloc.items())
        reg_area = regs.n_registers * self.lib.register_area
        mux_area = mux2 * self.lib.mux_area
        area = fu_area + reg_area + (mux_area if self.include_mux_area else 0.0)
        return DesignPoint(tuple(position), alloc, sched, regs, muxes, mux2,
                           fu_area, reg_area, mux_area, area, sched.latency)

    def evaluate(self, position):
        position = tuple(int(x) for x in position)
        if position not in self.cache:
            p = self._build(position)
            p.cost = (self.t1 * (p.area - self.ac) / self.amax
                      + self.t2 * (p.latency - self.lc) / self.lmax)
            self.cache[position] = p
        return self.cache[position]

    def all_positions(self):
        """Whole design space (used only for the optional validation / trade-off plot)."""
        grid = [()]
        for lo, hi in zip(self.lower, self.upper):
            grid = [g + (v,) for g in grid for v in range(lo, hi + 1)]
        return grid
