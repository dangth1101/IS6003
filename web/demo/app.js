// Flow demo: draws the as-is and to-be flows, replays the sample run from replay.json,
// and shows the official results from ../results.json. Text comes from demo.vi.json.
import { buildLayout, dotPosition, badgeWidth, HEADER, LANES, TYPE, SPACE, PILL_H, BADGE_H, CHIP } from "./layout.js";
import { prepare, stateAt, qcQueueSeries, clock, along, MONTH } from "./state.js";
import { figures } from "./figures.js";

const SVG = "http://www.w3.org/2000/svg";
const DAYS_PER_SECOND = 6.25; // 1x: the 375-day window in 60 s, a month in about 3.3 s
const SPEEDS = [0.5, 1, 2, 4];
const TRAVEL_MS = 520;
const FADE_MS = 260;
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

let T; // content
let NUM;
const fill = (s, vars = {}) => s.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? vars[k] : `{${k}}`));
const fmt = (v, d = 1) => NUM(d).format(v);
const pct = (v, d = 1) => NUM(d, "percent").format(v);

function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) k === "text" ? (n.textContent = v) : n.setAttribute(k, v);
  for (const c of kids.flat()) if (c != null) n.append(c);
  return n;
}
function sv(tag, attrs = {}, ...kids) {
  const n = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) k === "text" ? (n.textContent = v) : n.setAttribute(k, v);
  for (const c of kids.flat()) if (c != null) n.append(c);
  return n;
}

// ---------- text fitting ----------

const ctx = document.createElement("canvas").getContext("2d");
const textWidth = (text, size, weight) => {
  ctx.font = `${weight} ${size}px "Be Vietnam Pro", system-ui, sans-serif`;
  return ctx.measureText(text).width;
};
// Split a label into at most two lines: as even as possible (task boxes), or with as much as fits
// on the first line (lane names). The layout sizes each box so its label fits at the given size;
// nothing is shrunk below the type scale.
function wrap(text, size, weight, maxW, even = true) {
  if (textWidth(text, size, weight) <= maxW) return { lines: [text], size };
  const words = text.split(" ");
  let best = [text];
  let bestW = Infinity;
  for (let k = 1; k < words.length; k++) {
    const lines = [words.slice(0, k).join(" "), words.slice(k).join(" ")];
    const widths = lines.map((l) => textWidth(l, size, weight));
    if (!even) {
      if (widths[0] <= maxW) best = lines;
      continue;
    }
    const w = Math.max(...widths);
    if (w < bestW) { best = lines; bestW = w; }
  }
  return { lines: best, size };
}
// First baseline of a text block whose glyph box starts at `top`.
const baseline = (top, size) => top + TYPE.ascent * size;

// ---------- the flow drawing ----------

function roundedPath(pts, r) {
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let k = 1; k < pts.length - 1; k++) {
    const [px, py] = pts[k - 1], [x, y] = pts[k], [nx, ny] = pts[k + 1];
    const d1 = Math.hypot(x - px, y - py), d2 = Math.hypot(nx - x, ny - y);
    const rr = Math.min(r, d1 / 2, d2 / 2);
    const ax = x + ((px - x) / d1) * rr, ay = y + ((py - y) / d1) * rr;
    const bx = x + ((nx - x) / d2) * rr, by = y + ((ny - y) / d2) * rr;
    d += ` L${ax},${ay} Q${x},${y} ${bx},${by}`;
  }
  const last = pts[pts.length - 1];
  return d + ` L${last[0]},${last[1]}`;
}

