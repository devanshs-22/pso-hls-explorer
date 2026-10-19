/* PSO Architecture Explorer — front end. All numbers come from the Python engine (app.py). */
"use strict";

const $ = (id) => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
const S = {
  source: null, uploads: { dfg: null, lib: null, dfgName: "", libName: "" },
  result: null, runIdx: 0, frames: [], frame: 0, timer: null, inspect: null, inspectFrom: null,
};

// ------------------------------------------------------------------ helpers
function el(tag, attrs = {}, parent, ns = NS) {
  const e = ns ? document.createElementNS(ns, tag) : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "style") Object.assign(e.style, v);
    else if (k === "text") e.textContent = v;
    else if (k === "html") e.innerHTML = v;
    else if (k === "cls") e.setAttribute("class", v);
    else e.setAttribute(k, v);
  }
  if (parent) parent.appendChild(e);
  return e;
}
const h = (tag, attrs, parent) => el(tag, attrs, parent, null);
const fmt = (x, d = 2) => Number(x).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const keyOf = (pos) => pos.join(",");
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
function cfgText(pos, dims) { return pos.map((n, i) => plural(n, dims[i])).join(" · "); }
function cfgShort(pos, dims) { return pos.map((n, i) => `${n}${dims[i][0].toUpperCase()}`).join("·"); }
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const data = await r.json().catch(() => ({ error: "The server sent an unreadable reply." }));
  if (!r.ok) throw new Error(data.error || `Request failed (${r.status})`);
  return data;
}

// tooltip
const tipEl = $("tooltip");
function showTip(evt, html) {
  tipEl.innerHTML = html;
  tipEl.classList.add("show");
  const pad = 14, w = tipEl.offsetWidth, hgt = tipEl.offsetHeight;
  let x = evt.clientX + pad, y = evt.clientY + pad;
  if (x + w > innerWidth - 8) x = evt.clientX - w - pad;
  if (y + hgt > innerHeight - 8) y = evt.clientY - hgt - pad;
  tipEl.style.left = `${Math.max(8, x)}px`;
  tipEl.style.top = `${Math.max(8, y)}px`;
}
const hideTip = () => tipEl.classList.remove("show");
function bindTip(node, html) {
  node.addEventListener("mousemove", (e) => showTip(e, typeof html === "function" ? html() : html));
  node.addEventListener("mouseleave", hideTip);
}
document.querySelectorAll("[data-tip]").forEach((n) => bindTip(n, n.dataset.tip));

function niceTicks(lo, hi, count = 5) {
  if (hi === lo) { hi = lo + 1; lo = lo - 1; }
  const raw = (hi - lo) / count, mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  const t = [];
  const end = Math.ceil(hi / step - 1e-9) * step;
  for (let v = Math.floor(lo / step + 1e-9) * step; v <= end + step * 1e-6; v += step) t.push(+v.toFixed(10));
  return t;
}
function hexToRgb(hx) { const n = parseInt(hx.replace("#", ""), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
function lerpColor(a, b, t) {
  const A = hexToRgb(a), B = hexToRgb(b);
  return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * t)).join(",")})`;
}
function arrowMarker(svg, id, color) {
  const defs = el("defs", {}, svg);
  const m = el("marker", { id, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" }, defs);
  el("path", { d: "M0,0 L10,5 L0,10 z", style: { fill: color } }, m);
}

// ------------------------------------------------------------------ inputs
async function loadBenchmarks() {
  let list = [];
  try { list = await api("/api/benchmarks"); } catch (e) { return showError(e.message); }
  const box = $("benchList");
  list.forEach((b) => {
    const btn = h("button", { cls: "bench", "data-id": b.id }, box);
    h("div", { cls: "glyph", text: b.title.split(" ")[0] }, btn);
    const t = h("div", {}, btn);
    h("b", { text: b.title }, t);
    h("small", { text: b.blurb }, t);
    btn.addEventListener("click", () => selectBenchmark(b.id));
  });
  const q = new URLSearchParams(location.search);
  const pre = list.find((b) => b.id.toLowerCase() === (q.get("bench") || "").toLowerCase());
  await selectBenchmark((pre || list[0])?.id);
  if (pre && q.get("run")) runPSO();
}

async function selectBenchmark(id) {
  if (!id) return;
  document.querySelectorAll(".bench").forEach((b) => b.classList.toggle("on", b.dataset.id === id));
  S.uploads = { dfg: null, lib: null, dfgName: "", libName: "" };
  document.querySelectorAll(".drop").forEach((d) => { d.classList.remove("filled"); d.querySelector(".drop-name").textContent = ""; });
  S.source = { benchmark: id };
  await describe();
}

function setupDrop(id, which) {
  const zone = $(id), input = zone.querySelector("input");
  const take = async (file) => {
    if (!file) return;
    const text = await file.text();
    S.uploads[which] = text;
    S.uploads[which + "Name"] = file.name;
    zone.classList.add("filled");
    zone.querySelector(".drop-name").textContent = file.name;
    document.querySelectorAll(".bench").forEach((b) => b.classList.remove("on"));
    if (S.uploads.dfg && S.uploads.lib) {
      S.source = { dfg_text: S.uploads.dfg, lib_text: S.uploads.lib, name: S.uploads.dfgName.replace(/(_bechmark|_benchmark)?\.txt$/i, "") };
      describe();
    } else {
      S.source = null;
      $("runBtn").disabled = true;
      showError(which === "dfg" ? "Now add the module library file." : "Now add the application (DFG) file.", true);
    }
  };
  input.addEventListener("change", () => take(input.files[0]));
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("drag"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag"));
  zone.addEventListener("drop", (e) => { e.preventDefault(); zone.classList.remove("drag"); take(e.dataTransfer.files[0]); });
}

function showError(msg, info = false) {
  const b = $("inputError");
  b.hidden = !msg;
  b.textContent = msg || "";
  b.style.background = info ? "var(--accent-soft)" : "";
  b.style.color = info ? "var(--accent)" : "";
}

function params() {
  return {
    particles: [...document.querySelectorAll("#particleChips .chip.on")].map((c) => +c.dataset.n),
    t1: +$("t1").value, max_iter: +$("maxIter").value, stall: +$("stall").value, f: +$("f").value,
    k: $("k").value, seed: +$("seed").value, include_mux_area: $("muxArea").checked,
    ac: $("ac").value.trim() || "auto", lc: $("lc").value.trim() || "auto",
  };
}

async function describe() {
  if (!S.source) return;
  try {
    const d = await api("/api/describe", { ...S.source, params: params() });
    showError("");
    renderPreview(d);
    $("runBtn").disabled = params().particles.length === 0;
  } catch (e) {
    showError(e.message);
    $("preview").hidden = true;
    $("runBtn").disabled = true;
  }
}

function renderPreview(d) {
  $("preview").hidden = false;
  drawDfg($("dfgPreview"), d.dfg);
  const lg = $("dfgLegend");
  lg.innerHTML = "";
  [...new Set(d.dfg.ops.map((o) => o.fu))].forEach((fu) => {
    lg.insertAdjacentHTML("beforeend", `<span><i class="sw" style="background:${fuColor(fu)}"></i>${fu}</span>`);
  });
  lg.insertAdjacentHTML("beforeend", `<span><i class="sw" style="background:transparent;border:1.5px solid var(--text-muted)"></i>primary input</span>`);

  const t = $("libTable");
  t.innerHTML = `<tr><th>Unit</th><th class="num">Area</th><th class="num">Delay</th><th class="num">Available</th></tr>`;
  d.library.fus.forEach((f) => {
    const used = d.dims.includes(f.name);
    t.insertAdjacentHTML("beforeend", `<tr style="${used ? "" : "color:var(--text-muted)"}"><td>${used ? `<i class="sw" style="display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;background:${fuColor(f.name)}"></i>` : ""}${f.name}</td>
      <td class="num">${fmt(f.area, 2)}</td><td class="num">${fmt(f.latency, 2)}</td><td class="num">${used ? `1 – ${f.max}` : f.max}</td></tr>`);
  });
  t.insertAdjacentHTML("beforeend", `<tr><td>register</td><td class="num">${fmt(d.library.register.area, 4)}</td><td class="num" title="ignored for latency">—</td><td class="num">as needed</td></tr>`);
  const ranges = d.dims.map((dim, i) => `${d.lower[i]}–${d.upper[i]} ${dim}s`).join(" × ");
  $("spaceNote").innerHTML = `<b>${d.dfg.ops.length}</b> operations, <b>${d.dfg.n_inputs}</b> primary inputs.<br>
    Possible designs: ${ranges} = <b>${d.space}</b>. PSO won't try every combination; it follows the swarm.`;
}

