"""Turn a recorded PSO run into replay frames with plain-English narration.

PSO itself runs in milliseconds; the desktop app replays the recorded history slowly so a
person can watch it. Each iteration becomes two frames:

    move   - particles after the velocity/position update (Eq. 6, 7) and AETP
    mutate - particles after mutation and AETP; the global best is updated

plus an initial frame (the swarm placement) and a final "done" frame. The narration only
uses information the algorithm had at that moment (it never "knows" when it will stop).
"""
from dataclasses import dataclass, field

from .report import config_text


@dataclass
class Frame:
    iteration: int
    phase: str                    # init | move | mutate | done
    w: float
    positions: list               # one tuple per particle
    costs: list
    gbest: tuple
    gbest_cost: float
    improved: bool                # did this frame find a new global best?
    stall: int                    # iterations in a row without improvement so far
    local_best: list              # [(position, cost)] per particle
    visited: set = field(default_factory=set)
    prev_gbest: tuple = None


def build_frames(res):
    H = res.history
    lb = [(tuple(p), c) for p, c in zip(H[0]["particles"], H[0]["costs"])]
    visited = {tuple(p) for p in H[0]["particles"]}
    g, gc, stall = tuple(H[0]["gbest"]), H[0]["gbest_cost"], 0
    frames = [Frame(0, "init", None, [tuple(p) for p in H[0]["particles"]], list(H[0]["costs"]),
                    g, gc, True, 0, list(lb), set(visited))]

    def take(pos, costs):
        for i, (p, c) in enumerate(zip(pos, costs)):
            visited.add(tuple(p))
            if c < lb[i][1]:
                lb[i] = (tuple(p), c)

    for it in H[1:]:
        take(it["particles"], it["costs"])
        g1, gc1 = g, gc
        for p, c in zip(it["particles"], it["costs"]):
            if c < gc1 - 1e-12:
                g1, gc1 = tuple(p), c
        frames.append(Frame(it["iteration"], "move", it["w"], [tuple(p) for p in it["particles"]],
                            list(it["costs"]), g1, gc1, gc1 < gc - 1e-12, stall, list(lb),
                            set(visited), prev_gbest=g))
        take(it["mutated"], it["mutated_costs"])
        improved_iter = it["gbest_cost"] < gc - 1e-12
        stall = 0 if improved_iter else stall + 1
        f = Frame(it["iteration"], "mutate", it["w"], [tuple(p) for p in it["mutated"]],
                  list(it["mutated_costs"]), tuple(it["gbest"]), it["gbest_cost"],
                  it["gbest_cost"] < gc1 - 1e-12, stall, list(lb), set(visited))
        f.improved_iter = improved_iter
        frames.append(f)
        g, gc = tuple(it["gbest"]), it["gbest_cost"]
    last = frames[-1]
    done = Frame(last.iteration, "done", last.w, last.positions, last.costs, last.gbest,
                 last.gbest_cost, False, last.stall, last.local_best, last.visited)
    frames.append(done)
    return frames


PHASE_TITLE = {"init": "Initial swarm", "move": "Velocity update", "mutate": "Mutation",
               "done": "Finished"}


def narrate(f, dims, res, cfg, space):
    """Rich-text (HTML subset) explanation of one frame."""
    lab = lambda p: f"<b>{config_text(p, dims)}</b>"
    if f.phase == "init":
        n = len(f.positions)
        txt = f"The swarm is placed: <b>P0</b> at the maximum resources ({lab(f.positions[0])})"
        if n > 1:
            txt += f", <b>P1</b> at the minimum ({lab(f.positions[1])})"
        if n > 2:
            txt += f", <b>P2</b> at the average ({lab(f.positions[2])})"
        if n > 3:
            txt += f", and P3–P{n - 1} from the paper's random formula"
        return txt + (f". Every design is scheduled and its cost computed. The cheapest, {lab(f.gbest)}, "
                      "becomes the swarm's best.")
    if f.phase == "move":
        txt = (f"Each particle gets a new velocity: part of its old motion (inertia ω = {f.w:.3f}), a pull "
               f"towards <b>its own best</b> and a pull towards the <b>swarm's best</b> {lab(f.prev_gbest)}. "
               "Anything outside the library limits is pushed back inside (AETP).")
        if f.improved:
            txt += (f" <span style='color:#1a8f55'><b>New best found: {config_text(f.gbest, dims)}, "
                    f"cost {f.gbest_cost:.4f}.</b></span>")
        return txt
    if f.phase == "mutate":
        what = (f"swap their {dims[0]} and {dims[1]} counts" if len(dims) > 1 else "rotate their values")
        txt = f"Mutation keeps the swarm exploring: even particles {what}, odd particles jump by ±1–3. "
        if getattr(f, "improved_iter", False):
            txt += (f"<span style='color:#1a8f55'><b>This iteration improved the best design to "
                    f"{config_text(f.gbest, dims)} (cost {f.gbest_cost:.4f}).</b></span>")
        else:
            txt += f"No improvement this iteration: <b>{f.stall} of {cfg.stall_limit}</b> before the search stops."
        return txt
    return (f"Search finished: {res.stop_reason}. Best design {lab(f.gbest)}, cost <b>{f.gbest_cost:.4f}</b>. "
            f"It was first found in iteration {res.convergence_iter} (convergence time "
            f"<b>{res.convergence_time_ms:.3f} ms</b>). The whole search took <b>{res.exploration_time_ms:.3f} ms</b> "
            f"and looked at <b>{len(res.explored)} of {space}</b> designs.")
