# DCT_8pt

- Operations: 15, primary inputs: 16
- Search space: adder 1–1, multiplier 1–8 (8 designs)
- Amax = 635.4376 µm² (max resources), Lmax = 2186.0124 ps (min resources)
- Ac = 635.4376 µm², Lc = 2186.0124 ps
- PSO: f1 = f2 = 2.0, k = random, ω 0.9→0.1, max 50 iterations, stop after 10 without improvement, seed 1

| N | Best config | Area (µm²) | Latency (ps) | Registers | Cost | Iterations | Converged at | Convergence time (ms) | Exploration time (ms) | Designs visited |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | 1 adder, 2 multipliers | 182.4520 | 1324.8560 | 16 | -0.553406 | 12 | 2 | 0.984 | 1.251 | 8/8 |
| 5 | 1 adder, 2 multipliers | 182.4520 | 1324.8560 | 16 | -0.553406 | 11 | 1 | 0.822 | 1.278 | 8/8 |
| 7 | 1 adder, 2 multipliers | 182.4520 | 1324.8560 | 16 | -0.553406 | 12 | 2 | 1.309 | 1.575 | 8/8 |

Exhaustive check (done after the runs, for validation only): the minimum-cost design is **1 adder, 2 multipliers** with cost -0.553406 — every PSO run found it.

Pareto-optimal designs (no other design is both smaller and faster):

| Config | Area (µm²) | Latency (ps) | Cost |
|---|---|---|---|
| 1 adder, 8 multipliers | 635.4376 | 728.6708 | -0.333333 |
| 1 adder, 4 multipliers | 333.4472 | 927.3992 | -0.525503 |
| 1 adder, 3 multipliers | 257.9496 | 1126.1276 | -0.539454 |
| 1 adder, 2 multipliers | 182.4520 | 1324.8560 | -0.553406 |
| 1 adder, 1 multiplier | 106.9544 | 2186.0124 | -0.415842 |