const FU_VAR = { adder: "--series-1", multiplier: "--series-2", subtractor: "--series-3" };
const fuColor = (fu) => `var(${FU_VAR[fu] || "--text-muted"})`;

// ------------------------------------------------------------------ graph drawing (DFG + scheduled DFG)
function drawGraph(container, g) {
  container.innerHTML = "";
  const colW = g.colW || 92, rowH = g.rowH || 76, left = g.left ?? 30, right = g.right ?? 30, top = g.top ?? 40, r = 17;
  const W = left + right + Math.max(1, g.cols) * colW, H = top + g.rows * rowH + 26;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, role: "img", "aria-label": g.aria || "graph" }, container);
  const muted = cssVar("--text-muted");
  arrowMarker(svg, "arr", muted);
  arrowMarker(svg, "arrHot", cssVar("--text-primary"));
  const X = (c) => left + colW * (c + 0.5), Y = (row) => top + rowH * (row + 0.5);

  (g.bands || []).forEach((b, i) => {
    if (i % 2 === 0) el("rect", { x: 0, y: Y(i) - rowH / 2, width: W, height: rowH, style: { fill: "var(--surface-2)", opacity: 0.6 } }, svg);
  });
  (g.rowLabels || []).forEach((l) => {
    el("text", { x: 10, y: Y(l.row) + 4, cls: "lbl strong", text: l.text }, svg);
    if (l.right) el("text", { x: W - 10, y: Y(l.row) + 4, "text-anchor": "end", cls: "lbl", text: l.right }, svg);
  });
  (g.colLabels || []).forEach((l) => {
    const t = el("text", { x: X(l.col), y: l.sub ? 13 : 18, "text-anchor": "middle", cls: "lbl strong", text: l.text }, svg);
    if (l.sub) el("text", { x: X(l.col), y: 27, "text-anchor": "middle", cls: "lbl muted", style: { fontSize: "10px" }, text: l.sub }, svg);
    if (l.tip) bindTip(t, l.tip);
  });

  const edgeLayer = el("g", {}, svg), nodeLayer = el("g", {}, svg);
  const pos = {};
  g.nodes.forEach((n) => { pos[n.id] = [X(n.col), Y(n.row)]; });
  const edgeEls = [];
  g.nodes.forEach((n) => {
    n.preds.forEach((p) => {
      const [x0, y0] = pos[p], [x1, y1] = pos[n.id];
      const dx = x1 - x0, dy = y1 - y0, len = Math.hypot(dx, dy) || 1;
      const sx = x0 + dx / len * r, sy = y0 + dy / len * r, ex = x1 - dx / len * (r + 3), ey = y1 - dy / len * (r + 3);
      let d = `M${sx},${sy} L${ex},${ey}`;
      if (dx === 0 && Math.abs(dy) > rowH * 1.5) {
        const bend = colW * 0.38;
        d = `M${x0 + r * 0.6},${y0 + r * 0.8} Q${x0 + bend},${(y0 + y1) / 2} ${x1 + r * 0.6},${y1 - r * 0.8 - 3}`;
      }
      edgeEls.push({ from: p, to: n.id, e: el("path", { d, cls: "edge", "marker-end": "url(#arr)" }, edgeLayer) });
    });
  });
  const nodeEls = {};
  g.nodes.forEach((n) => {
    const [x, y] = pos[n.id];
    const gn = el("g", { cls: "node", style: { cursor: "default" } }, nodeLayer);
    nodeEls[n.id] = gn;
    (n.inputs || []).forEach((lab, k, arr) => {
      const ox = arr.length > 1 ? (k ? 9 : -9) : 0;
      el("line", { x1: x + ox * 1.6, y1: y - r - 16, x2: x + ox * 0.7, y2: y - r - 1, style: { stroke: "var(--text-muted)", strokeWidth: 1.2 } }, gn);
      if (g.inputLabels) el("text", { x: x + ox * 2.2, y: y - r - 19, "text-anchor": "middle", cls: "lbl muted", style: { fontSize: "9.5px" }, text: lab }, gn);
      else el("circle", { cx: x + ox * 1.6, cy: y - r - 18, r: 2.6, style: { fill: "var(--surface-1)", stroke: "var(--text-muted)", strokeWidth: 1.2 } }, gn);
    });
    if (n.out) {
      el("line", { x1: x, y1: y + r, x2: x, y2: y + r + 12, style: { stroke: "var(--text-muted)", strokeWidth: 1.2 } }, gn);
      el("text", { x, y: y + r + 23, "text-anchor": "middle", cls: "lbl muted", style: { fontSize: "9.5px" }, text: n.out }, gn);
    }
    el("circle", { cx: x, cy: y, r, style: { fill: fuColor(n.fu), stroke: "var(--surface-1)", strokeWidth: 2.5 } }, gn);
    el("text", { x, y: y + 4, "text-anchor": "middle", style: { fill: "#fff", fontSize: "11.5px", fontWeight: 700 }, text: n.label }, gn);
    gn.addEventListener("mouseenter", () => {
      svg.classList.add("dim");
      gn.classList.add("hot");
      edgeEls.forEach((ed) => {
        if (ed.from === n.id || ed.to === n.id) {
          ed.e.classList.add("hot"); ed.e.setAttribute("marker-end", "url(#arrHot)");
          nodeEls[ed.from === n.id ? ed.to : ed.from].classList.add("hot");
        }
      });
    });
    gn.addEventListener("mouseleave", () => {
      svg.classList.remove("dim");
      svg.querySelectorAll(".hot").forEach((q) => q.classList.remove("hot"));
      edgeEls.forEach((ed) => ed.e.setAttribute("marker-end", "url(#arr)"));
      hideTip();
    });
    gn.addEventListener("mousemove", (e) => showTip(e, n.tip));
  });
}

function opTip(o, extra = "") {
  const src = [o.operand1, o.operand2].map((x) => (x ? `result of op ${x}` : "primary input"));
  return `<b>Operation ${o.id}</b> <span class="muted">(${o.fu})</span><br>${src[0]} ${o.symbol} ${src[1]}${extra}`;
}

function drawDfg(container, dfg) {
  const byLevel = {};
  dfg.ops.forEach((o) => (byLevel[o.asap] ||= []).push(o));
  const levels = Object.keys(byLevel).map(Number);
  const cols = Math.max(...levels.map((l) => byLevel[l].length));
  const nodes = [];
  levels.forEach((l) => {
    const row = byLevel[l], off = (cols - row.length) / 2;
    row.forEach((o, i) => nodes.push({
      id: o.id, col: off + i, row: l - 1, fu: o.fu, label: `${o.symbol}${o.id}`, preds: o.preds,
      inputs: [o.operand1, o.operand2].filter((x) => x === 0).map(() => "in"),
      out: o.succs.length ? null : "out", tip: opTip(o, `<br><span class="muted">earliest possible cycle: ${o.asap}</span>`),
    }));
  });
  drawGraph(container, { nodes, cols, rows: levels.length, colW: 70, rowH: 74, top: 34, left: 16, right: 16, aria: "data-flow graph" });
}

