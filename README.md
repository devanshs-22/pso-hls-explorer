# PSO HLS Explorer

**Made by Devansh Singhal, Deepak Kumar, Dhristi, Kshaunish and Anshul Gupta.**

PSO HLS Explorer is a desktop tool for high-level synthesis (HLS). You give it an
algorithm written as a **data-flow graph** (a list of additions and multiplications) and a
**module library** of hardware units. It uses **particle swarm optimisation (PSO)** to find
how many adders and multipliers the chip should have, so that **chip area** and
**latency (speed)** are best balanced. It then shows the scheduled design, the
**register allocation table (RAT)**, the multiplexers, and the final area, latency and
design cost, all step by step.

The method is the PSO-based architecture exploration of A. Anshul & A. Sengupta, *"PSO
based exploration of multi-phase encryption based secured image processing filter
hardware IP core datapath during high level synthesis"*, Expert Systems with Applications
223 (2023), Section 4-B. The DFG goes straight into PSO, with no structural
transformation. Area and delay come from the 15 nm open cell library.

---

## 1. Running the app

| What | How |
|---|---|
| **Use the built Mac app** | Double-click `dist/PSO HLS Explorer.app` (you can drag it into Applications). On a different Mac, the first time, right-click → **Open**, because the app is not signed with an Apple developer certificate. |
| **Run from source (Mac)** | `cd ~/Desktop/PSO_HLS_Project` then `.venv/bin/python desktop_app.py` |
| **Rebuild the Mac app** | `./build_mac.sh` creates `dist/PSO HLS Explorer.app` |
| **Build for Windows** | On a Windows PC with Python from python.org, double-click `build_windows.bat`. It creates `dist\PSO HLS Explorer\PSO HLS Explorer.exe`. |
| **Build for Windows without a Windows PC** | Push the project to GitHub, open the **Actions** tab, run **Build desktop app**, and download the Windows and macOS apps from the run's *Artifacts*. |

First-time setup from source: `python3 -m venv .venv`, then
`.venv/bin/pip install -r requirements.txt -r requirements-app.txt`.

---

## 2. The main window, button by button

The window has a **header**, a blue **"Next →" banner**, three panels (**input**,
**status**, **output**), an **activity log** and a **footer**.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [Read me!]  PSO HLS Explorer                                        [Reset] │
│ Next → Step 3: choose the swarm sizes and click Run PSO exploration.         │
├──────────────────────┬────────────────────┬──────────────────────────────────┤
│ INPUT PANEL          │ STATUS PANEL       │ OUTPUT PANEL                     │
│ 1 Load DFG       ✓   │ DONE  1 App graph  │ ↗ View data-flow graph           │
│ 2 Load library   ✓   │ DONE  2 Library    │ ↗ View module library            │
│ 3 Run PSO   ◀ active │ NEXT  3 PSO        │ 🔒 Watch PSO exploration …       │
│ 4 Schedule  (locked) │ WAIT  4 Schedule   │ 🔒 …                             │
│ 5 RAT       (locked) │ WAIT  5 RAT        │                                  │
│ 6 Cost      (locked) │ WAIT  6 Cost       │                                  │
├──────────────────────┴────────────────────┴──────────────────────────────────┤
│ activity log: what happened, step by step                                    │
│ Made by …                                                                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Header

| Button | What it does |
|---|---|
| **Read me!** (green) | Opens the in-app guide: what the tool does, every button, the words used, and the input file formats. |
| **Reset** | Clears everything and goes back to step 1. Asks for confirmation if you have done any steps. |

The **Next →** banner always says what to do next. It turns green when all six steps are done.

### Input panel (left): the six steps

Do the steps **in order**. A step stays **greyed out with "Locked — finish step N first"**
until the step before it is done. The active step has a blue border, and a finished step
gets a green ✓ and a one-line result. **Doing an earlier step again clears every later
step** (for example, loading a new DFG means you have to load the library and run PSO again).

