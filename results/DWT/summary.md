# DWT

- Operations: 17, primary inputs: 10
- Search space: adder 1–4, multiplier 1–5 (20 designs)
- Amax = 460.8496 µm² (max resources), Lmax = 2252.2552 ps (min resources)
- Ac = 460.8496 µm², Lc = 2252.2552 ps
- PSO: f1 = f2 = 2.0, k = random, ω 0.9→0.1, max 50 iterations, stop after 10 without improvement, seed 1

| N | Best config | Area (µm²) | Latency (ps) | Registers | Cost | Iterations | Converged at | Convergence time (ms) | Exploration time (ms) | Designs visited |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | 1 adder, 2 multipliers | 177.7336 | 1854.7984 | 10 | -0.395403 | 13 | 3 | 1.372 | 3.056 | 18/20 |
| 5 | 1 adder, 2 multipliers | 177.7336 | 1854.7984 | 10 | -0.395403 | 11 | 1 | 1.360 | 3.145 | 20/20 |
| 7 | 1 adder, 2 multipliers | 177.7336 | 1854.7984 | 10 | -0.395403 | 11 | 1 | 1.941 | 3.527 | 20/20 |

Exhaustive check (done after the runs, for validation only): the minimum-cost design is **1 adder, 2 multipliers** with cost -0.395403 — every PSO run found it.

Pareto-optimal designs (no other design is both smaller and faster):

| Config | Area (µm²) | Latency (ps) | Cost |
|---|---|---|---|
| 1 adder, 5 multipliers | 404.2264 | 1457.3416 | -0.237904 |
| 1 adder, 3 multipliers | 253.2312 | 1656.0700 | -0.357609 |
| 1 adder, 2 multipliers | 177.7336 | 1854.7984 | -0.395403 |
| 1 adder, 1 multiplier | 102.2360 | 2252.2552 | -0.389079 |