function drawSchedule(container, res, d) {
  const ops = Object.fromEntries(res.dfg.ops.map((o) => [o.id, o]));
  const usedUnits = d.units.filter((u) => d.steps.some((st) => st.some((x) => x.unit === u)));
  const col = Object.fromEntries(usedUnits.map((u, i) => [u, i]));
  const nodes = [];
  d.steps.forEach((st, s) => st.forEach(({ op, unit }) => {
    const o = ops[op], ins = d.op_inputs[op];
    nodes.push({
      id: op, col: col[unit], row: s, fu: o.fu, label: `${o.symbol}${op}`, preds: o.preds,
      inputs: [o.operand1, o.operand2].map((x, k) => (x === 0 ? ins[k] : null)).filter(Boolean),
      out: o.succs.length ? null : "output",
      tip: `<b>Operation ${op}</b> on <b>${unit}</b> in cycle ${s + 1}<br>${ins[0]} ${o.symbol} ${ins[1]} → ${d.op_output[op]}<br>` +
        `<span class="muted">${o.fu} delay ${fmt(res.library.fus.find((f) => f.name === o.fu).latency, 2)} ps</span>`,
    });
  }));
  drawGraph(container, {
    nodes, cols: usedUnits.length, rows: d.n_steps, colW: 96, rowH: 78, left: 62, right: 96, top: 42, inputLabels: true,
    bands: d.steps, colLabels: usedUnits.map((u, i) => {
      const busy = d.steps.filter((st) => st.some((x) => x.unit === u)).length;
      return { col: i, text: u, sub: `busy ${busy}/${d.n_steps}`, tip: `<b>${u}</b> is used in ${busy} of ${d.n_steps} cycles` +
        (busy > 1 ? ` (one unit reused ${busy} times)` : "") };
    }),
    rowLabels: d.steps.map((_, s) => ({ row: s, text: `CS${s + 1}`, right: `${fmt(d.step_latency[s], 2)} ps` })),
    aria: "scheduled data-flow graph",
  });
}

// ------------------------------------------------------------------ run
async function runPSO() {
  if (!S.source) return;
  stopPlay();
  $("loading").hidden = false;
  const msgs = ["Placing the swarm…", "Scheduling each candidate design…", "Allocating registers…", "Moving particles towards the best…"];
  let mi = 0;
  $("loadingText").textContent = msgs[0];
  const ticker = setInterval(() => { $("loadingText").textContent = msgs[++mi % msgs.length]; }, 450);
  const t0 = performance.now();
  try {
    const res = await api("/api/run", { ...S.source, params: params() });
    await new Promise((r) => setTimeout(r, Math.max(0, 900 - (performance.now() - t0))));
    S.result = res;
    onResult();
  } catch (e) {
    showError(e.message);
  } finally {
    clearInterval(ticker);
    $("loading").hidden = true;
  }
}

function onResult() {
  const res = S.result;
  ["explore", "result", "tradeoff"].forEach((id) => { $(id).hidden = false; });
  document.querySelectorAll(".stepper a.locked").forEach((a) => a.classList.remove("locked"));
  const tabs = $("runTabs");
  tabs.innerHTML = "";
  res.runs.forEach((r, i) => {
    const b = h("button", { cls: "tab", text: `N = ${r.n} particles` }, tabs);
    b.addEventListener("click", () => selectRun(i));
  });
  const best = res.runs.reduce((a, b) => (b.best_cost < a.best_cost - 1e-12 ? b : a));
  setInspect(best.best, `run:${res.runs.indexOf(best)}`);
  drawTradeoff();
  drawRunTable();
  drawTimes();
  selectRun(0, true);
  $("explore").scrollIntoView({ behavior: "smooth" });
}

// ------------------------------------------------------------------ exploration animation
function buildFrames(run) {
  const H = run.history, frames = [];
  let g = H[0].gbest, gc = H[0].gbest_cost, stall = 0;
  const lb = H[0].particles.map((p, i) => ({ pos: p, cost: H[0].costs[i] }));
  const visited = new Set(H[0].particles.map(keyOf));
  const snap = () => lb.map((x) => ({ ...x }));
  const take = (pos, costs) => pos.forEach((p, i) => { visited.add(keyOf(p)); if (costs[i] < lb[i].cost) lb[i] = { pos: p, cost: costs[i] }; });
  frames.push({ iter: 0, phase: "init", pos: H[0].particles, costs: H[0].costs, gbest: g, gcost: gc, improved: true, lb: snap(), visited: new Set(visited), stall });
  for (const it of H.slice(1)) {
    take(it.particles, it.costs);
    let g1 = g, gc1 = gc;
    it.costs.forEach((c, i) => { if (c < gc1 - 1e-12) { gc1 = c; g1 = it.particles[i]; } });
    frames.push({ iter: it.iteration, phase: "move", w: it.w, pos: it.particles, costs: it.costs, gbest: g1, gcost: gc1, improved: gc1 < gc - 1e-12, prevG: g, lb: snap(), visited: new Set(visited), stall });
    take(it.mutated, it.mutated_costs);
    const improvedIter = it.gbest_cost < gc - 1e-12;
    stall = improvedIter ? 0 : stall + 1;
    frames.push({ iter: it.iteration, phase: "mutate", w: it.w, pos: it.mutated, costs: it.mutated_costs, gbest: it.gbest, gcost: it.gbest_cost, improved: it.gbest_cost < gc1 - 1e-12, improvedIter, lb: snap(), visited: new Set(visited), stall });
    g = it.gbest; gc = it.gbest_cost;
  }
  const last = frames[frames.length - 1];
  frames.push({ ...last, phase: "done", improved: false });
  return frames;
}

function selectRun(i, autoplay = false) {
  stopPlay();
  S.runIdx = i;
  document.querySelectorAll("#runTabs .tab").forEach((t, k) => t.classList.toggle("on", k === i));
  S.frames = buildFrames(S.result.runs[i]);
  $("pSlider").max = S.frames.length - 1;
  buildSpaceMap();
  drawConvergence();
  showFrame(0);
  if (autoplay) setTimeout(startPlay, 700);
}

let MAP = null;
function buildSpaceMap() {
  const res = S.result, wrap = $("spaceMap");
  wrap.innerHTML = "";
  const d2 = res.dims.length >= 2;
  const rowsV = d2 ? range(res.lower[0], res.upper[0]) : [null];
  const colsV = range(res.lower[d2 ? 1 : 0], res.upper[d2 ? 1 : 0]);
  const cw = Math.max(58, Math.min(112, 600 / colsV.length)), ch = Math.max(58, Math.min(84, cw * 0.8));
  const left = d2 ? 74 : 20, top = 50;
  const W = left + cw * colsV.length + 12, H = top + ch * rowsV.length + 14;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, role: "img", "aria-label": "design space map" }, wrap);
  const costs = Object.values(res.designs).map((x) => x.cost);
  const cmin = Math.min(...costs), cmax = Math.max(...costs);
  const colDim = res.dims[d2 ? 1 : 0];
  el("text", { x: left, y: 16, cls: "lbl", text: `number of ${colDim}s →` }, svg);
  colsV.forEach((v, c) => el("text", { x: left + cw * (c + 0.5), y: top - 10, "text-anchor": "middle", cls: "lbl strong", text: v }, svg));
  if (d2) {
    el("text", { x: 8, y: top - 10, cls: "lbl", text: `${res.dims[0]}s ↓` }, svg);
    rowsV.forEach((v, r) => el("text", { x: left - 14, y: top + ch * (r + 0.5) + 4, "text-anchor": "end", cls: "lbl strong", text: v }, svg));
  }
  const cells = {};
  const lo = cssVar("--seq-lo"), hi = cssVar("--seq-hi");
  rowsV.forEach((rv, r) => colsV.forEach((cv, c) => {
    const pos = d2 ? [rv, cv, ...res.lower.slice(2)] : [cv];
    const k = keyOf(pos), des = res.designs[k];
    const g = el("g", { cls: "cell" }, svg);
    const x = left + c * cw, y = top + r * ch;
    const t = des ? (cmax > cmin ? (des.cost - cmin) / (cmax - cmin) : 0.5) : 0;
    const rect = el("rect", { x: x + 2, y: y + 2, width: cw - 4, height: ch - 4, rx: 8, style: { fill: "var(--surface-2)" } }, g);
    const txt = el("text", { x: x + 9, y: y + 17, cls: "lbl muted", style: { fontSize: "10.5px" }, text: "?" }, g);
    cells[k] = { rect, txt, cx: x + cw / 2, cy: y + ch / 2 + 5, x, y, fill: des ? lerpColor(lo, hi, 0.08 + t * 0.92) : null, ink: t > 0.55 ? "#fff" : cssVar("--text-primary"), des };
    bindTip(g, () => {
      const f = S.frames[S.frame], seen = f.visited.has(k);
      if (!des) return `<b>${cfgText(pos, res.dims)}</b><br><span class="muted">not evaluated</span>`;
      return `<b>${cfgText(pos, res.dims)}</b><br>` + (seen
        ? `cost ${fmt(des.cost, 4)}<br>area ${fmt(des.area, 2)} µm² · latency ${fmt(des.latency, 2)} ps`
        : `<span class="muted">not visited yet by the swarm</span>`);
    });
  }));
  const trails = el("g", {}, svg);
  // global-best marker: ring + star in one group, positioned with the SVG transform attribute
  const best = el("g", { "pointer-events": "none" }, svg);
  el("rect", { x: 1, y: 1, width: cw - 2, height: ch - 2, rx: 9, style: { fill: "none", stroke: "var(--text-primary)", strokeWidth: 2.5 } }, best);
  el("text", { x: cw - 7, y: ch - 8, "text-anchor": "end", style: { fill: "var(--series-2)", fontSize: "16px" }, text: "★" }, best);
  const n = S.result.runs[S.runIdx].n;
  const parts = Array.from({ length: n }, (_, i) => {
    const g = el("g", { cls: "particle", style: { cursor: "default" } }, svg);
    el("circle", { r: 10.5, style: { fill: "var(--series-2)", stroke: "var(--surface-1)", strokeWidth: 2 } }, g);
    el("text", { y: 4, "text-anchor": "middle", style: { fill: "#fff", fontSize: "10.5px", fontWeight: 700, fontFamily: "var(--font)" }, text: `P${i}` }, g);
    bindTip(g, () => {
      const f = S.frames[S.frame];
      return `<b>Particle P${i}</b><br>now: ${cfgText(f.pos[i], res.dims)} (cost ${fmt(f.costs[i], 4)})<br>own best: ${cfgText(f.lb[i].pos, res.dims)} (${fmt(f.lb[i].cost, 4)})`;
    });
    return g;
  });
  MAP = { svg, cells, parts, best, trails, cw, ch, d2, placed: false, last: null };
  $("costScale").innerHTML = `<span>cost ${fmt(cmin, 3)}</span><i class="bar"></i><span>${fmt(cmax, 3)}</span>`;
}
const range = (a, b) => Array.from({ length: b - a + 1 }, (_, i) => a + i);