| Step | Controls | What happens |
|---|---|---|
| **1 · Load application graph (DFG)** | **Load DFG file…** opens a file chooser. **DCT 4-point / DCT 8-point / DWT** load a built-in sample instead. | The file is read into operations (*operation, first operand, second operand, operation number*). The result line shows e.g. "DWT: 17 operations (8 ×, 9 +), 10 primary inputs". |
| **2 · Load module library** | **Load library file…** opens a file chooser. **Use sample library (…_lib.txt)** appears when a sample was loaded in step 1 and loads its matching library. | Reads the area, delay and number available of each unit and checks that every operation in the DFG has a unit. The result line shows the design space, e.g. "adders 1–4, multipliers 1–5 → 20 possible designs". |
| **3 · Explore designs with PSO** | **3 / 5 / 7 particles**: which swarm sizes to run; each is a separate run, and all three are on by default. **Max iterations** (50): hard limit. **Stop if no improvement for** (10 iterations): stops a run early once the best design stops changing. **Advanced settings** (click to open): *f1 = f2* (social/cognitive factor, 2), *k1 = k2* (random 0–1, or fixed 1 or 0.5), *random seed* (same seed = same run), *area weight t1* (latency weight t2 = 1 − t1), *area constraint Ac* and *latency constraint Lc* (empty = automatic Amax / Lmax, which makes every cost negative), and *add multiplexer area to the design area*. **Run PSO exploration** starts the search. | PSO runs for every chosen swarm size (it takes milliseconds). The **animated replay** window opens automatically. The result line shows the best design and its cost. |
| **4 · Generate scheduled design** | **Design:** choose which result to continue with: *Best overall* or *Best of N = 3 / 5 / 7*. **Generate scheduled design** runs list scheduling. | Every operation is placed in a clock cycle (control step) on a unit. Result: number of control steps and the latency. |
| **5 · Generate register allocation (RAT)** | **Generate register allocation table** | Works out how long every value must be stored, and puts values that are never alive at the same time in the same register (left-edge register colouring). Result: e.g. "10 registers hold 27 values". |
| **6 · Compute area, latency & design cost** | **Compute design cost** | Area = units + registers; latency = sum of the cycle lengths; design cost = Eq. 5 of the paper. |

### Status panel (middle)

One tile per step, with its result once the step is done.

| Colour | Meaning |
|---|---|
| Grey **WAITING** | Not reached yet |
| Blue **DO THIS NEXT** | The step you should do now |
| Amber **RUNNING…** | Working |
| Green **DONE ✓** | Finished; the tile shows the result |
| Red **ERROR** | Something is wrong (for example a bad file); the tile and a pop-up say what |

### Output panel (right): every button opens its own window

A button shows a **lock** until the step that produces it is done. The newest outputs get
a **blue outline**. You can open several windows side by side. Charts have a
**Save image…** button (PNG, PDF or SVG).

