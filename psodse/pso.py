"""PSO based architecture exploration (Section 4-B of Anshul & Sengupta, ESWA 2023).

Particle  = a resource configuration, e.g. (2 adders, 3 multipliers).
Fitness   = design cost of that configuration (Evaluator.evaluate, Eq. 5).

    swarm init   P0 = max resources, P1 = min resources, P2 = average,
                 P3.. = ceil((min+max)/2) +/- rand(min, max)  (alternating sign)
    velocity     V+ = w V + f1 k1 (Plb - P) + f2 k2 (Pgb - P)            Eq. (7)
    position     P+ = P + V+                                           Eq. (6)
    then         velocity clamping, AETP (pull back inside the library limits),
                 mutation (even particle: left rotation, odd: +/- rand[1,3]),
                 AETP again, re-evaluate, update local/global best.
    inertia w    decreases linearly 0.9 -> 0.1 over the iterations
    stop         global best unchanged for `stall_limit` (10) iterations, or 50 iterations.

Convergence time  = time until the final global best was first found.
Exploration time  = total time until the algorithm terminated.
"""
import math
import random
import time
from dataclasses import dataclass, field


@dataclass
class PSOConfig:
    n_particles: int = 3
    max_iter: int = 50
    stall_limit: int = 10
    w_start: float = 0.9
    w_end: float = 0.1
    f1: float = 2.0
    f2: float = 2.0
    k: object = "random"          # 'random' -> k1, k2 ~ U(0,1) each update; or a fixed number
    seed: int = None


@dataclass
class PSOResult:
    best: object                  # DesignPoint of the global best
    history: list                 # one dict per iteration (iteration 0 = initial swarm)
    convergence_iter: int
    convergence_time_ms: float
    exploration_time_ms: float
    iterations_run: int
    stop_reason: str
    explored: dict = field(default_factory=dict)   # position -> DesignPoint visited by the swarm


def _round(x):
    return int(math.floor(x + 0.5))


class PSO:
    def __init__(self, evaluator, config):
        self.ev, self.cfg = evaluator, config
        self.rng = random.Random(config.seed)
        self.lo, self.hi = evaluator.lower, evaluator.upper
        self.d = len(self.lo)

    # ---- helpers -------------------------------------------------------------
    def aetp(self, pos):
        """Adaptive end terminal perturbation: step back inside [LW, UP] by random J."""
        out = []
        for x, lo, hi in zip(pos, self.lo, self.hi):
            if lo == hi:
                x = lo
            while x < lo:
                x += self.rng.randint(1, hi - lo)
            while x > hi:
                x -= self.rng.randint(1, hi - lo)
            out.append(x)
        return out

    def _k(self):
        return self.rng.random() if self.cfg.k == "random" else float(self.cfg.k)

    def initial_swarm(self):
        n = self.cfg.n_particles
        mid = [math.ceil((lo + hi) / 2) for lo, hi in zip(self.lo, self.hi)]
        swarm = [list(self.hi), list(self.lo), list(mid)]
        for i in range(3, n):
            p = []
            for dim, (lo, hi) in enumerate(zip(self.lo, self.hi)):
                a = self.rng.randint(lo, hi)
                sign = 1 if (dim % 2 == 0) == (i % 2 == 0) else -1
                p.append(mid[dim] + sign * a)
            swarm.append(self.aetp(p))
        return swarm[:n]

    def mutate(self, i, pos):
        pos = list(pos)
        if i % 2 == 0:                                   # left rotation of the dimensions
            for t in range(self.d - 1):
                pos[t], pos[t + 1] = pos[t + 1], pos[t]
        else:                                            # random +/- step of 1..3
            for t in range(self.d):
                pos[t] += self.rng.choice((-1, 1)) * self.rng.randint(1, 3)
        return self.aetp(pos)

    # ---- main loop -----------------------------------------------------------
    def run(self):
        cfg, ev = self.cfg, self.ev
        t0 = time.perf_counter()
        explored = {}

        def evaluate(pos):
            p = ev.evaluate(pos)
            explored[p.position] = p
            return p

        pos = self.initial_swarm()
        vel = [[0.0] * self.d for _ in pos]
        pts = [evaluate(p) for p in pos]
        lbest = list(pts)
        gbest = min(pts, key=lambda p: p.cost)
        conv_iter, conv_time = 0, time.perf_counter() - t0
        history = [dict(iteration=0, w=None, particles=[p.position for p in pts],
                        costs=[p.cost for p in pts], mutated=None, mutated_costs=None,
                        gbest=gbest.position, gbest_cost=gbest.cost,
                        elapsed_ms=conv_time * 1e3)]

        stall, r, reason = 0, 0, f"reached max iterations ({cfg.max_iter})"
        vmax = [hi - lo for lo, hi in zip(self.lo, self.hi)]
        while r < cfg.max_iter:
            r += 1
            w = cfg.w_start - (cfg.w_start - cfg.w_end) * (r - 1) / max(cfg.max_iter - 1, 1)
            improved = False

            def consider(i, p):
                nonlocal gbest, improved
                if p.cost < lbest[i].cost:
                    lbest[i] = p
                if p.cost < gbest.cost - 1e-12:
                    gbest, improved = p, True

            # velocity + position update (Eq. 6, 7), clamping and AETP
            for i in range(len(pos)):
                for t in range(self.d):
                    v = (w * vel[i][t]
                         + cfg.f1 * self._k() * (lbest[i].position[t] - pos[i][t])
                         + cfg.f2 * self._k() * (gbest.position[t] - pos[i][t]))
                    vel[i][t] = max(-vmax[t], min(vmax[t], v))
                    pos[i][t] = _round(pos[i][t] + vel[i][t])
                pos[i] = self.aetp(pos[i])
            pts = [evaluate(p) for p in pos]
            for i, p in enumerate(pts):
                consider(i, p)

            # mutation for diversification, AETP, re-evaluate
            pos = [self.mutate(i, p) for i, p in enumerate(pos)]
            mpts = [evaluate(p) for p in pos]
            for i, p in enumerate(mpts):
                consider(i, p)

            now = time.perf_counter() - t0
            if improved:
                stall, conv_iter, conv_time = 0, r, now
            else:
                stall += 1
            history.append(dict(iteration=r, w=w, particles=[p.position for p in pts],
                                costs=[p.cost for p in pts],
                                mutated=[p.position for p in mpts],
                                mutated_costs=[p.cost for p in mpts],
                                gbest=gbest.position, gbest_cost=gbest.cost,
                                elapsed_ms=now * 1e3))
            if stall >= cfg.stall_limit:
                reason = f"global best unchanged for {cfg.stall_limit} iterations"
                break

        total = time.perf_counter() - t0
        return PSOResult(gbest, history, conv_iter, conv_time * 1e3, total * 1e3, r, reason, explored)