function cellOf(pos) {
  return MAP.cells[keyOf(pos)] || MAP.cells[keyOf([...pos.slice(0, 2), ...S.result.lower.slice(2)])];
}

// Where particle i sits inside its square. Particles on the same design share the square
// in a small grid (below the cost label), shrinking only when the square is crowded.
function particleXY(frame, i) {
  const k = keyOf(frame.pos[i]), c = cellOf(frame.pos[i]);
  const same = frame.pos.map((p, j) => [keyOf(p), j]).filter(([kk]) => kk === k).map(([, j]) => j);
  const slot = same.indexOf(i), m = same.length;
  const availW = MAP.cw - 12, availH = MAP.ch - 30, top = c.y + 24;
  let best = { perRow: 1, pitch: 0 };
  for (let perRow = 1; perRow <= m; perRow++) {
    const rows = Math.ceil(m / perRow), pitch = Math.min(availW / perRow, availH / rows);
    if (pitch > best.pitch) best = { perRow, pitch };
  }
  const { perRow, pitch } = best, rows = Math.ceil(m / perRow);
  const row = Math.floor(slot / perRow), inRow = row === rows - 1 ? m - perRow * (rows - 1) : perRow, col = slot % perRow;
  const x = c.x + MAP.cw / 2 + (col - (inRow - 1) / 2) * pitch;
  const y = top + availH / 2 + (row - (rows - 1) / 2) * pitch;
  return [x, y, Math.min(1, pitch / 23)];
}

const REDUCED_MOTION = matchMedia("(prefers-reduced-motion: reduce)").matches;
// Tween an SVG group to (x, y, scale) through its transform attribute — identical in every browser.
function moveTo(node, x, y, s = 1, dur = 0) {
  cancelAnimationFrame(node._raf);
  const set = (a, b, c) => { node._pos = [a, b, c]; node.setAttribute("transform", `translate(${a} ${b}) scale(${c})`); };
  const from = node._pos;
  if (!from || !dur || REDUCED_MOTION) return set(x, y, s);
  const t0 = performance.now();
  const step = (now) => {
    const p = Math.min(1, (now - t0) / dur), e = p < 0.5 ? 2 * p * p : 1 - (-2 * p + 2) ** 2 / 2;
    set(from[0] + (x - from[0]) * e, from[1] + (y - from[1]) * e, from[2] + (s - from[2]) * e);
    if (p < 1) node._raf = requestAnimationFrame(step);
  };
  node._raf = requestAnimationFrame(step);
}