| Button | Unlocked by | What the window shows and how to read it |
|---|---|---|
| **View data-flow graph (DFG)** | Step 1 | Left: the application as a graph. Circles are operations (blue + adder, orange × multiplier), arrows show which result feeds which operation, and the small stubs on top are primary inputs. Rows are the earliest cycle each operation could run in. Right: the file as a table: *Op #, operation, operand 1, operand 2* and its meaning (e.g. "op5 = op1 + op2"). |
| **View module library** | Step 2 | Table of every unit: area (µm²), delay (ps), power, how many are available, and whether this application uses it. Below: the size of the design space, Amax and Lmax. |
| **Watch PSO exploration (animated)** | Step 3 | A slowed-down **replay** of the search. Each square is one design (rows = adders, columns = multipliers). A square shows its cost colour once the swarm has visited it (darker = higher cost, **?** = not visited yet). Orange dots **P0, P1…** are particles; the black frame with **★** is the best design so far. Solid trails = velocity moves, dashed trails = mutation jumps. **Buttons:** **N = 3 / 5 / 7 particles** switches between runs; **⏮ ◀ ▶ ▶\| ⏭** go to the start, step back, play/pause, step forward and go to the end; the **slider** jumps anywhere; **slow / normal / fast** sets the speed. **Right side:** the current phase (initial swarm / velocity update / mutation / finished), the iteration, the inertia ω, the **stop-rule meter** (dots fill up for each iteration without improvement), a plain-English explanation, the best design so far, and a table of what each particle is trying and its own best. **Bottom:** the best cost so far, drawn up to the current iteration on an axis that runs to the hard limit of 50. The replay never shows when the run will end, because PSO doesn't know that either. |
| **View convergence graph** | Step 3 | Best design cost after every iteration, one panel per swarm size. The dot marks where the final best design was first found (convergence). The shaded part is the run of iterations without improvement that made the search stop. |
| **Compare swarm sizes (N = 3 · 5 · 7)** | Step 3 | Table: best design, cost, iteration it was found at, iterations run, **convergence time**, **exploration time** and designs visited, for each swarm size, plus a bar chart of the two times. A green note confirms whether every run found the true best design (checked afterwards against every design). |
| **View area–latency trade-off** | Step 3 | Every design's area against its latency. The dashed line is the **Pareto front** (designs that cannot get smaller without getting slower) and ★ is the chosen design. The table on the right lists the Pareto designs. |
| **View scheduled design** | Step 4 | The scheduled data-flow graph (rows = clock cycles, columns = units; each cycle's length is on the right) and the schedule as a table (cycle × unit, cycle length, total latency). "Unit reuse" says how many cycles each unit is busy, e.g. "A1 busy 9/10 cycles". |
| **View register allocation table (RAT)** | Step 5 | The RAT in the format of **Table 1 of the paper**: rows = registers named by colour (Red (R), Green (G), …), columns = C0 (start), C1 (after cycle 1), …; each cell is the value that register holds, "–" = empty. A "How to read it" box explains it, **hovering** a value highlights every cell where it is stored, and an example and summary line explain the register reuse. **Save RAT as image…** saves it as a picture. |
| **View datapath interconnect** | Step 5 | The multiplexers (k:1 mux, where an input receives data from several places) and demultiplexers (1:k, where an output feeds several places) that reusing units and registers requires, plus the equivalent number of 2:1 muxes and their area. |
| **View area, latency & design cost** | Step 6 | Tiles for design cost, adders, multipliers, registers, area and latency; an area breakdown table; a latency table (each cycle's slowest operation); and the cost formula filled in with the numbers. |
| **Export all results…** | Step 6 | Choose a folder. The tool saves every chart (DFG, schedules, RATs, convergence, trade-off, times), the per-iteration logs, a design report for each swarm size, `summary.md`, and `chosen_design.txt` for the design taken through steps 4–6. **Open folder** shows it. |

### Activity log and footer

The **activity log** at the bottom writes one line per step (with the time), for example
*"Step 3 done — PSO best: 1 adder, 2 multipliers · cost −0.3954. N=3: 13 iterations, best at iteration 3 (2.98 ms) …"*.
The **footer** shows the team.

---

## 3. Input file formats

**Application (DFG):** groups of four comma-separated values,
`operation, operand 1, operand 2, operation number`. Operations are `+`, `-` and `*`.
Operand `0` is a primary input, and operand `k` is the result of operation `k`.

```
*,0,0,1,*,0,0,2,*,0,0,3,*,0,0,4,+,1,2,5,+,5,3,6,+,6,4,7        (DCT 4-point)
```

**Module library:** one line per unit. Values ending in `um` are area, `ps` are delay
and `pj` are power. The last number is how many are available.

```
adder(16),0.739pj,18.8744um,66.2428ps,18.6um,70.0ps,1
multiplier(16),9.8pj,75.4976um,264.9712ps,75.2um,270.9712ps,4
register,0.7864um,25.9108ps
```

---

## 4. The concepts behind it

**Scheduling (list scheduling).** An operation can run once its inputs are ready. At most
"number of adders" additions and "number of multipliers" multiplications run in the same
cycle. When more operations are ready than there are units, the ones on the longest path
to the output go first.

**Latency.** A cycle lasts as long as its slowest operation, and the latency is the sum of
all cycles (register delay is ignored). Example: 2 multiplier cycles + 2 adder cycles =
2 × 264.97 + 2 × 66.24 = 662.43 ps.

**Registers and the RAT.** Every value is stored from the cycle that produces it until
the last cycle that reads it. Values whose lifetimes don't overlap share a register
(left-edge algorithm = register colouring), so the fewest registers are used.

**Area.** (area of each unit × how many) + number of registers × register area.
Multiplexer area is reported separately and only added if you tick the option.

**Design cost (Eq. 5).** `t1·(A − Ac)/Amax + t2·(L − Lc)/Lmax` with t1 = t2 = 0.5.
Amax is the area with the most hardware and Lmax the latency with the least hardware.
By default Ac = Amax and Lc = Lmax, so every cost is between −1 and 0 and **more
negative is better**.

**PSO.** Each particle is one design, e.g. (1 adder, 2 multipliers).
- **Initial swarm:** P0 = maximum resources, P1 = minimum, P2 = average, and P3… come
  from the paper's formula `ceil((min+max)/2) ± rand(min, max)`.
- **Each iteration:** velocity `V = ωV + f1·k1·(own best − P) + f2·k2·(swarm best − P)`,
  then position `P = P + V`. Velocity clamping and AETP keep particles inside the
  library limits. Then **mutation**: even particles swap their adder and multiplier
  counts, odd particles jump ±1–3. Local and global bests are updated after both moves.
- **Inertia ω** falls linearly from 0.9 to 0.1.
- **Stop:** after 50 iterations, or after 10 iterations in a row without improvement.

**Convergence time** is the time until the final best design was first found.
**Exploration time** is the time until the search stopped.

---

## 5. Other ways to run it

**Command line:** writes every chart and report to `results/`.

```bash
.venv/bin/python main.py                                   # all samples, N = 3, 5, 7
.venv/bin/python main.py --dfg inputs/DCT_4pt.txt --lib inputs/DCT_4pt_lib.txt
.venv/bin/python main.py --stall 15 --seed 7 --k 0.5 --ac 0 --lc 0
.venv/bin/python -m unittest -v                            # tests
```

**Web version:** `.venv/bin/python app.py` opens the same exploration in a browser at
`http://localhost:8000`.

---

## 6. Checked against the reference tool (HarDMark tutorial)

For DCT-4pt with 1 adder and 2 multipliers, the tutorial shows the schedule
`CS1: ×1 ×2 | CS2: ×3 ×4 +5 | CS3: +6 | CS4: +7`, 8 registers, area 176.1608 µm²,
latency 662.428 ps and cost 0.5633482281883153 (that tool uses Ac = Lc = 0). With
`--ac 0 --lc 0` this code reproduces all of these exactly (`tests/test_reference.py`).
With the default constraints the same design costs 0.5633… − 1 = −0.4367, and the
ranking of designs is unchanged.

## 7. Assumptions

1. Amax = area at maximum resources, Lmax = latency at minimum resources; Ac / Lc
   default to Amax / Lmax (every cost negative). The paper does not publish its own
   Ac / Lc; enter your values under Advanced settings or with `--ac` / `--lc`.
2. Multiplexer area is not added to the design area by default (the reference tool's
   area excludes it).
3. k1 and k2 are random in [0, 1] on each update (the paper uses 1 in the text and 0.5 in
   Fig. 7; both can be selected).
4. Every operand `0` is a separate primary input that needs its own register.

## 8. Project layout

| Path | Contents |
|---|---|
| `desktop_app.py`, `gui/` | Desktop app: main window, step cards, status tiles, output windows, animated replay |
| `psodse/` | Engine: file reading, list scheduling, register allocation, cost, PSO, replay, charts, reports, export |
| `main.py` | Command-line tool |
| `app.py`, `web/` | Web version |
| `inputs/` | Sample DFGs and libraries (DCT 4-point, DCT 8-point, DWT) |
| `tests/` | Tests, including the check against the HarDMark tutorial |
| `build_mac.sh`, `build_windows.bat`, `.github/workflows/` | Building the apps |
| `tools/` | Icon generator and an automated click-through test of the app |
