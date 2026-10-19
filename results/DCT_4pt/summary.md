# DCT_4pt

- Operations: 7, primary inputs: 8
- Search space: adder 1–1, multiplier 1–4 (4 designs)
- Amax = 327.1560 µm² (max resources), Lmax = 1126.1276 ps (min resources)
- Ac = 327.1560 µm², Lc = 1126.1276 ps
- PSO: f1 = f2 = 2.0, k = random, ω 0.9→0.1, max 50 iterations, stop after 10 without improvement, seed 1

| N | Best config | Area (µm²) | Latency (ps) | Registers | Cost | Iterations | Converged at | Convergence time (ms) | Exploration time (ms) | Designs visited |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | 1 adder, 2 multipliers | 176.1608 | 662.4280 | 8 | -0.436652 | 11 | 1 | 0.289 | 0.415 | 4/4 |
| 5 | 1 adder, 2 multipliers | 176.1608 | 662.4280 | 8 | -0.436652 | 10 | 0 | 0.252 | 0.586 | 4/4 |
| 7 | 1 adder, 2 multipliers | 176.1608 | 662.4280 | 8 | -0.436652 | 10 | 0 | 0.271 | 0.542 | 4/4 |

Exhaustive check (done after the runs, for validation only): the minimum-cost design is **1 adder, 2 multipliers** with cost -0.436652 — every PSO run found it.

Pareto-optimal designs (no other design is both smaller and faster):

| Config | Area (µm²) | Latency (ps) | Cost |
|---|---|---|---|
| 1 adder, 4 multipliers | 327.1560 | 463.6996 | -0.294118 |
| 1 adder, 2 multipliers | 176.1608 | 662.4280 | -0.436652 |
| 1 adder, 1 multiplier | 100.6632 | 1126.1276 | -0.346154 |