function showFrame(fi) {
  const frames = S.frames, f = frames[fi], prev = frames[fi - 1];
  S.frame = fi;
  $("pSlider").value = fi;
  const res = S.result, run = res.runs[S.runIdx], dims = res.dims;

  // cells
  for (const [k, c] of Object.entries(MAP.cells)) {
    const seen = f.visited.has(k) && c.des;
    c.rect.style.fill = seen ? c.fill : "var(--surface-2)";
    c.txt.textContent = seen ? fmt(c.des.cost, 3) : "?";
    c.txt.style.fill = seen ? c.ink : "var(--text-muted)";
  }
  // gbest ring + star
  const animate = MAP.placed && prev && Math.abs(fi - (MAP.last ?? fi)) === 1;
  const gc = cellOf(f.gbest);
  moveTo(MAP.best, gc.x, gc.y, 1, animate ? 450 : 0);
  // trails
  MAP.trails.innerHTML = "";
  if (animate && (f.phase === "move" || f.phase === "mutate")) {
    f.pos.forEach((p, i) => {
      const [x0, y0] = particleXY(prev, i), [x1, y1] = particleXY(f, i);
      if (Math.hypot(x1 - x0, y1 - y0) < 2) return;
      el("line", { x1: x0, y1: y0, x2: x1, y2: y1, style: { stroke: "var(--series-2)", strokeWidth: 2, opacity: 0.45, strokeDasharray: f.phase === "mutate" ? "4 4" : "none" } }, MAP.trails);
    });
  }
  MAP.parts.forEach((g, i) => {
    const [x, y, s] = particleXY(f, i);
    moveTo(g, x, y, s, animate ? (f.phase === "mutate" ? 380 : 560) : 0);
  });
  MAP.placed = true;
  MAP.last = fi;

  // narration
  const lab = (p) => `<b>${cfgText(p, dims)}</b>`;
  const stallLim = res.params.stall;
  const badge = { init: "Initial swarm", move: "Velocity update", mutate: "Mutation", done: "Finished" }[f.phase];
  $("phaseBadge").textContent = badge;
  $("iterLine").innerHTML = f.phase === "done"
    ? `Stopped after iteration ${run.iterations_run}`
    : `Iteration ${f.iter}${f.w != null ? ` <small>inertia ω = ${fmt(f.w, 3)}</small>` : ""}`;
  // The algorithm only knows its stop rule, not when it will stop: show the rule's live state.
  const dots = Array.from({ length: stallLim }, (_, k) => `<i class="${k < f.stall ? "on" : ""}"></i>`).join("");
  $("stopMeter").innerHTML = `<div class="dots">${dots}</div><span>` +
    (f.phase === "done"
      ? (run.iterations_run >= res.params.max_iter ? `hit the limit of ${res.params.max_iter} iterations` : `${stallLim} iterations in a row without improvement, so it stopped`)
      : `<b>${f.stall}</b> of ${stallLim} iterations without improvement · hard limit ${res.params.max_iter}`) + `</span>`;
  $("replayNote").innerHTML = `This is a slowed-down <b>replay</b>. The real search finished in ${fmt(run.exploration_time_ms, 2)} ms; ` +
    `while running, PSO never knew when it would stop, only the stop rule shown on the right.`;
  let txt = "";
  if (f.phase === "init") {
    txt = `The swarm is placed: <b>P0</b> at the maximum resources (${lab(f.pos[0])})` +
      (f.pos[1] ? `, <b>P1</b> at the minimum (${lab(f.pos[1])})` : "") +
      (f.pos[2] ? `, <b>P2</b> at the average (${lab(f.pos[2])})` : "") +
      (f.pos.length > 3 ? `, and P3–P${f.pos.length - 1} from the paper's random formula` : "") +
      `. Every design is scheduled and costed. The cheapest, ${lab(f.gbest)}, becomes the swarm's best.`;
  } else if (f.phase === "move") {
    txt = `Each particle gets a new velocity: part of its old motion (ω), a pull towards <b>its own best</b>, and a pull towards the <b>swarm's best</b> ${lab(f.prevG)}. ` +
      `Anything outside the library limits is pushed back inside (AETP).` +
      (f.improved ? ` <span class="delta-good">New best found: ${cfgText(f.gbest, dims)}, cost ${fmt(f.gcost, 4)}.</span>` : "");
  } else if (f.phase === "mutate") {
    txt = `Mutation keeps the swarm exploring: even particles ${dims.length > 1 ? `swap their ${dims[0]} and ${dims[1]} counts` : "rotate their values"}, odd particles jump by ±1–3. ` +
      (f.improvedIter ? `<span class="delta-good">This iteration improved the best design to ${cfgText(f.gbest, dims)} (cost ${fmt(f.gcost, 4)}).</span>`
        : `No improvement this iteration: <b>${f.stall} of ${stallLim}</b> before the search stops.`);
  } else {
    txt = `Search finished: ${run.stop_reason}. Best design ${lab(f.gbest)}, cost <b>${fmt(f.gcost, 4)}</b>. ` +
      `It was first found in iteration ${run.convergence_iter} (convergence time <b>${fmt(run.convergence_time_ms, 3)} ms</b>). ` +
      `The whole search took <b>${fmt(run.exploration_time_ms, 3)} ms</b> and looked at <b>${run.explored.length} of ${res.space}</b> designs.`;
  }
  $("narration").innerHTML = txt;
  const order = ["init", "move", "mutate", "best"];
  const on = { init: ["init"], move: ["move"], mutate: ["mutate", "best"], done: [] }[f.phase];
  document.querySelectorAll("#pipeline span").forEach((s) => {
    s.classList.toggle("on", on.includes(s.dataset.ph));
    s.classList.toggle("done", f.phase === "done" || order.indexOf(s.dataset.ph) < order.indexOf(on[0]));
  });

  // global best box + particle table
  const gb = $("gbestBox");
  gb.innerHTML = `<span class="star">★</span><div><small>Swarm's best so far</small><b>${cfgText(f.gbest, dims)}</b></div>
    <div style="margin-left:auto;text-align:right"><small>design cost</small><b>${fmt(f.gcost, 4)}</b></div>`;
  if (f.improved && animate) gb.querySelector("b").classList.add("flash");
  const gk = keyOf(f.gbest);
  $("particleTable").innerHTML = `<tr><th></th><th>Now trying</th><th class="num">Cost</th><th>Own best</th></tr>` +
    f.pos.map((p, i) => `<tr class="${keyOf(p) === gk ? "hl" : ""}"><td><span class="pdot">${i}</span></td><td>${cfgShort(p, dims)}</td>
      <td class="num">${fmt(f.costs[i], 4)}</td><td>${cfgShort(f.lb[i].pos, dims)} <span style="color:var(--text-muted)">(${fmt(f.lb[i].cost, 3)})</span></td></tr>`).join("");
  moveConvCursor(f);
}

function startPlay() {
  if (S.frame >= S.frames.length - 1) showFrame(0);
  $("pPlay").innerHTML = `<svg viewBox="0 0 24 24"><path d="M7 5h3v14H7zM14 5h3v14h-3z"/></svg>`;
  const step = () => {
    if (S.frame >= S.frames.length - 1) return stopPlay();
    showFrame(S.frame + 1);
    S.timer = setTimeout(step, +$("pSpeed").value);
  };
  S.timer = setTimeout(step, 250);
}
function stopPlay() {
  clearTimeout(S.timer);
  S.timer = null;
  $("pPlay").innerHTML = `<svg viewBox="0 0 24 24"><path d="M7 4v16l13-8z"/></svg>`;
}

// ------------------------------------------------------------------ convergence chart
let CONV = null;
function drawConvergence() {
  const res = S.result, run = res.runs[S.runIdx], wrap = $("convChart");
  wrap.innerHTML = "";
  const W = 900, H = 270, m = { l: 58, r: 24, t: 30, b: 38 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, role: "img", "aria-label": "convergence chart" }, wrap);
  const hist = run.history, xs = hist.map((x) => x.iteration), ys = hist.map((x) => x.gbest_cost);
  const xmax = Math.max(res.params.max_iter, xs[xs.length - 1]);
  let ylo = Math.min(...ys), yhi = Math.max(...ys);
  const pad = (yhi - ylo) * 0.15 || 0.01;
  const yt = niceTicks(ylo - pad, yhi + pad, 4);
  ylo = yt[0]; yhi = yt[yt.length - 1];
  const X = (v) => m.l + (v / xmax) * (W - m.l - m.r), Y = (v) => m.t + (1 - (v - ylo) / (yhi - ylo)) * (H - m.t - m.b);
  const ax = el("g", { cls: "ax" }, svg);
  yt.forEach((t) => {
    el("line", { x1: m.l, x2: W - m.r, y1: Y(t), y2: Y(t) }, ax);
    el("text", { x: m.l - 8, y: Y(t) + 4, "text-anchor": "end", text: fmt(t, 3) }, ax);
  });
  niceTicks(0, xmax, 10).filter((t) => Number.isInteger(t) && t <= xmax).forEach((t) =>
    el("text", { x: X(t), y: H - m.b + 18, "text-anchor": "middle", text: t }, ax));
  el("line", { x1: X(xmax), x2: X(xmax), y1: m.t - 8, y2: H - m.b, style: { stroke: "var(--text-muted)", strokeDasharray: "4 4" } }, svg);
  el("text", { x: X(xmax) - 4, y: m.t - 12, "text-anchor": "end", cls: "lbl muted", text: `hard limit: ${xmax} iterations` }, svg);
  el("text", { x: (m.l + W - m.r) / 2, y: H - 4, "text-anchor": "middle", cls: "lbl", text: "iteration" }, svg);
  el("text", { x: 14, y: (m.t + H - m.b) / 2, "text-anchor": "middle", cls: "lbl", transform: `rotate(-90 14 ${(m.t + H - m.b) / 2})`, text: "best cost" }, svg);
  // whole line, revealed up to the current iteration through a clip rectangle
  const clipId = `convClip${S.runIdx}`;
  const clip = el("rect", { x: 0, y: 0, width: X(0) + 6, height: H }, el("clipPath", { id: clipId }, el("defs", {}, svg)));
  let d = `M${X(xs[0])},${Y(ys[0])}`;
  for (let i = 1; i < xs.length; i++) d += ` H${X(xs[i])} V${Y(ys[i])}`;
  el("path", { d, "clip-path": `url(#${clipId})`, style: { fill: "none", stroke: "var(--series-1)", strokeWidth: 2.5, strokeLinejoin: "round" } }, svg);
  const marks = [];
  hist.forEach((hh, i) => {
    if (i === 0 || hh.gbest_cost < hist[i - 1].gbest_cost - 1e-12)
      marks.push([hh.iteration, el("circle", { cx: X(hh.iteration), cy: Y(hh.gbest_cost), r: 5, style: { fill: "var(--series-1)", stroke: "var(--surface-1)", strokeWidth: 2 } }, svg)]);
  });
  // explanation of the stop, shown only once the replay reaches the end
  // bracket BELOW the flat tail (the line only ever comes down from above), labels under it
  const ci = run.convergence_iter, last = run.iterations_run, by = Y(run.best_cost) + 14;
  const endNote = el("g", { style: { display: "none" } }, svg);
  if (last > ci) {
    el("path", { d: `M${X(ci)},${by - 5} V${by} H${X(last)} V${by - 5}`, style: { fill: "none", stroke: "var(--text-secondary)", strokeWidth: 1.2 } }, endNote);
    el("text", { x: X(ci), y: by + 15, cls: "lbl", text: `best found at iteration ${ci}, then ${last - ci} iterations without improvement → stop` }, endNote);
  } else {
    el("text", { x: X(ci), y: by + 15, cls: "lbl", text: `best found at iteration ${ci}` }, endNote);
  }
  const cursor = el("line", { y1: m.t, y2: H - m.b, style: { stroke: "var(--text-primary)", strokeWidth: 1, strokeDasharray: "3 3" } }, svg);
  const cdot = el("circle", { r: 5, style: { fill: "var(--series-1)", stroke: "var(--surface-1)", strokeWidth: 2 } }, svg);
  const hit = el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, style: { fill: "transparent", cursor: "pointer" } }, svg);
  const pick = (e) => {
    const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    return Math.max(0, Math.min(xmax, Math.round(((p.x - m.l) / (W - m.l - m.r)) * xmax)));
  };
  hit.addEventListener("mousemove", (e) => {
    const it = pick(e), shown = S.frames[S.frame].iter, hh = hist.find((x) => x.iteration === it);
    if (hh && it <= shown) showTip(e, `<b>Iteration ${it}</b><br>best: ${cfgText(hh.gbest, res.dims)}<br>cost ${fmt(hh.gbest_cost, 4)}`);
    else if (hh) showTip(e, `<b>Iteration ${it}</b><br><span class="muted">not reached yet in the replay; click to jump there</span>`);
    else hideTip();
  });
  hit.addEventListener("mouseleave", hideTip);
  hit.addEventListener("click", (e) => {
    stopPlay();
    const it = pick(e);
    const fi = S.frames.findIndex((f) => f.iter === it && (f.phase === "mutate" || f.phase === "init"));
    if (fi >= 0) showFrame(fi);
  });
  CONV = { cursor, cdot, X, Y, clip, marks, endNote };
}
function moveConvCursor(f) {
  if (!CONV) return;
  const x = CONV.X(f.iter);
  CONV.cursor.setAttribute("x1", x); CONV.cursor.setAttribute("x2", x);
  CONV.cdot.setAttribute("cx", x); CONV.cdot.setAttribute("cy", CONV.Y(f.gcost));
  CONV.clip.setAttribute("width", x + 6);
  CONV.marks.forEach(([it, c]) => { c.style.display = it <= f.iter ? "" : "none"; });
  CONV.endNote.style.display = f.phase === "done" ? "" : "none";
}