function drawFlow(layout, scenario) {
  const { width, height, lanes, boxes, edges, bands, markers, metrics: m } = layout;
  const svg = sv("svg", { class: "flow", viewBox: `0 0 ${width} ${height + 2}`, role: "img", "aria-label": scenario.name, preserveAspectRatio: "xMidYMid meet" });
  const uid = `${scenario.id}-${height}`;
  svg.append(sv("defs", {},
    sv("marker", { id: `arrow-${uid}`, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" },
      sv("path", { d: "M0,1 L9,5 L0,9 z", fill: "var(--edge)" })),
    sv("marker", { id: `arrow-hot-${uid}`, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" },
      sv("path", { d: "M0,1 L9,5 L0,9 z", fill: "var(--orange)" }))));

  // lanes: name, then the head count (and the C4 change in the to-be QC lane), from the lane's top
  LANES.forEach((id, i) => {
    const L = lanes[id];
    svg.append(sv("rect", { x: 0, y: L.top, width, height: L.h, fill: i % 2 ? "var(--lane-alt)" : "var(--lane)", "data-lane-bg": id }));
    svg.append(sv("line", { x1: 0, x2: width, y1: L.bottom, y2: L.bottom, stroke: "var(--line)", "stroke-width": 1 }));
  });
  svg.append(sv("line", { x1: HEADER, x2: HEADER, y1: 0, y2: height, stroke: "var(--line)" }));
  const caps = scenario.capacities;
  const asIsCaps = scenario.asIsCapacities;
  const laneX = SPACE.l;
  for (const id of LANES) {
    const L = lanes[id];
    const name = wrap(T.lanes[id], TYPE.lg, 700, HEADER - laneX - SPACE.s, false);
    const g = sv("g", { "data-lane": id });
    const y0 = baseline(L.top + m.laneTop, TYPE.lg); // level with the tops of the boxes
    name.lines.forEach((line, k) => g.append(sv("text", { x: laneX, y: y0 + k * TYPE.lg * TYPE.line, "font-size": TYPE.lg, "font-weight": 700, fill: "var(--ink)", text: line })));
    const nameBottom = y0 + (name.lines.length - 1) * TYPE.lg * TYPE.line + TYPE.descent * TYPE.lg;
    const py = baseline(nameBottom + SPACE.xs, TYPE.sm);
    const changed = asIsCaps && asIsCaps[id] !== caps[id];
    if (changed) {
      g.append(sv("text", { x: laneX, y: py, "font-size": TYPE.sm, "font-weight": 600, fill: "var(--orange-ink)", text: `${asIsCaps[id]} → ${fill(T.people, { n: caps[id] })}` }));
      g.append(chipSvg("C4", laneX, py + TYPE.descent * TYPE.sm + SPACE.s));
    } else if (caps[id]) {
      g.append(sv("text", { x: laneX, y: py, "font-size": TYPE.sm, fill: "var(--muted)", text: fill(T.people, { n: caps[id] }) }));
    }
    svg.append(g);
  }

  // highlight bands (bottleneck in the as-is, C1 in the to-be), labelled just below the QC lane
  for (const band of bands) {
    svg.append(sv("rect", { x: band.x, y: band.y, width: band.w, height: band.h, rx: 12, fill: "var(--orange-soft)", stroke: "var(--orange)", "stroke-width": 1.2, "stroke-dasharray": band.kind === "change" ? null : "5 4", "data-band": band.kind }));
    const [lx, ly] = band.label;
    if (band.kind === "change") {
      const text = T.changes.C1.detail;
      const tw = textWidth(text, TYPE.md, 600);
      const x0 = lx - (CHIP.w + SPACE.m + tw) / 2;
      svg.append(chipSvg("C1", x0, ly - TYPE.ascent * TYPE.md + 1));
      svg.append(sv("text", { x: x0 + CHIP.w + SPACE.m, y: ly, "font-size": TYPE.md, "font-weight": 600, fill: "var(--orange-ink)", text }));
    } else {
      svg.append(sv("text", { x: lx, y: ly, "text-anchor": "middle", "font-size": TYPE.md, "font-weight": 600, fill: "var(--orange-ink)", text: T.bottleneck }));
    }
  }

  // go-live line, labelled at the top of the first lane
  const gx = markers.goLive;
  const gTop = lanes[LANES[0]].top + SPACE.s;
  svg.append(sv("line", { x1: gx, x2: gx, y1: SPACE.s, y2: height - SPACE.s, stroke: "var(--teal)", "stroke-width": 1.5, "stroke-dasharray": "3 5" }));
  svg.append(sv("text", { x: gx + SPACE.m, y: baseline(gTop, TYPE.lg), "font-size": TYPE.lg, "font-weight": 700, fill: "var(--teal)", text: T.markers.go_live }));
  svg.append(sv("text", { x: gx + SPACE.m, y: baseline(gTop + (TYPE.ascent + TYPE.descent) * TYPE.lg + SPACE.xs, TYPE.sm), "font-size": TYPE.sm, fill: "var(--muted)", text: T.markers.go_live_note }));

  // edges, and the rework rate of each loop as a pill on or beside its arrow
  const rates = Object.fromEntries(scenario.rework.map((r) => [r.gateway_id, r.rate]));
  const edgeLayer = sv("g", { fill: "none" });
  const labelLayer = sv("g", {});
  for (const e of edges) {
    if (e.silent) continue;
    const hot = e.hot;
    edgeLayer.append(sv("path", {
      d: roundedPath(e.pts, e.loop ? 16 : 9),
      stroke: hot ? "var(--orange)" : "var(--edge)", "stroke-width": hot ? 2 : 1.6,
      "stroke-dasharray": e.loop ? "6 4" : null,
      "marker-end": e.noArrow ? null : `url(#${hot ? "arrow-hot" : "arrow"}-${uid})`,
    }));
    if (typeof e.loop === "string" && e.label && rates[e.loop] != null) {
      const text = fill(T.loops[e.loop], { rate: pct(rates[e.loop], 0) });
      const w = textWidth(text, TYPE.sm, 700) + 2 * SPACE.m;
      const { x, y, anchor } = e.label;
      const left = anchor === "end" ? x - w : x - w / 2;
      labelLayer.append(sv("g", { "data-pill": e.loop },
        sv("rect", { x: left, y: y - PILL_H / 2, width: w, height: PILL_H, rx: PILL_H / 2, fill: "var(--surface)", stroke: hot ? "var(--orange)" : "var(--edge)", "stroke-width": 1.2 }),
        sv("text", { x: left + w / 2, y: y + 0.36 * TYPE.sm, "text-anchor": "middle", "font-size": TYPE.sm, "font-weight": 700, fill: hot ? "var(--orange-ink)" : "var(--ink)", text })));
    }
  }
  svg.append(edgeLayer);

  // markers
  const { start, rejected, closed, split } = markers;
  svg.append(sv("circle", { cx: start.x, cy: start.y, r: 9, fill: "var(--surface)", stroke: "var(--ink)", "stroke-width": 2 }));
  for (const p of [rejected, closed]) svg.append(sv("circle", { cx: p.x, cy: p.y, r: 9, fill: "var(--surface)", stroke: "var(--ink)", "stroke-width": 3.5 }));
  svg.append(sv("text", { x: rejected.x, y: baseline(rejected.y + 9 + SPACE.xs, TYPE.sm), "text-anchor": "middle", "font-size": TYPE.sm, fill: "var(--muted)", text: T.markers.rejected }));
  svg.append(sv("circle", { cx: split.x, cy: split.y, r: 5, fill: "var(--surface)", stroke: "var(--edge)", "stroke-width": 2 }));

  // tasks: the label on top, the status strip (queue and dots) along the bottom
  for (const box of Object.values(boxes)) {
    const change = layout.changed[box.id];
    const afterGoLive = box.cx > gx;
    const g = sv("g", { "data-box-group": box.id });
    g.append(sv("rect", {
      x: box.left, y: box.top, width: box.w, height: m.boxH, rx: 10, "data-box": box.id,
      fill: change === "C2" ? "var(--orange-soft)" : "var(--surface)",
      stroke: change ? "var(--orange)" : afterGoLive ? "var(--line)" : "#a9bcc0", "stroke-width": change ? 2 : 1.3,
    }));
    const label = wrap(T.activities[box.id], TYPE.md, 600, box.w - 10);
    const lh = TYPE.md * TYPE.line;
    const blockH = (TYPE.ascent + TYPE.descent) * TYPE.md + (label.lines.length - 1) * lh;
    const y0 = baseline(box.top + m.labelTop + (m.labelH - blockH) / 2, TYPE.md);
    const lg = sv("g", { "data-label": box.id });
    label.lines.forEach((line, k) => lg.append(sv("text", {
      x: box.cx, y: y0 + k * lh, "text-anchor": "middle", "font-size": TYPE.md, "font-weight": 600,
      fill: afterGoLive ? "var(--muted)" : "var(--ink)", text: line,
    })));
    g.append(lg);
    if (change) g.append(chipSvg(change, box.right + SPACE.s, box.top));
    svg.append(g);
  }
  svg.append(labelLayer);

  const dynamic = sv("g", {});
  const badges = sv("g", {});
  svg.append(dynamic, badges);
  return { svg, dynamic, badges };
}

function chipSvg(text, x, y) {
  return sv("g", { "data-chip": text },
    sv("rect", { x, y, width: CHIP.w, height: CHIP.h, rx: 5, fill: "var(--orange)" }),
    sv("text", { x: x + CHIP.w / 2, y: y + CHIP.h / 2 + 0.36 * TYPE.sm, "text-anchor": "middle", "font-size": TYPE.sm, "font-weight": 700, fill: "#fff", text }));
}

// ---------- one animated flow ----------

class FlowView {
  constructor(scenario, prep, layout) {
    this.scenario = scenario;
    this.prep = prep;
    this.layout = layout;
    const { svg, dynamic, badges } = drawFlow(layout, scenario);
    this.svg = svg;
    this.layer = dynamic;
    this.badgeLayer = badges;
    this.dots = new Map(); // row index -> dot
    this.badges = new Map(); // task -> badge
    this.edgeIndex = new Map(layout.edges.filter((e) => !e.line).map((e) => [`${e.from}>${e.to}`, e.pts]));
  }

  update(state, now, dt) {
    const L = this.layout;
    const r = L.metrics.dot;
    const seen = new Set();
    for (const item of state.items) {
      const target = dotPosition(L, item.task, item.mode, item.slot, item.count, state.waitCounts[item.task] ?? 0);
      seen.add(item.i);
      let dot = this.dots.get(item.i);
      if (!dot) {
        const prevDot = item.prev != null ? this.dots.get(item.prev) : null;
        const prevRow = item.prev != null ? this.prep.rows[item.prev] : null;
        let from = prevDot ? [prevDot.x, prevDot.y] : null;
        let path = null;
        if (prevRow) path = this.edgeIndex.get(`${prevRow.activity}>${item.task}`);
        else if (item.task === "Task_RegisterRequest") {
          const s = L.markers.start;
          from = [s.x, s.y];
          path = [[s.x, s.y]];
        }
        const el = sv("circle", { r, class: "dot" });
        const start = from ?? target ?? [0, 0];
        dot = { el, x: start[0], y: start[1], opacity: from ? 1 : 0, travel: null, mode: null };
        if (from && !REDUCED) dot.travel = { pts: [from, ...(path ?? []), target ?? from], t0: now };
        this.layer.append(el);
        this.dots.set(item.i, dot);
        if (prevDot) prevDot.claimed = true;
      }
      dot.target = target;
      dot.gone = null;
      const mode = item.mode === "work" && item.live ? "live" : item.mode;
      if (mode !== dot.mode) {
        dot.mode = mode;
        const style = DOT_STYLE[mode];
        dot.el.setAttribute("fill", style.fill);
        dot.el.setAttribute("stroke", style.stroke);
        dot.el.setAttribute("stroke-width", style.width);
      }
    }
    for (const [i, dot] of this.dots) {
      if (seen.has(i)) continue;
      if (dot.claimed || REDUCED) { dot.el.remove(); this.dots.delete(i); continue; }
      dot.gone ??= now;
    }
    for (const [i, dot] of this.dots) {
      if (dot.gone != null) {
        const f = (now - dot.gone) / FADE_MS;
        if (f >= 1) { dot.el.remove(); this.dots.delete(i); continue; }
        dot.opacity = 1 - f;
      } else if (dot.travel) {
        const f = (now - dot.travel.t0) / TRAVEL_MS;
        if (f >= 1) dot.travel = null;
        else {
          const e = f < 0.5 ? 2 * f * f : 1 - (-2 * f + 2) ** 2 / 2;
          [dot.x, dot.y] = along(dot.travel.pts, e);
        }
        dot.opacity = Math.min(1, dot.opacity + dt / 150);
      }
      if (!dot.travel && dot.gone == null) {
        if (dot.target) {
          const k = REDUCED ? 1 : 1 - Math.exp(-dt / 90);
          dot.x += (dot.target[0] - dot.x) * k;
          dot.y += (dot.target[1] - dot.y) * k;
          dot.opacity = Math.min(1, dot.opacity + dt / 150);
        } else dot.opacity = 0; // beyond the tray: the badge counts it
      }
      dot.el.setAttribute("cx", dot.x.toFixed(1));
      dot.el.setAttribute("cy", dot.y.toFixed(1));
      dot.el.setAttribute("opacity", dot.opacity.toFixed(2));
    }
    this.updateBadges(state.waitCounts);
  }

  updateBadges(counts) {
    const L = this.layout;
    for (const [task, n] of Object.entries(counts)) {
      const box = L.boxes[task];
      if (!box) continue;
      let b = this.badges.get(task);
      if (!b) {
        const qc = box.lane === "Lane_QualityControl";
        const rect = sv("rect", { height: BADGE_H, rx: BADGE_H / 2, fill: qc ? "var(--orange)" : "var(--surface)", stroke: "var(--orange)", "stroke-width": 1.2 });
        const text = sv("text", { "text-anchor": "middle", "font-size": TYPE.sm, "font-weight": 700, fill: qc ? "#fff" : "var(--orange-ink)" });
        const g = sv("g", { "data-badge": task }, rect, text);
        this.badgeLayer.append(g);
        b = { g, rect, text, n: -1 };
        this.badges.set(task, b);
      }
      if (b.n !== n) {
        b.n = n;
        // the left end of the task's status strip, in front of its waiting dots
        const w = badgeWidth(n);
        const x = box.strip.x0, cy = box.strip.rows[0];
        b.rect.setAttribute("x", x); b.rect.setAttribute("y", cy - BADGE_H / 2); b.rect.setAttribute("width", w);
        b.text.setAttribute("x", x + w / 2); b.text.setAttribute("y", cy + 0.36 * TYPE.sm);
        b.text.textContent = n;
      }
      b.g.style.display = "";
    }
    for (const [task, b] of this.badges) if (!(task in counts)) { b.g.style.display = "none"; b.n = -1; }
  }

  reset() {
    for (const dot of this.dots.values()) dot.el.remove();
    this.dots.clear();
  }
}

const DOT_STYLE = {
  work: { fill: "var(--teal)", stroke: "#fff", width: 1.3 },
  wait: { fill: "var(--orange)", stroke: "#fff", width: 1.3 },
  park: { fill: "#fff", stroke: "var(--teal)", width: 1.8 },
  live: { fill: "var(--teal-soft)", stroke: "#fff", width: 1.3 },
};

// ---------- counters ----------

function countersBlock() {
  const make = (key, cls) => {
    const dd = el("dd", {});
    return { node: el("div", { class: cls }, el("dt", { text: T.counters[key] }), dd), dd };
  };
  const c = { inProgress: make("in_progress"), waitingQc: make("waiting_qc", "qc"), finished: make("finished"), meanCycle: make("mean_cycle") };
  const node = el("dl", { class: "counters" }, Object.values(c).map((x) => x.node));
  const set = (k) => {
    for (const key of ["inProgress", "waitingQc", "finished"]) c[key].dd.textContent = k[key];
    c.meanCycle.dd.replaceChildren(k.meanCycle == null ? T.counters.none : fmt(k.meanCycle), k.meanCycle == null ? "" : el("span", { class: "unit", text: T.counters.days }));
  };
  return { node, set };
}

// ---------- queue chart ----------

function queueChart(series, now) {
  // series: [{id, name, color, points}]
  const W = 300, H = 54; // plot area only; the tick labels are HTML beside it, so they keep their size
  const host = el("div", {});
  const head = el("h3", {}, T.chart.title);
  if (series.length > 1) for (const s of series) head.append(el("span", { class: "key" }, legendLine(s.color), s.name));
  const svg = sv("svg", { class: "plot", viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", role: "img", "aria-label": T.chart.title });
  const ymax = Math.max(5, ...series.flatMap((s) => s.points.map((p) => p[1])));
  const top = Math.ceil(ymax / 4) * 4;
  const t0 = series[0].points[0][0], t1 = series[0].points.at(-1)[0];
  const x = (t) => ((t - t0) / (t1 - t0)) * W;
  const y = (v) => H - 4 - (v / top) * (H - 10);
  const ticks = el("div", { class: "ticks", "aria-hidden": "true" });
  for (const v of [0, top / 2, top]) {
    svg.append(sv("line", { x1: 0, x2: W, y1: y(v), y2: y(v), stroke: "var(--line)", "stroke-width": 1, "vector-effect": "non-scaling-stroke" }));
    ticks.append(el("span", { style: `top: ${((y(v) / H) * 100).toFixed(1)}%`, text: NUM(0).format(v) }));
  }
  const lines = series.map((s) => {
    const p = sv("polyline", { fill: "none", stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round", "vector-effect": "non-scaling-stroke" });
    svg.append(p);
    return { s, p };
  });
  const cross = sv("line", { y1: 0, y2: H, stroke: "var(--muted)", "stroke-width": 1, "vector-effect": "non-scaling-stroke", visibility: "hidden" });
  const tip = el("span", { class: "tip" });
  svg.append(cross);
  svg.addEventListener("pointermove", (ev) => {
    const rect = svg.getBoundingClientRect();
    const f = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
    const t = t0 + f * (t1 - t0);
    if (t > now.t) { cross.setAttribute("visibility", "hidden"); tip.textContent = ""; return; }
    cross.setAttribute("x1", x(t)); cross.setAttribute("x2", x(t)); cross.setAttribute("visibility", "visible");
    const k = Math.round((t - t0) / (series[0].points[1][0] - t0));
    const month = Math.floor((t - t0) / MONTH) + 1;
    tip.textContent = `${fill(T.chart.tooltip, { month })}: ` + series.map((s) => `${series.length > 1 ? s.name + " " : ""}${s.points[Math.min(k, s.points.length - 1)][1]}`).join(", ");
  });
  svg.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); tip.textContent = ""; });
  head.append(tip);
  host.append(head, el("div", { class: "plot-row" }, svg, ticks));
  const draw = (t) => {
    for (const { s, p } of lines) {
      const pts = s.points.filter((q) => q[0] <= t).map((q) => `${x(q[0]).toFixed(1)},${y(q[1]).toFixed(1)}`);
      p.setAttribute("points", pts.join(" "));
    }
  };
  return { node: host, draw };
}

function legendLine(color) {
  return sv("svg", { width: 16, height: 8, "aria-hidden": "true" }, sv("line", { x1: 1, x2: 15, y1: 4, y2: 4, stroke: color, "stroke-width": 2.5, "stroke-linecap": "round" }));
}
function legendLoop() {
  return sv("svg", { width: 22, height: 8, "aria-hidden": "true" }, sv("line", { x1: 1, x2: 21, y1: 4, y2: 4, stroke: "var(--edge)", "stroke-width": 2, "stroke-dasharray": "5 3" }));
}
function legendDot(style) {
  return sv("svg", { width: 14, height: 14, "aria-hidden": "true" }, sv("circle", { cx: 7, cy: 7, r: 5, fill: style.fill, stroke: style.stroke === "#fff" ? "none" : style.stroke, "stroke-width": style.width }));
}

// ---------- result view ----------

function resultView(results) {
  const f = figures(results);
  const goal = T.result.goal_share;
  const joined = (ids) => ids.join("+");
  const met = f.full.share.ci_low > goal;
  const box = el("section", { class: "panel result", "aria-labelledby": "result-title" });
  box.append(el("h2", { id: "result-title", text: T.result.title }));
  box.append(el("p", { class: "method", text: fill(T.result.method, { replications: f.replications, cases: NUM(0).format(f.cases) }) }));

  const left = el("div", {},
    el("div", { class: "big" },
      el("div", { class: "value", "data-figure": "share", text: pct(f.full.share.value) }),
      el("div", { class: "what", text: T.result.share }),
      el("div", { class: "ci", "data-figure": "share-ci", text: fill(T.result.share_ci, { low: pct(f.full.share.ci_low), high: pct(f.full.share.ci_high) }) })),
    el("div", { class: "big" },
      el("div", { class: "value days", "data-figure": "saving", text: fill(T.result.saving, { days: fmt(f.full.saving.value) }) }),
      el("div", { class: "what", text: T.result.saving_label }),
      el("div", { class: "ci", "data-figure": "saving-ci", text: fill(T.result.saving_ci, { low: fmt(f.full.saving.ci_low), high: fmt(f.full.saving.ci_high) }) })),
    el("div", { class: "goal" }, checkIcon(met), el("span", { text: fill(met ? T.result.goal_met : T.result.goal_missed, { goal: pct(goal, 0) }) })));

  const rows = [
    { key: "as_is", label: T.result.as_is, e: f.asIs.cycleTime, color: "var(--teal-soft)" },
    { key: "full", label: fill(T.result.full, { changes: joined(f.full.changes) }), e: f.full.cycleTime, color: "var(--teal)" },
    { key: "best", label: fill(T.result.best, { changes: joined(f.best.changes) }), e: f.best.cycleTime, color: "var(--orange)" },
  ];
  const right = el("div", {},
    el("div", { class: "chart-block" }, el("h3", { text: T.result.cycle_title }), cycleChart(rows)),
    el("div", { class: "chart-block" }, el("h3", { text: T.result.share_title }), shareChart([
      { key: "full", label: rows[1].label, e: f.full.share, color: "var(--teal)" },
      { key: "best", label: rows[2].label, e: f.best.share, color: "var(--orange)" },
    ], goal)),
    el("p", { class: "fine", "data-figure": "best-note", text: fill(T.result.best_note, { changes: joined(f.best.changes), share: pct(f.best.share.value) }) }),
    el("p", { class: "fine", text: `${T.result.ci_note} ${T.result.sample_vs_official}` }));
  box.append(el("div", { class: "result-grid" }, left, right));
  return box;
}

function checkIcon(ok) {
  return sv("svg", { width: 22, height: 22, viewBox: "0 0 24 24", "aria-hidden": "true" },
    sv("circle", { cx: 12, cy: 12, r: 11, fill: ok ? "var(--teal)" : "var(--orange)" }),
    sv("path", { d: ok ? "M7 12.5l3.2 3.2L17 9" : "M8 8l8 8M16 8l-8 8", fill: "none", stroke: "#fff", "stroke-width": 2.4, "stroke-linecap": "round", "stroke-linejoin": "round" }));
}

function cycleChart(rows) {
  const W = 640, labelW = 190, rowH = 46, H = rows.length * rowH + 22;
  const max = Math.ceil(Math.max(...rows.map((r) => r.e.ci_high)) / 20) * 20 + 20;
  const x = (v) => labelW + (v / max) * (W - labelW - 70);
  const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": T.result.cycle_title });
  for (let v = 0; v <= max; v += 40) {
    svg.append(sv("line", { x1: x(v), x2: x(v), y1: 4, y2: H - 20, stroke: "var(--line)" }));
    svg.append(sv("text", { x: x(v), y: H - 4, "text-anchor": "middle", "font-size": 12, fill: "var(--muted)", text: v }));
  }
  rows.forEach((r, k) => {
    const cy = 8 + k * rowH + 16, bh = 22;
    const g = sv("g", { "data-figure": `cycle-${r.key}` },
      sv("title", { text: `${r.label}: ${fmt(r.e.value)} (${fill(T.result.range, { low: fmt(r.e.ci_low), high: fmt(r.e.ci_high) })})` }),
      sv("text", { x: labelW - 12, y: cy + 5, "text-anchor": "end", "font-size": 15, "font-weight": 600, fill: "var(--ink)", text: r.label }),
      sv("path", { d: `M${x(0)},${cy - bh / 2} H${x(r.e.value) - 4} q4,0 4,4 V${cy + bh / 2 - 4} q0,4 -4,4 H${x(0)} z`, fill: r.color }),
      sv("line", { x1: x(r.e.ci_low), x2: x(r.e.ci_high), y1: cy, y2: cy, stroke: "var(--ink)", "stroke-width": 1.6 }),
      sv("line", { x1: x(r.e.ci_low), x2: x(r.e.ci_low), y1: cy - 6, y2: cy + 6, stroke: "var(--ink)", "stroke-width": 1.6 }),
      sv("line", { x1: x(r.e.ci_high), x2: x(r.e.ci_high), y1: cy - 6, y2: cy + 6, stroke: "var(--ink)", "stroke-width": 1.6 }),
      sv("text", { x: x(r.e.ci_high) + 8, y: cy + 6, "font-size": 17, "font-weight": 700, fill: "var(--ink)", text: fmt(r.e.value) }));
    svg.append(g);
  });
  return svg;
}

function shareChart(rows, goal) {
  const W = 640, labelW = 190, rowH = 40, H = rows.length * rowH + 44;
  const max = Math.max(0.35, Math.ceil(Math.max(...rows.map((r) => r.e.ci_high)) * 20) / 20 + 0.05);
  const x = (v) => labelW + (v / max) * (W - labelW - 70);
  const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": T.result.share_title });
  for (let v = 0; v <= max + 1e-9; v += 0.1) {
    svg.append(sv("line", { x1: x(v), x2: x(v), y1: 22, y2: H - 20, stroke: "var(--line)" }));
    svg.append(sv("text", { x: x(v), y: H - 4, "text-anchor": "middle", "font-size": 12, fill: "var(--muted)", text: pct(v, 0) }));
  }
  svg.append(sv("line", { x1: x(goal), x2: x(goal), y1: 18, y2: H - 20, stroke: "var(--ink)", "stroke-width": 1.6, "stroke-dasharray": "4 3" }));
  svg.append(sv("text", { x: x(goal), y: 13, "text-anchor": "middle", "font-size": 13, "font-weight": 600, fill: "var(--ink)", text: fill(T.result.goal_line, { goal: pct(goal, 0) }) }));
  rows.forEach((r, k) => {
    const cy = 26 + k * rowH + 16;
    svg.append(sv("g", { "data-figure": `share-${r.key}` },
      sv("title", { text: `${r.label}: ${pct(r.e.value)} (${fill(T.result.range, { low: pct(r.e.ci_low), high: pct(r.e.ci_high) })})` }),
      sv("text", { x: labelW - 12, y: cy + 5, "text-anchor": "end", "font-size": 15, "font-weight": 600, fill: "var(--ink)", text: r.label }),
      sv("rect", { x: x(r.e.ci_low), y: cy - 5, width: x(r.e.ci_high) - x(r.e.ci_low), height: 10, rx: 5, fill: r.color, opacity: 0.35 }),
      sv("circle", { cx: x(r.e.value), cy, r: 7, fill: r.color, stroke: "#fff", "stroke-width": 2 }),
      sv("text", { x: x(r.e.ci_high) + 8, y: cy + 6, "font-size": 16, "font-weight": 700, fill: "var(--ink)", text: pct(r.e.value) })));
  });
  return svg;
}

// ---------- app ----------

async function main() {
  const [content, replay, results] = await Promise.all(
    ["demo.vi.json", "replay.json", "../results.json"].map(async (u) => {
      const r = await fetch(u);
      if (!r.ok) throw new Error(`${u}: HTTP ${r.status}`);
      return r.json();
    }));
  T = content;
  const formats = new Map();
  NUM = (d, style = "decimal") => {
    const key = `${d}/${style}`;
    if (!formats.has(key)) formats.set(key, new Intl.NumberFormat(T.lang, { style, minimumFractionDigits: d, maximumFractionDigits: d }));
    return formats.get(key);
  };
  document.documentElement.lang = T.lang;
  document.title = T.title;
  document.getElementById("title").textContent = T.title;
  document.getElementById("subtitle").textContent = `${T.subtitle}.`;
  document.getElementById("report").textContent = T.report_link;
  try { await document.fonts.ready; } catch { /* system font */ }

  const win = replay.window;
  const scen = Object.fromEntries(replay.scenarios.map((s) => [s.id, s]));
  scen.to_be.asIsCapacities = scen.as_is.capacities;
  const preps = Object.fromEntries(replay.scenarios.map((s) => [s.id, prepare(s, win)]));
  const series = Object.fromEntries(replay.scenarios.map((s) => [s.id, qcQueueSeries(preps[s.id], 1)]));
  const COLORS = { as_is: "var(--ink)", to_be: "var(--teal)" };

  const params = new URLSearchParams(location.search);
  const sim = { t: win.start, playing: false, speed: 1, view: params.get("view") ?? "as_is" };
  if (!["as_is", "to_be", "compare", "result"].includes(sim.view)) sim.view = "as_is";
  const at = Number(params.get("at"));
  if (at > 0 && at <= 1) sim.t = win.start + at * (win.end - win.start);

  const stage = document.getElementById("stage");
  const bar = document.getElementById("bar");
  const playBtn = document.getElementById("play");
  const progress = document.getElementById("progress");
  const qchartHost = document.getElementById("qchart");
  let views = []; // {flow: FlowView, counters}
  let chart = null;

  // view switch
  const nav = document.getElementById("views");
  nav.setAttribute("aria-label", T.views.label);
  const viewButtons = ["as_is", "to_be", "compare", "result"].map((v) => {
    const b = el("button", { type: "button", "data-view": v, text: T.views[v] });
    b.addEventListener("click", () => setView(v));
    nav.append(b);
    return b;
  });

  function panel(id, metrics) {
    const s = scen[id];
    const flow = new FlowView(s, preps[id], buildLayout(id, metrics));
    const counters = countersBlock();
    const scroller = el("div", { class: "flow-scroll" }, flow.svg);
    const wrapNode = el("div", { class: "flow-wrap" }, scroller);
    // Narrow screens: fade the side that has more of the flow.
    const cue = () => {
      const more = [];
      if (scroller.scrollLeft > 2) more.push("left");
      if (scroller.scrollLeft + scroller.clientWidth < scroller.scrollWidth - 2) more.push("right");
      wrapNode.dataset.more = more.join(" ");
    };
    scroller.addEventListener("scroll", cue, { passive: true });
    new ResizeObserver(cue).observe(scroller);
    const node = el("section", { class: "panel", "data-scenario": id, "aria-label": s.name },
      el("div", { class: "panel-head" }, el("h2", { text: s.name }), counters.node),
      wrapNode, el("p", { class: "scroll-hint", text: T.scroll_hint }));
    return { id, flow, counters, node };
  }

  function legend() {
    const items = [["work", T.legend.work], ["wait", T.legend.wait], ["live", T.legend.live]];
    if (sim.view !== "as_is") items.splice(2, 0, ["park", T.legend.park]);
    return el("div", {},
      el("ul", { class: "legend" }, items.map(([k, label]) => el("li", {}, legendDot(DOT_STYLE[k]), label)),
        el("li", {}, legendLoop(), T.loops_note)),
      el("p", { class: "note", "data-note": "sample", text: fill(T.sample_note, { seed: replay.seed, months: clock(win, win.end).totalMonths }) }));
  }

  function changesList() {
    const caps = scen.to_be.capacities, before = scen.as_is.capacities;
    const qc = "Lane_QualityControl";
    return el("ul", { class: "changes" }, scen.to_be.changes.map((c) => el("li", {},
      el("span", { class: "chip", text: c }), el("b", { text: T.changes[c].name }),
      el("span", { text: fill(T.changes[c].detail, { from: before[qc], to: caps[qc] }) }))));
  }

  function setView(v) {
    sim.view = v;
    viewButtons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.view === v)));
    const url = new URL(location.href);
    url.searchParams.set("view", v);
    url.searchParams.delete("at");
    history.replaceState(null, "", url);
    for (const x of views) x.flow.reset();
    views = [];
    stage.replaceChildren();
    stage.classList.toggle("compare", v === "compare");
    document.body.classList.toggle("compare", v === "compare");
    if (v === "result") {
      sim.playing = false;
      bar.hidden = true;
      stage.append(resultView(results));
      return;
    }
    bar.hidden = false;
    const ids = v === "compare" ? ["as_is", "to_be"] : [v];
    views = ids.map((id) => panel(id, v === "compare" ? "compact" : "normal"));
    for (const x of views) stage.append(x.node);
    const below = el("div", { class: "below" });
    if (v === "to_be") below.append(changesList());
    below.append(legend());
    if (v === "compare") stage.append(el("div", { class: "panel" }, below));
    else views[0].node.append(below);
    chart = queueChart(ids.map((id) => ({ id, name: scen[id].name, color: COLORS[id], points: series[id] })), sim);
    qchartHost.replaceChildren(chart.node);
    render(performance.now(), 1000);
  }

  // transport
  const speedHost = document.getElementById("speed");
  document.getElementById("speed-label").textContent = T.controls.speed;
  const speedButtons = SPEEDS.map((s) => {
    const b = el("button", { type: "button", "aria-pressed": String(s === sim.speed), text: `${NUM(s % 1 ? 1 : 0).format(s)}×` });
    b.addEventListener("click", () => { sim.speed = s; speedButtons.forEach((x, k) => x.setAttribute("aria-pressed", String(SPEEDS[k] === s))); });
    speedHost.append(b);
    return b;
  });
  progress.setAttribute("aria-label", T.controls.progress);
  progress.addEventListener("input", () => {
    sim.t = win.start + (progress.value / 1000) * (win.end - win.start);
    for (const x of views) x.flow.reset();
    render(performance.now(), 1000);
  });
  playBtn.addEventListener("click", togglePlay);
  addEventListener("keydown", (ev) => {
    if (ev.target.closest?.("input, textarea")) return;
    if (ev.code === "Space" && sim.view !== "result") { ev.preventDefault(); togglePlay(); }
    const k = Number(ev.key);
    if (k >= 1 && k <= 4) setView(["as_is", "to_be", "compare", "result"][k - 1]);
  });

  function togglePlay() {
    if (sim.t >= win.end) { sim.t = win.start; for (const x of views) x.flow.reset(); }
    sim.playing = !sim.playing;
    updateButton();
  }
  function updateButton() {
    const label = sim.playing ? T.controls.pause : sim.t >= win.end ? T.controls.restart : sim.t > win.start ? T.controls.resume : T.controls.play;
    const icon = sim.playing ? "M3 2h4v12H3zM9 2h4v12H9z" : sim.t >= win.end ? "M8 2a6 6 0 1 0 6 6h-2a4 4 0 1 1-4-4v3l4-4-4-4z" : "M3 1.5v13l11-6.5z";
    if (playBtn.dataset.label !== label) {
      playBtn.dataset.label = label;
      playBtn.replaceChildren(sv("svg", { viewBox: "0 0 16 16", "aria-hidden": "true" }, sv("path", { d: icon })), label);
    }
  }

  const clockEl = document.getElementById("clock"), dayEl = document.getElementById("day");
  function render(now, dt) {
    const c = clock(win, sim.t);
    clockEl.textContent = fill(T.controls.clock, { month: c.month, total: c.totalMonths });
    dayEl.textContent = fill(T.controls.day, { day: c.day, total: c.totalDays });
    if (document.activeElement !== progress) progress.value = Math.round(c.progress * 1000);
    for (const x of views) {
      const state = stateAt(x.flow.prep, sim.t);
      x.flow.update(state, now, dt);
      x.counters.set(state.counters);
    }
    chart?.draw(sim.t);
    updateButton();
  }

  let last = performance.now();
  function frame(now) {
    const dt = Math.min(100, now - last);
    last = now;
    if (sim.playing) {
      sim.t = Math.min(win.end, sim.t + (dt / 1000) * DAYS_PER_SECOND * sim.speed);
      if (sim.t >= win.end) sim.playing = false;
    }
    if (views.length) render(now, dt);
    requestAnimationFrame(frame);
  }

  setView(sim.view);
  requestAnimationFrame(frame);
  // For the browser checks: read the clock and the counters the page shows.
  window.demo = { sim, win, figures: () => figures(results), state: (id) => stateAt(preps[id], sim.t), setView, togglePlay };
}

main().catch((err) => {
  console.error(err);
  const msg = T?.error ? fill(T.error, { error: err.message }) : `${err.name}: ${err.message}`;
  document.getElementById("stage").replaceChildren(el("p", { class: "error", text: msg }));
});
