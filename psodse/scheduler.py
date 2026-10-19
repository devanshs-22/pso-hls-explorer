"""Resource-constrained LIST scheduling (+ binding of each op to an FU instance).

Every operation occupies one control step (CS). An op is *ready* in CS s when all
of its predecessor ops finished in an earlier step. Among ready ops, the ones on
the longest remaining path to the output go first (ties -> lower op number), and
at most `alloc[fu]` ops of one resource type can run in the same step.

The clock period of a step is decided by the slowest op in that step, so the
design latency is the sum of those per-step maxima (register delay is ignored).
This matches Eq. (4) of the paper: L = CM*LM + CA*LA.
"""
from dataclasses import dataclass


@dataclass
class Schedule:
    steps: list          # steps[s-1] = list of op ids executed in CS s
    op_step: dict        # op_id -> CS (1-based)
    binding: dict        # op_id -> (fu_type, instance index 0-based)
    step_latency: list   # ps, one per CS

    @property
    def n_steps(self):
        return len(self.steps)

    @property
    def latency(self):
        return sum(self.step_latency)


def critical_path_priority(dfg):
    """Number of ops on the longest path from each op to any sink (inclusive)."""
    prio = {}
    for oid in reversed(list(dfg.ops)):
        prio[oid] = 1 + max((prio[s] for s in dfg.successors[oid]), default=0)
    return prio


def list_schedule(dfg, library, alloc):
    """alloc: dict fu_type -> number of instances allowed."""
    for fu in dfg.fu_types_used:
        if alloc.get(fu, 0) < 1:
            raise ValueError(f"need at least one {fu} to schedule {dfg.name}")
    prio = critical_path_priority(dfg)
    op_step, binding, steps = {}, {}, []
    remaining = set(dfg.ops)
    s = 0
    while remaining:
        s += 1
        ready = [o for o in remaining
                 if all(op_step.get(p, s) < s for p in dfg.ops[o].predecessors)]
        ready.sort(key=lambda o: (-prio[o], o))
        used, placed = {}, []
        for o in ready:
            fu = dfg.ops[o].fu_type
            if used.get(fu, 0) < alloc[fu]:
                binding[o] = (fu, used.get(fu, 0))
                used[fu] = used.get(fu, 0) + 1
                op_step[o] = s
                placed.append(o)
        remaining.difference_update(placed)
        steps.append(sorted(placed))
    step_latency = [max(library.fus[dfg.ops[o].fu_type].latency for o in st) for st in steps]
    return Schedule(steps, op_step, binding, step_latency)