// ------------------------------------------------------------------ result (inspect a design)
function setInspect(key, from) {
  S.inspect = key;
  S.inspectFrom = from;
  renderResult();
  if (S.result) drawTradeoff();
}

function renderResult() {
  const res = S.result, d = res.designs[S.inspect], dims = res.dims;
  if (!d) return;
  const runIdx = S.inspectFrom?.startsWith("run:") ? +S.inspectFrom.slice(4) : null;
  const run = runIdx != null ? res.runs[runIdx] : null;
  const isOpt = S.inspect === res.optimum;

  // inspect bar
  const bar = $("inspectBar");
  bar.innerHTML = "<span>Showing:</span>";
  res.runs.forEach((r, i) => {
    const p = h("button", { cls: `pill ${S.inspectFrom === `run:${i}` ? "on" : ""}`, text: `PSO best, N = ${r.n}` }, bar);
    p.addEventListener("click", () => setInspect(r.best, `run:${i}`));
  });
  if (!run) h("button", { cls: "pill on", text: `Selected: ${cfgShort(d.position, dims)}` }, bar);
  h("span", { text: "· or click a point in the trade-off chart below", style: { color: "var(--text-muted)" } }, bar);

  $("resultTitle").textContent = run ? `Best design: ${cfgText(d.position, dims)}` : `Design: ${cfgText(d.position, dims)}`;
  $("resultLede").innerHTML = run
    ? `Found by PSO with <b>${run.n} particles</b> in iteration ${run.convergence_iter}, after looking at ${run.explored.length} of ${res.space} possible designs.` +
      (res.exhaustive ? (isOpt ? " A check of every design confirms this is the <b>lowest-cost design</b> there is." : " <b>Note:</b> a check of every design found a cheaper one; try more particles or another seed.") : "")
    : `A design you picked from the trade-off chart. ${isOpt ? "It is the lowest-cost design." : `Its cost is ${fmt(d.cost - res.designs[res.optimum].cost, 4)} above the best one.`}`;

  const k = $("kpis");
  k.innerHTML = "";
  const tile = (label, val, sub, hero) => k.insertAdjacentHTML("beforeend", `<div class="kpi ${hero ? "hero" : ""}"><small>${label}</small><b>${val}</b><span>${sub || "&nbsp;"}</span></div>`);
  tile("Design cost", fmt(d.cost, 4), "more negative is better", true);
  dims.forEach((dim, i) => tile(`${dim[0].toUpperCase()}${dim.slice(1)}s`, d.position[i], `of ${res.lower[i]}–${res.upper[i]} available`));
  tile("Registers", d.n_registers, "after register sharing");
  tile("Area", `${fmt(d.area, 2)}`, "µm²");
  tile("Latency", `${fmt(d.latency, 2)}`, `ps · ${d.n_steps} clock cycles`);
  if (run) {
    tile("Convergence time", `${fmt(run.convergence_time_ms, 3)}`, `ms · iteration ${run.convergence_iter}`);
    tile("Exploration time", `${fmt(run.exploration_time_ms, 3)}`, `ms · ${run.iterations_run} iterations`);
  }

  drawSchedule($("schedChart"), res, d);
  drawRat(d);
  drawCost(d);
  $("muxCount").textContent = `${d.mux2_count} × 2:1 equivalent`;
  $("muxList").innerHTML = d.muxes.length
    ? `<div class="mux-grid">${d.muxes.map(([l, t]) => `<span>${l.replace(/R-(\d+)/, (_, r) => d.reg_colors[+r].name)}: ${t}</span>`).join("")}</div>`
    : `<p class="footnote">No multiplexers needed.</p>`;
}

// RAT exactly as Table 1 of the paper: rows = registers named by colour ("Red (R)"),
// columns = control steps C0..Cn, cells = storage variable held, "–" when empty.
function drawRat(d) {
  const res = S.result, vars = Object.fromEntries(d.variables.map((v) => [v.name, v]));
  const ops = Object.fromEntries(res.dfg.ops.map((o) => [o.id, o]));
  const stepOf = {};
  d.steps.forEach((st, s) => st.forEach(({ op }) => { stepOf[op] = s + 1; }));
  const readers = {};
  Object.entries(d.op_inputs).forEach(([op, ins]) => new Set(ins).forEach((v) => (readers[v] ||= []).push(+op)));
  const nCols = d.rat.length;
  const t = h("table", { cls: "rat paper" });
  const hr = h("tr", {}, t);
  h("th", {}, hr);
  for (let b = 0; b < nCols; b++) h("th", { text: `C${b}` }, hr);
  const clear = () => { t.querySelectorAll(".hot").forEach((x) => x.classList.remove("hot")); hideTip(); };
  for (let r = 0; r < d.n_registers; r++) {
    const col = d.reg_colors[r], tr = h("tr", {}, t);
    h("th", { cls: "rowh", text: `${col.name} (${col.abbr})` }, tr);
    for (let b = 0; b < nCols; b++) {
      const v = d.rat[b][r];
      const td = h("td", { text: v || "–" }, tr);
      if (!v) { td.className = "empty"; continue; }
      td.dataset.v = v;
      const info = vars[v];
      td.addEventListener("mouseenter", () => t.querySelectorAll(`td[data-v="${v}"]`).forEach((x) => x.classList.add("hot")));
      td.addEventListener("mouseleave", clear);
      td.addEventListener("mousemove", (e) => {
        const what = info.producer ? `output of operation ${info.producer} (${ops[info.producer].symbol}, control step ${stepOf[info.producer]})` : "primary input";
        const users = (readers[v] || []).map((o) => `op ${o} (C${stepOf[o]})`).join(", ");
        showTip(e, `<b>${v}</b>: ${what}<br>register <b>${col.name}</b>, ${info.birth === info.last ? `C${info.birth}` : `C${info.birth}–C${info.last}`}` +
          `<br><span class="muted">${users ? `read by ${users}` : "final output"}</span>`);
      });
    }
  }
  $("ratTable").innerHTML = "";
  $("ratTable").appendChild(t);
  const nOps = res.dfg.ops.length, ni = res.dfg.n_inputs;
  $("ratLegend").innerHTML = `<span>V0–V${ni - 1}: primary inputs · V${ni}–V${ni + nOps - 1}: outputs of op1–op${nOps}. ` +
    `C0 = inputs, Ck = values held after control step k. ${d.n_registers} registers.</span>`;
}

function drawCost(d) {
  const res = S.result;
  const aTerm = res.t1 * (d.area - res.ac) / res.amax, lTerm = res.t2 * (d.latency - res.lc) / res.lmax;
  const lines = d.area_terms.map((a) => `<div class="line"><span>${a.count} × ${a.fu} (${fmt(a.unit, 2)} µm²)</span><span>${fmt(a.total, 2)} µm²</span></div>`);
  lines.push(`<div class="line"><span>${d.n_registers} registers (${fmt(d.reg_area / Math.max(1, d.n_registers), 4)} µm²)</span><span>${fmt(d.reg_area, 2)} µm²</span></div>`);
  if (res.include_mux_area) lines.push(`<div class="line"><span>${d.mux2_count} × 2:1 mux</span><span>${fmt(d.mux_area, 2)} µm²</span></div>`);
  lines.push(`<div class="line"><span><b>Area A</b></span><span><b>${fmt(d.area, 2)} µm²</b></span></div>`);
  lines.push(`<div class="line"><span><b>Latency L</b> (${d.n_steps} cycles)</span><span><b>${fmt(d.latency, 2)} ps</b></span></div>`);
  const bar = (val, max, color) => `<div class="b"><i style="width:${Math.max(0, Math.min(100, val / max * 100))}%;background:${color}"></i></div>`;
  $("costBreakdown").innerHTML = `<div class="formula">${lines.join("")}
    <div class="bars">
      <label><span>t1 × (A − Ac) / Amax = ${res.t1} × (${fmt(d.area, 1)} − ${fmt(res.ac, 1)}) / ${fmt(res.amax, 1)}</span><b>${fmt(aTerm, 4)}</b></label>
      ${bar(d.area, res.amax, "var(--series-1)")}
      <label><span>t2 × (L − Lc) / Lmax = ${res.t2} × (${fmt(d.latency, 1)} − ${fmt(res.lc, 1)}) / ${fmt(res.lmax, 1)}</span><b>${fmt(lTerm, 4)}</b></label>
      ${bar(d.latency, res.lmax, "var(--series-2)")}
    </div>
    <div class="line total"><span>Design cost</span><span>${fmt(d.cost, 4)}</span></div></div>
    <p class="footnote">Bars show A / Amax and L / Lmax. Amax = area with the most hardware (${fmt(res.amax, 2)} µm²);
      Lmax = latency with the least hardware (${fmt(res.lmax, 2)} ps). Constraints Ac = ${fmt(res.ac, 2)} µm², Lc = ${fmt(res.lc, 2)} ps
      ${Math.abs(res.ac - res.amax) < 1e-9 && Math.abs(res.lc - res.lmax) < 1e-9 ? "(set to Amax / Lmax, so every design's cost is negative)" : "(set by you)"}. More negative = better.</p>`;
}

// ------------------------------------------------------------------ trade-off, runs table, times
function drawTradeoff() {
  const res = S.result, wrap = $("tradeChart");
  wrap.innerHTML = "";
  const pts = Object.values(res.designs), dims = res.dims;
  const visited = new Set(res.runs.flatMap((r) => r.explored));
  const W = 760, H = 460, m = { l: 66, r: 24, t: 20, b: 50 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, role: "img", "aria-label": "area versus latency chart" }, wrap);
  const lx = pts.map((p) => p.latency), ly = pts.map((p) => p.area);
  const xpad = (Math.max(...lx) - Math.min(...lx)) * 0.08 || 50, ypad = (Math.max(...ly) - Math.min(...ly)) * 0.08 || 20;
  const xt = niceTicks(Math.min(...lx) - xpad, Math.max(...lx) + xpad), yt = niceTicks(Math.min(...ly) - ypad, Math.max(...ly) + ypad);
  const X = (v) => m.l + (v - xt[0]) / (xt[xt.length - 1] - xt[0]) * (W - m.l - m.r);
  const Y = (v) => m.t + (1 - (v - yt[0]) / (yt[yt.length - 1] - yt[0])) * (H - m.t - m.b);
  const ax = el("g", { cls: "ax" }, svg);
  yt.forEach((t) => { el("line", { x1: m.l, x2: W - m.r, y1: Y(t), y2: Y(t) }, ax); el("text", { x: m.l - 8, y: Y(t) + 4, "text-anchor": "end", text: fmt(t, 0) }, ax); });
  xt.forEach((t) => { el("line", { x1: X(t), x2: X(t), y1: m.t, y2: H - m.b }, ax); el("text", { x: X(t), y: H - m.b + 18, "text-anchor": "middle", text: fmt(t, 0) }, ax); });
  el("text", { x: (m.l + W - m.r) / 2, y: H - 8, "text-anchor": "middle", cls: "lbl", text: "latency (ps) → slower" }, svg);
  el("text", { x: 16, y: (m.t + H - m.b) / 2, "text-anchor": "middle", cls: "lbl", transform: `rotate(-90 16 ${(m.t + H - m.b) / 2})`, text: "area (µm²) → bigger" }, svg);
  const front = res.pareto.map((k) => res.designs[k]);
  el("path", { d: front.map((p, i) => `${i ? "L" : "M"}${X(p.latency)},${Y(p.area)}`).join(" "), style: { fill: "none", stroke: "var(--text-secondary)", strokeWidth: 1.5, strokeDasharray: "6 5" } }, svg);
  const offsets = {};
  pts.forEach((p) => {
    const cx = X(p.latency), cy = Y(p.area), vis = visited.has(p.key), isOpt = p.key === res.optimum, sel = p.key === S.inspect;
    const g = el("g", { style: { cursor: "pointer" } }, svg);
    el("circle", { cx, cy, r: 14, style: { fill: "transparent" } }, g);
    if (sel) el("circle", { cx, cy, r: 13, style: { fill: "none", stroke: "var(--text-primary)", strokeWidth: 2 } }, g);
    if (isOpt) el("text", { x: cx, y: cy + 7, "text-anchor": "middle", style: { fill: "var(--series-2)", fontSize: "22px", stroke: "var(--surface-1)", strokeWidth: 1 }, text: "★" }, g);
    else el("circle", { cx, cy, r: 6, style: vis ? { fill: "var(--series-1)", stroke: "var(--surface-1)", strokeWidth: 2 } : { fill: "var(--surface-1)", stroke: "var(--text-muted)", strokeWidth: 1.8 } }, g);
    const lk = `${Math.round(cx)},${Math.round(cy)}`;
    offsets[lk] = (offsets[lk] || 0) + 1;
    el("text", { x: cx + 10, y: cy - 7 - (offsets[lk] - 1) * 11, cls: "lbl muted", style: { fontSize: "10px" }, text: cfgShort(p.position, dims) }, g);
    bindTip(g, `<b>${cfgText(p.position, dims)}</b><br>area ${fmt(p.area, 2)} µm² · latency ${fmt(p.latency, 2)} ps<br>cost <b>${fmt(p.cost, 4)}</b>${isOpt ? " (lowest)" : ""}` +
      `<br><span class="muted">${vis ? "visited by PSO" : "never visited by PSO"}${res.pareto.includes(p.key) ? " · on the Pareto front" : ""}<br>click to inspect</span>`);
    g.addEventListener("click", () => {
      hideTip();
      const ri = res.runs.findIndex((r) => r.best === p.key);
      setInspect(p.key, ri >= 0 ? `run:${ri}` : "pick");
      $("result").scrollIntoView({ behavior: "smooth" });
    });
  });
  const anyUnvisited = pts.some((p) => !visited.has(p.key));
  $("tradeLegend").innerHTML = `<span><i class="sw" style="background:var(--series-1)"></i>visited by PSO</span>` +
    (anyUnvisited ? `<span><i class="sw" style="border:1.8px solid var(--text-muted)"></i>never visited (evaluated afterwards, only for this chart)</span>` : "") +
    `<span><b style="color:var(--series-2)">★</b> lowest design cost</span><span>- - - Pareto front</span>` +
    (res.exhaustive ? "" : `<span>design space too large: only visited designs shown</span>`);
}

function drawRunTable() {
  const res = S.result, t = $("runTable");
  t.innerHTML = `<tr><th>N</th><th>Best</th><th class="num">Cost</th><th class="num">Found at</th><th class="num">Iterations</th><th class="num">Visited</th></tr>`;
  res.runs.forEach((r, i) => {
    const tr = h("tr", { cls: "clickable", title: "watch this run" }, t);
    tr.innerHTML = `<td><b>${r.n}</b></td><td>${cfgShort(r.best.split(",").map(Number), res.dims)}</td><td class="num">${fmt(r.best_cost, 4)}</td>
      <td class="num">iter ${r.convergence_iter}</td><td class="num">${r.iterations_run}</td><td class="num">${r.explored.length}/${res.space}</td>`;
    tr.addEventListener("click", () => { selectRun(i); $("explore").scrollIntoView({ behavior: "smooth" }); });
  });
  const allOk = res.runs.every((r) => Math.abs(r.best_cost - res.designs[res.optimum].cost) < 1e-12);
  const v = $("verifyNote");
  v.className = `verify ${res.exhaustive && !allOk ? "bad" : ""}`;
  v.innerHTML = res.exhaustive
    ? (allOk ? `✓ Checked against all <b>${res.space}</b> designs (after the runs): every PSO run found the true optimum, <b>${cfgText(res.optimum.split(",").map(Number), res.dims)}</b>.`
      : `Some runs stopped at a design that is not the true optimum (${cfgShort(res.optimum.split(",").map(Number), res.dims)}). Try more particles or another seed.`)
    : `The design space (${res.space} designs) is too large for an exhaustive check.`;
}

function drawTimes() {
  const res = S.result, wrap = $("timeChart");
  wrap.innerHTML = "";
  const W = 420, H = 220, m = { l: 48, r: 10, t: 30, b: 30 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, role: "img", "aria-label": "time comparison" }, wrap);
  const maxv = Math.max(...res.runs.map((r) => r.exploration_time_ms));
  const yt = niceTicks(0, maxv, 4);
  const Y = (v) => m.t + (1 - v / yt[yt.length - 1]) * (H - m.t - m.b);
  const ax = el("g", { cls: "ax" }, svg);
  yt.forEach((t) => { el("line", { x1: m.l, x2: W - m.r, y1: Y(t), y2: Y(t) }, ax); el("text", { x: m.l - 6, y: Y(t) + 4, "text-anchor": "end", text: fmt(t, t < 1 ? 1 : 0) }, ax); });
  el("text", { x: 8, y: 14, cls: "lbl", text: "ms" }, svg);
  const lg = [["Convergence", "--series-1"], ["Exploration", "--series-2"]];
  lg.forEach(([t, c], i) => {
    el("rect", { x: W - 200 + i * 100, y: 5, width: 10, height: 10, rx: 2, style: { fill: `var(${c})` } }, svg);
    el("text", { x: W - 186 + i * 100, y: 14, cls: "lbl", text: t }, svg);
  });
  const slot = (W - m.l - m.r) / res.runs.length, bw = Math.min(34, slot * 0.3);
  res.runs.forEach((r, i) => {
    const cx = m.l + slot * (i + 0.5);
    [[r.convergence_time_ms, "--series-1", "Convergence"], [r.exploration_time_ms, "--series-2", "Exploration"]].forEach(([v, c, name], j) => {
      const x = cx + (j ? 1 : -bw - 1), y = Y(v), hgt = Y(0) - y;
      const b = el("path", { d: `M${x},${Y(0)} V${y + 4} Q${x},${y} ${x + 4},${y} H${x + bw - 4} Q${x + bw},${y} ${x + bw},${y + 4} V${Y(0)} Z`, style: { fill: `var(${c})` } }, svg);
      if (hgt < 4) b.setAttribute("d", `M${x},${Y(0)} V${y} H${x + bw} V${Y(0)} Z`);
      bindTip(b, `<b>N = ${r.n}</b><br>${name} time: ${fmt(v, 3)} ms`);
    });
    el("text", { x: cx, y: H - 10, "text-anchor": "middle", cls: "lbl strong", text: `N = ${r.n}` }, svg);
  });
}

// ------------------------------------------------------------------ chrome: stepper, theme, wiring
function setupStepper() {
  const links = [...document.querySelectorAll("#stepper a")];
  const obs = new IntersectionObserver((ents) => {
    ents.forEach((e) => {
      if (!e.isIntersecting) return;
      links.forEach((a) => a.classList.toggle("active", a.dataset.step === e.target.id));
    });
  }, { rootMargin: "-40% 0px -55% 0px" });
  document.querySelectorAll("main > section").forEach((s) => obs.observe(s));
}

function setupTheme() {
  const root = document.documentElement;
  try { const saved = localStorage.getItem("pso-theme"); if (saved) root.dataset.theme = saved; } catch (e) { /* storage unavailable */ }
  const qt = new URLSearchParams(location.search).get("theme");
  if (qt === "light" || qt === "dark") root.dataset.theme = qt;
  $("themeBtn").addEventListener("click", () => {
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("pso-theme", root.dataset.theme); } catch (e) { /* ignore */ }
    if (S.result) { const f = S.frame; buildSpaceMap(); drawConvergence(); showFrame(f); drawGraphsAgain(); }
    else if (S.source) describe();
  });
}
function drawGraphsAgain() { renderResult(); drawTradeoff(); drawTimes(); }

function wire() {
  document.querySelectorAll("#particleChips .chip").forEach((c) => c.addEventListener("click", () => {
    c.classList.toggle("on");
    $("runBtn").disabled = !S.source || params().particles.length === 0;
  }));
  $("t1").addEventListener("input", () => {
    const t1 = +$("t1").value;
    $("t1Val").textContent = `area ${fmt(t1, 2)} · latency ${fmt(1 - t1, 2)}`;
  });
  $("runBtn").addEventListener("click", runPSO);
  $("pPlay").addEventListener("click", () => (S.timer ? stopPlay() : startPlay()));
  $("pFirst").addEventListener("click", () => { stopPlay(); showFrame(0); });
  $("pLast").addEventListener("click", () => { stopPlay(); showFrame(S.frames.length - 1); });
  $("pPrev").addEventListener("click", () => { stopPlay(); showFrame(Math.max(0, S.frame - 1)); });
  $("pNext").addEventListener("click", () => { stopPlay(); showFrame(Math.min(S.frames.length - 1, S.frame + 1)); });
  $("pSlider").addEventListener("input", () => { stopPlay(); showFrame(+$("pSlider").value); });
  $("downloadBtn").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(S.result, null, 2)], { type: "application/json" });
    const a = h("a", { href: URL.createObjectURL(blob), download: `pso_${S.result.dfg.name}.json` });
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  document.addEventListener("keydown", (e) => {
    if (!S.result || ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
    if (e.key === "ArrowRight") { stopPlay(); showFrame(Math.min(S.frames.length - 1, S.frame + 1)); }
    if (e.key === "ArrowLeft") { stopPlay(); showFrame(Math.max(0, S.frame - 1)); }
  });
  setupDrop("dropDfg", "dfg");
  setupDrop("dropLib", "lib");
}

wire();
setupStepper();
setupTheme();
loadBenchmarks();
