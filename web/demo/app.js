// Flow demo, one page in six steps: the as-is model in BPMN, its graphs (paths, the handover
// network between departments with betweenness, graph2vec vectors), the k-means groups, the replay of the sample run from replay.json for
// as-is and to-be, and the official results. Groups and results come from ../results.json. Text comes from demo.vi.json.
import { buildLayout, dotPosition, parkPosition, route, HEADER, POOL_W, LANES, TYPE, SPACE, GW, EV, CHIP } from "./layout.js";
import { prepare, stateAt, qcQueueSeries, clock, along, rest, MONTH } from "./state.js";
import { figures } from "./figures.js";
import { caseGroups, overallDays, casePoints, findings } from "./groups.js";

const SVG = "http://www.w3.org/2000/svg";
const DAYS_PER_SECOND = 6.25; // 1x: the 375-day window in 60 s, a month in about 3.3 s
const SPEEDS = [0.5, 1, 2, 4];
const TRAVEL_MS = 520;
const FADE_MS = 260;
// The talk, in order. Steps 4 and 5 replay the sample run; the others are still.
const STEPS = ["bpmn", "embed", "kmeans", "sim_as_is", "sim_to_be", "result"];
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

let T; // content
let NUM;
const fill = (s, vars = {}) => s.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? vars[k] : `{${k}}`));
const fmt = (v, d = 1) => NUM(d).format(v);
const pct = (v, d = 1) => NUM(d, "percent").format(v);
const lines = (s) => s.split("\n");
const oneLine = (s) => s.replace(/\n/g, " ");

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

const ctx = document.createElement("canvas").getContext("2d");
const textWidth = (text, size, weight) => {
  ctx.font = `${weight} ${size}px "Be Vietnam Pro", system-ui, sans-serif`;
  return ctx.measureText(text).width;
};
// First baseline of a text block whose glyph box starts at `top`.
const baseline = (top) => top + TYPE.ascent * TYPE.size;
const S = TYPE.size;

// ---------- BPMN shapes (Dumas et al., ch. 3), also used for the legend ----------

const shape = {
  start: (cx, cy, r = EV) => sv("circle", { cx, cy, r, fill: "var(--surface)", stroke: "var(--ink)", "stroke-width": 1.5 }),
  end: (cx, cy, r = EV) => sv("circle", { cx, cy, r: r - 1.2, fill: "var(--surface)", stroke: "var(--ink)", "stroke-width": 3.4 }),
  gateway(cx, cy, kind, r = GW) {
    const k = kind === "parallelGateway" ? 0.5 * r : 0.34 * r;
    const marker = kind === "parallelGateway"
      ? `M${cx - k},${cy} H${cx + k} M${cx},${cy - k} V${cy + k}`
      : `M${cx - k},${cy - k} L${cx + k},${cy + k} M${cx + k},${cy - k} L${cx - k},${cy + k}`;
    return sv("g", {},
      sv("path", { d: `M${cx},${cy - r} L${cx + r},${cy} L${cx},${cy + r} L${cx - r},${cy} Z`, fill: "var(--surface)", stroke: "var(--ink)", "stroke-width": 1.5, "stroke-linejoin": "round" }),
      sv("path", { d: marker, stroke: "var(--ink)", "stroke-width": 2.4, "stroke-linecap": "round", fill: "none" }));
  },
  task: (x, y, w, h, extra = {}) => sv("rect", { x, y, width: w, height: h, rx: 8, fill: "var(--surface)", stroke: "var(--task)", "stroke-width": 1.3, ...extra }),
};

function arrowMarker(id, color) {
  return sv("marker", { id, viewBox: "0 0 10 10", refX: 9.5, refY: 5, markerWidth: 6.5, markerHeight: 6.5, markerUnits: "userSpaceOnUse", orient: "auto" },
    sv("path", { d: "M0,0.8 L10,5 L0,9.2 z", fill: color }));
}

// Orthogonal path with slightly rounded corners.
function roundedPath(pts, r = 4) {
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

// ---------- the flow drawing ----------

const HOT = new Set(["Flow_DefectsFound", "Flow_DefectsFixed"]); // as-is: the rework loop through all four checks

function drawFlow(layout, scenario) {
  const { width, height, lanes, nodes, flows, frames, metrics: m } = layout;
  const svg = sv("svg", { class: "flow", viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": scenario.name, preserveAspectRatio: "xMidYMid meet" });
  const uid = `${scenario.id}-${m.name}`;
  svg.append(sv("defs", {}, arrowMarker(`arrow-${uid}`, "var(--flow)"), arrowMarker(`arrow-hot-${uid}`, "var(--orange)")));
  const laneFill = (id) => (LANES.indexOf(id) % 2 ? "var(--lane-alt)" : "var(--lane)");
  const laneAt = (y) => LANES.find((id) => y >= lanes[id].top && y < lanes[id].bottom) ?? LANES[0];
  // A label on the flow: one text per line, left-aligned at the layout's spot, with a halo in the colour of
  // the lane under it so a line passing close by never runs into the letters.
  const textBlock = (text, at, attrs) => {
    const g = sv("g", attrs);
    lines(text).forEach((line, k) => {
      const y = at.y + k * S * TYPE.line;
      g.append(sv("text", {
        x: at.x, y, "font-size": S, "font-weight": 600, fill: attrs.fill,
        stroke: laneFill(laneAt(y - 5)), "stroke-width": 4, "stroke-linejoin": "round", "paint-order": "stroke", text: line,
      }));
    });
    return g;
  };

  // the pool (one organisation) with one lane per department
  for (const id of LANES) {
    const L = lanes[id];
    svg.append(sv("rect", { x: POOL_W, y: L.top, width: width - POOL_W, height: L.h, fill: laneFill(id), "data-lane-bg": id }));
    if (L.top > 0) svg.append(sv("line", { x1: POOL_W, x2: width, y1: L.top, y2: L.top, stroke: "var(--line)" }));
  }
  svg.append(sv("rect", { x: 0, y: 0, width: POOL_W, height, fill: "var(--pool)" }));
  svg.append(sv("text", { x: POOL_W / 2 + 0.36 * TYPE.pool, y: height / 2, transform: `rotate(-90 ${POOL_W / 2 + 0.36 * TYPE.pool} ${height / 2})`, "text-anchor": "middle", "font-size": TYPE.pool, "font-weight": 700, fill: "var(--ink)", text: T.pool, "data-pool": "" }));
  svg.append(sv("line", { x1: POOL_W, x2: POOL_W, y1: 0, y2: height, stroke: "var(--line-strong)" }));
  svg.append(sv("line", { x1: HEADER, x2: HEADER, y1: 0, y2: height, stroke: "var(--line)" }));
  svg.append(sv("rect", { x: 0.5, y: 0.5, width: width - 1, height: height - 1, fill: "none", stroke: "var(--line-strong)" }));

  // lane names, then the head count (and C4 in the to-be QC lane)
  const caps = scenario.capacities, asIsCaps = scenario.asIsCapacities;
  const laneX = POOL_W + SPACE.m;
  for (const id of LANES) {
    const L = lanes[id];
    const g = sv("g", { "data-lane": id });
    const y0 = baseline(L.top + m.laneTop + SPACE.xs);
    const name = lines(T.lanes[id]);
    name.forEach((line, k) => g.append(sv("text", { x: laneX, y: y0 + k * S * TYPE.line, "font-size": S, "font-weight": 700, fill: "var(--ink)", text: line })));
    const py = y0 + name.length * S * TYPE.line;
    const changed = asIsCaps && asIsCaps[id] !== caps[id];
    g.append(sv("text", { x: laneX, y: py, "font-size": S, "font-weight": changed ? 700 : 400, fill: changed ? "var(--orange-ink)" : "var(--muted)", text: fill(T.people, { n: caps[id] }) }));
    if (changed) {
      const cy = py + TYPE.descent * S + SPACE.s;
      g.append(chipSvg("C4", laneX, cy));
      g.append(sv("text", { x: laneX + CHIP.w + SPACE.s, y: cy + CHIP.h / 2 + 0.36 * S, "font-size": S, "font-weight": 600, fill: "var(--orange-ink)", text: fill(T.people_added, { n: caps[id] - asIsCaps[id] }) }));
    }
    svg.append(g);
  }

  // highlight frames: the bottleneck (as-is) or C1 (to-be) around the checks, and the part after go-live
  for (const f of frames) {
    if (f.kind === "golive") {
      svg.append(sv("rect", { x: f.x, y: f.y, width: f.w, height: f.h, rx: 10, fill: "var(--teal-wash)", stroke: "var(--teal)", "stroke-width": 1.2, "data-band": "golive" }));
      const ty = baseline(f.y + m.laneTop / 2 + SPACE.xs);
      svg.append(sv("text", { x: f.x + SPACE.m, y: ty, "font-size": S, "font-weight": 700, fill: "var(--teal)", text: T.golive.title }));
      svg.append(sv("text", { x: f.x + SPACE.m, y: ty + S * TYPE.line, "font-size": S, fill: "var(--muted)", text: T.golive.note }));
      continue;
    }
    svg.append(sv("rect", { x: f.x, y: f.y, width: f.w, height: f.h, rx: 10, fill: "var(--orange-soft)", stroke: "var(--orange)", "stroke-width": 1.2, "data-band": f.kind }));
    const [lx, ly] = f.label;
    if (f.kind === "change") {
      const text = T.changes[f.change].detail;
      const x0 = lx - (CHIP.w + SPACE.m + textWidth(text, S, 600)) / 2;
      svg.append(chipSvg(f.change, x0, ly - TYPE.ascent * S + 1));
      svg.append(sv("text", { x: x0 + CHIP.w + SPACE.m, y: ly, "font-size": S, "font-weight": 600, fill: "var(--orange-ink)", text }));
    } else {
      svg.append(sv("text", { x: lx, y: ly, "text-anchor": "middle", "font-size": S, "font-weight": 600, fill: "var(--orange-ink)", text: T.bottleneck }));
    }
  }

  // sequence flows: solid arrows; the conditions of XOR-split arcs beside them
  const rates = Object.fromEntries(scenario.rework.map((r) => [r.gateway_id, r.rate]));
  const flowLayer = sv("g", { fill: "none" });
  const labelLayer = sv("g", {});
  for (const f of Object.values(flows)) {
    const hot = scenario.id === "as_is" && HOT.has(f.id);
    flowLayer.append(sv("path", {
      d: roundedPath(f.pts), "data-flow": f.id,
      stroke: hot ? "var(--orange)" : "var(--flow)", "stroke-width": hot ? 2 : 1.5,
      "marker-end": `url(#${hot ? "arrow-hot" : "arrow"}-${uid})`,
    }));
    if (f.label) {
      const text = fill(T.conditions[f.id], { rate: rates[f.source] != null ? pct(rates[f.source], 0) : "" });
      // a two-line condition breaks before the rate in brackets
      const split = f.label.lines === 2 ? text.replace(" (", "\n(") : text;
      labelLayer.append(textBlock(split, f.label, { "data-cond": f.id, fill: hot ? "var(--orange-ink)" : "var(--ink)" }));
    }
  }
  svg.append(flowLayer);

  // events, gateways and tasks
  const goLive = layout.goLive;
  for (const n of Object.values(nodes)) {
    const title = sv("title", { text: n.type === "task" ? oneLine(T.activities[n.id]) : n.type.endsWith("Gateway") ? T.gateways[n.type] : oneLine(T.events[n.id]) });
    if (n.type === "startEvent") { svg.append(sv("g", { "data-node": n.id }, title, shape.start(n.cx, n.cy))); continue; }
    if (n.type === "endEvent") { svg.append(sv("g", { "data-node": n.id }, title, shape.end(n.cx, n.cy))); continue; }
    if (n.type.endsWith("Gateway")) { svg.append(sv("g", { "data-node": n.id, "data-gateway": n.type }, title, shape.gateway(n.cx, n.cy, n.type))); continue; }
    const change = layout.changed[n.id];
    const after = n.cx > goLive;
    const g = sv("g", { "data-box-group": n.id, "data-node": n.id }, title);
    g.append(shape.task(n.left, n.top, n.w, m.boxH, {
      "data-box": n.id, fill: change === "C2" ? "var(--orange-soft)" : "var(--surface)",
      stroke: change ? "var(--orange)" : "var(--task)", "stroke-width": change ? 2 : 1.3,
    }));
    const label = lines(T.activities[n.id]);
    const lh = S * TYPE.line;
    const blockH = (TYPE.ascent + TYPE.descent) * S + (label.length - 1) * lh;
    const y0 = baseline(n.top + m.labelTop + (m.labelH - blockH) / 2);
    const lg = sv("g", { "data-label": n.id });
    label.forEach((line, k) => lg.append(sv("text", { x: n.cx, y: y0 + k * lh, "text-anchor": "middle", "font-size": S, "font-weight": 600, fill: after ? "var(--muted)" : "var(--ink)", text: line })));
    g.append(lg);
    if (change) g.append(chipSvg(change, n.chip.x, n.chip.y));
    svg.append(g);
  }
  // event names, beside each start and end event (Dumas et al., §5.4.3)
  for (const n of Object.values(nodes)) if (n.label) labelLayer.append(textBlock(T.events[n.id], n.label, { "data-event-label": n.id, fill: "var(--ink)" }));
  svg.append(labelLayer);

  const dynamic = sv("g", {});
  svg.append(dynamic);
  return { svg, dynamic };
}

function chipSvg(text, x, y) {
  return sv("g", { "data-chip": text },
    sv("rect", { x, y, width: CHIP.w, height: CHIP.h, rx: 5, fill: "var(--orange)" }),
    sv("text", { x: x + CHIP.w / 2, y: y + CHIP.h / 2 + 0.36 * S, "text-anchor": "middle", "font-size": S, "font-weight": 700, fill: "#fff", text }));
}

// ---------- one animated flow ----------

// Each dot is a token (Dumas et al., §3.1): one project. It is created at the start event, moves
// along the arcs and through the gateways, sits on a task while it waits or is worked on, and is
// destroyed at an end event. At the to-be AND-split it splits into four; at the AND-join they merge.
class FlowView {
  constructor(scenario, prep, layout) {
    this.scenario = scenario;
    this.prep = prep;
    this.layout = layout;
    const { svg, dynamic } = drawFlow(layout, scenario);
    this.svg = svg;
    this.layer = dynamic;
    this.dots = new Map(); // row index -> dot
    this.routes = new Map();
    this.start = Object.values(layout.nodes).find((n) => n.type === "startEvent");
  }

  route(from, to) {
    const key = `${from}>${to}`;
    if (!this.routes.has(key)) this.routes.set(key, route(this.layout, from, to));
    return this.routes.get(key);
  }

  path(from, to) {
    return this.route(from, to)?.pts ?? null;
  }

  update(state, now, dt) {
    const L = this.layout;
    const r = L.metrics.dot;
    const seen = new Set();
    // parked dots of all four checks share the arc into the AND-join, oldest nearest the gateway
    const parked = state.items.filter((x) => x.mode === "park").sort((a, b) => this.prep.rows[a.i].end - this.prep.rows[b.i].end || a.i - b.i);
    const parkSlot = new Map(parked.map((x, k) => [x.i, k]));
    for (const item of state.items) {
      const waiting = state.waitCounts[item.task] ?? 0, total = waiting + (state.workCounts[item.task] ?? 0);
      const target = item.mode === "park" ? parkPosition(L, item.task, parkSlot.get(item.i))
        : dotPosition(L, item.task, item.mode === "wait" ? item.slot : waiting + item.slot, total);
      seen.add(item.i);
      let dot = this.dots.get(item.i);
      if (!dot) {
        const prevDot = item.prev != null ? this.dots.get(item.prev) : null;
        const prevRow = item.prev != null ? this.prep.rows[item.prev] : null;
        let pts = null;
        if (prevRow && prevDot) {
          const r0 = this.route(prevRow.activity, item.task);
          const lead = here(prevDot); // a dot still on its way finishes that path first
          if (r0 && prevDot.mode === "park") pts = [...lead, ...r0.pts.slice(this.layout.flows[r0.flows[0]].pts.length - 1)];
          else if (r0) pts = [...lead.slice(0, -1), ...leave(L.boxes[prevRow.activity], lead.at(-1), r0.pts)];
        } else if (!prevRow && item.task === "Task_RegisterRequest") pts = this.path(this.start.id, item.task);
        if (pts && target) pts = enter(L.boxes[item.task], pts, target);
        const node = sv("circle", { r, class: "dot" });
        const start = pts?.[0] ?? target ?? [0, 0];
        dot = { el: node, x: start[0], y: start[1], opacity: pts ? 1 : 0, travel: null, mode: null, task: item.task, last: item.last };
        if (pts && !REDUCED) dot.travel = { pts, t0: now };
        this.layer.append(node);
        this.dots.set(item.i, dot);
        if (prevDot) prevDot.claimed = true;
      }
      // a check that finished first runs down its arc to wait just before the AND-join
      if (item.mode === "park" && dot.mode && dot.mode !== "park" && target && !REDUCED) {
        const f = this.joinFlow(item.task);
        const lead = here(dot);
        dot.travel = { pts: [...lead.slice(0, -1), ...leave(L.boxes[item.task], lead.at(-1), [...f.pts.slice(0, -1), target])], t0: now };
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
      if (dot.gone == null) {
        dot.gone = now;
        // the last task of a project: the token runs on to its end event; a parked check merges into the join
        const lead = here(dot);
        let pts = null;
        if (dot.mode === "park") {
          const f = this.joinFlow(dot.task), j = L.nodes[f.target];
          pts = [...lead, f.pts.at(-1), [j.cx, j.cy]];
        } else if (dot.last) {
          const exit = this.path(dot.task, null);
          if (exit) pts = [...lead.slice(0, -1), ...leave(L.boxes[dot.task], lead.at(-1), exit)];
        }
        if (pts) { dot.travel = { pts, t0: now }; dot.gone = now + TRAVEL_MS; }
      }
    }
    for (const [i, dot] of this.dots) {
      if (dot.travel) {
        const f = (now - dot.travel.t0) / TRAVEL_MS;
        if (f >= 1) { [dot.x, dot.y] = dot.travel.pts.at(-1); dot.travel = null; }
        else {
          const e = f < 0.5 ? 2 * f * f : 1 - (-2 * f + 2) ** 2 / 2;
          dot.travel.e = e;
          [dot.x, dot.y] = along(dot.travel.pts, e);
        }
        dot.opacity = Math.min(1, dot.opacity + dt / 150);
      }
      if (dot.gone != null && now >= dot.gone) {
        const f = (now - dot.gone) / FADE_MS;
        if (f >= 1) { dot.el.remove(); this.dots.delete(i); continue; }
        dot.opacity = 1 - f;
      } else if (!dot.travel && dot.gone == null && dot.target) {
        const k = REDUCED ? 1 : 1 - Math.exp(-dt / 90);
        dot.x += (dot.target[0] - dot.x) * k;
        dot.y += (dot.target[1] - dot.y) * k;
        dot.opacity = Math.min(1, dot.opacity + dt / 150);
      }
      dot.el.setAttribute("cx", dot.x.toFixed(1));
      dot.el.setAttribute("cy", dot.y.toFixed(1));
      dot.el.setAttribute("opacity", dot.opacity.toFixed(2));
    }
  }

  joinFlow(task) {
    return Object.values(this.layout.flows).find((fl) => fl.source === task && this.layout.nodes[fl.target]?.type === "parallelGateway");
  }

  reset() {
    for (const dot of this.dots.values()) dot.el.remove();
    this.dots.clear();
  }
}

// The rest of a dot's current path, from where it is now (just its position if it is not moving).
function here(dot) {
  return dot.travel ? rest(dot.travel.pts, dot.travel.e ?? 0) : [[dot.x, dot.y]];
}

// Into a task: from the end of `pts` (on the box edge) to the dot's place `s` in the strip, and out
// of it again. The dot goes round the outside of the box, so it never crosses the task's label.
const OUT = 5;
function edge(box, p) {
  if (Math.abs(p[1] - box.bottom) < 0.5) return "bottom";
  if (Math.abs(p[1] - box.top) < 0.5) return "top";
  return p[0] < box.cx ? "left" : "right";
}
function enter(box, pts, s) {
  if (!box) return [...pts, s];
  const p = pts.at(-1), side = edge(box, p);
  const ox = (side === "top" ? p[0] < box.cx : side === "left") ? box.left - OUT : box.right + OUT;
  if (side === "bottom") return [...pts, [p[0], box.bottom + OUT], [s[0], box.bottom + OUT], s];
  if (side === "top") return [...pts.slice(0, -1), [p[0], box.top - 2], [ox, box.top - 2], [ox, s[1]], s];
  return [...pts, [ox, p[1]], [ox, s[1]], s];
}
function leave(box, s, pts) {
  if (!box) return [s, ...pts];
  const way = enter(box, [pts[0]], s); // the same way round, backwards
  return [...way.reverse(), ...pts.slice(1)];
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
function legendDot(style) {
  return sv("svg", { width: 14, height: 14, "aria-hidden": "true" }, sv("circle", { cx: 7, cy: 7, r: 5, fill: style.fill, stroke: style.stroke === "#fff" ? "none" : style.stroke, "stroke-width": style.width }));
}
// Small samples of the BPMN shapes the flow uses, drawn with the same code as the flow.
function legendShape(kind) {
  const box = (w, ...kids) => sv("svg", { width: w, height: 22, viewBox: `0 0 ${w} 22`, "aria-hidden": "true" }, ...kids);
  if (kind === "start") return box(22, shape.start(11, 11, 8));
  if (kind === "end") return box(22, shape.end(11, 11, 8));
  if (kind === "task") return box(30, shape.task(1, 3, 28, 16, { rx: 5 }));
  if (kind === "xor") return box(24, shape.gateway(12, 11, "exclusiveGateway", 10));
  if (kind === "and") return box(24, shape.gateway(12, 11, "parallelGateway", 10));
  return box(30, sv("defs", {}, arrowMarker("legend-arrow", "var(--flow)")),
    sv("path", { d: "M1,11 H28", stroke: "var(--flow)", "stroke-width": 1.5, "marker-end": "url(#legend-arrow)" }));
}

// ---------- steps 1 to 3: the model, the embeddings, the groups ----------

/** A still flow (no tokens) in its scroll wrapper. tint(svg) may recolour its boxes. */
function stillFlow(scenario, tint) {
  const { svg } = drawFlow(buildLayout(scenario.id, "normal"), scenario);
  if (tint) tint(svg);
  return [el("div", { class: "flow-wrap" }, el("div", { class: "flow-scroll" }, svg)), el("p", { class: "scroll-hint", text: T.scroll_hint })];
}

function notationLegend(kinds) {
  return el("ul", { class: "legend", "data-legend": "notation" }, kinds.map((k) => el("li", {}, legendShape(k), T.legend[k])));
}

/** The model's XML with the Vietnamese names of the content file, so bpmn.io shows the same words as the rest of the demo. */
function vietnameseBpmn(xml, rework) {
  const doc = new DOMParser().parseFromString(xml, "application/xml");
  const rates = Object.fromEntries(rework.map((r) => [r.gateway_id, r.rate]));
  for (const node of doc.querySelectorAll("[id]")) {
    const id = node.getAttribute("id");
    let name = T.activities[id] ?? T.events[id] ?? T.lanes[id];
    if (T.conditions[id]) {
      const rate = rates[node.getAttribute("sourceRef")];
      name = fill(T.conditions[id], { rate: rate == null ? "" : pct(rate, 0) });
    }
    if (node.localName === "participant") name = T.pool;
    if (name != null) node.setAttribute("name", oneLine(name));
  }
  return new XMLSerializer().serializeToString(doc);
}

/** Step 1: the as-is model as bpmn.io draws it from models/as_is.bpmn, before anything runs. */
function bpmnView(asIs, xml) {
  const B = T.bpmn;
  const canvas = el("div", { class: "bpmn-canvas", role: "img", "aria-label": B.title });
  // bpmn.io needs the canvas on the page to fit the diagram, so draw on the next frame
  requestAnimationFrame(async () => {
    try {
      const viewer = new BpmnJS({ container: canvas });
      await viewer.importXML(vietnameseBpmn(xml, asIs.rework));
      // as tall as the diagram is at full width, so no empty band under it
      const c = viewer.get("canvas"), inner = c.viewbox().inner;
      canvas.style.height = `${Math.ceil((canvas.clientWidth * inner.height) / inner.width) + 24}px`;
      c.resized();
      c.zoom("fit-viewport", "auto");
    } catch (err) {
      canvas.replaceChildren(el("p", { class: "error", text: fill(T.error, { error: err.message }) }));
    }
  });
  return [el("section", { class: "panel", "aria-labelledby": "bpmn-title" },
    el("div", { class: "panel-head" }, el("h2", { id: "bpmn-title", text: B.title })),
    canvas,
    el("div", { class: "below" }, el("div", { class: "legend-block" },
      el("p", { class: "note", text: `${B.note} ${T.legend.share}` }))))];
}

/** Display name of a node of the as-is model: a task, an event, or a gateway named after the task before it. */
function nodeName(id) {
  if (T.activities[id]) return oneLine(T.activities[id]);
  if (T.events[id]) return oneLine(T.events[id]);
  const into = Object.values(buildLayout("as_is", "normal").flows).find((f) => f.target === id);
  return fill(T.embed.gateway_after, { task: into && T.activities[into.source] ? oneLine(T.activities[into.source]) : id });
}

// A rework arc is one whose condition shows the rework share.
const isLoop = (flowId) => (T.conditions[flowId] ?? "").includes("{rate}");
const condition = (flowId) => (T.conditions[flowId] ?? flowId).replace(/\s*\(\{rate\}\)/, "");

/** A 2D map of vectors. points: {x, y, cls?, title?, label?}. */
function vectorMap(points, { width = 460, height = 330, labels = false } = {}) {
  const pad = labels ? 14 : 10;
  const xs = points.map((p) => p.x), ys = points.map((p) => p.y);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const right = labels ? 150 : 0; // room for the labels of the rightmost dots
  const px = (x) => pad + ((x - x0) / (x1 - x0 || 1)) * (width - 2 * pad - right);
  const py = (y) => height - pad - ((y - y0) / (y1 - y0 || 1)) * (height - 2 * pad);
  const svg = sv("svg", { class: "vector-map", viewBox: `0 0 ${width} ${height}`, role: "img" });
  // Each label tries right, left, above and below its dot, and takes the first spot that hits no label or dot.
  const placed = points.map((p) => ({ x: px(p.x) - 5, y: py(p.y) - 5, w: 10, h: 10 }));
  const hits = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
  const free = (box, self) => box.x >= 0 && box.x + box.w <= width && box.y >= 0 && box.y + box.h <= height
    && placed.every((o, i) => i === self || !hits(box, o));
  const dots = points.map((p, i) => {
    const g = sv("g", { class: p.cls ?? "" }, p.title ? sv("title", { text: p.title }) : null,
      sv("circle", { cx: px(p.x).toFixed(1), cy: py(p.y).toFixed(1), r: labels ? 4.5 : 2.6 }));
    if (labels && p.label) {
      const w = textWidth(p.label, 12, 500) + 2, h = 14, cx = px(p.x), cy = py(p.y);
      const spots = [[cx + 8, cy - h / 2], [cx - 8 - w, cy - h / 2], [cx - w / 2, cy - 8 - h], [cx - w / 2, cy + 8],
        [cx + 8, cy - h - 4], [cx + 8, cy + 4], [cx - 8 - w, cy - h - 4], [cx - 8 - w, cy + 4]];
      const spot = spots.map(([x, y]) => ({ x, y, w, h })).find((b) => free(b, -1)) ?? { x: cx + 8, y: cy - h / 2, w, h };
      placed.push(spot);
      g.append(sv("text", { x: spot.x.toFixed(1), y: (spot.y + 11).toFixed(1), "font-size": 12, "font-weight": 500, fill: "var(--ink)", text: p.label }));
    }
    svg.append(g);
    return g;
  });
  return { svg, dots };
}

/** One path as graph2vec reads it: a chain of BPMN nodes, wrapped onto rows, with the branch taken at each gateway. */
function chainSvg(labels) {
  const W = 1180, boxW = 88, boxH = 42, rowH = 104, gap = 22;
  const items = labels.map((label) => {
    const [id, flow] = label.split(">");
    const kind = flow ? "gateway" : id.startsWith("Start_") ? "start" : id.startsWith("End_") ? "end" : "task";
    const w = kind === "task" ? boxW : kind === "gateway" ? 2 * GW : 2 * EV;
    const out = flow ? Math.max(gap, textWidth(condition(flow), 11, 600) + 14) : gap; // room for the condition on the arc after a gateway
    return { id, flow, kind, w, out };
  });
  let x = 12, row = 0;
  for (const it of items) {
    if (x + it.w > W - 12) { x = 12; row += 1; }
    it.x = x; it.cy = 30 + row * rowH;
    x += it.w + it.out;
  }
  const H = 30 + row * rowH + 44;
  const svg = sv("svg", { class: "chain", viewBox: `0 0 ${W} ${H}`, role: "img" },
    sv("defs", {}, arrowMarker("chain-arrow", "var(--flow)"), arrowMarker("chain-arrow-hot", "var(--orange)")));
  items.forEach((it, k) => {
    const next = items[k + 1];
    if (next) {
      const hot = it.flow && isLoop(it.flow);
      const stroke = hot ? "var(--orange)" : "var(--flow)";
      const marker = `url(#${hot ? "chain-arrow-hot" : "chain-arrow"})`;
      const d = next.cy === it.cy
        ? `M${it.x + it.w},${it.cy} H${next.x - 1}`
        : `M${it.x + it.w / 2},${it.cy + (it.kind === "task" ? boxH / 2 : it.w / 2)} V${it.cy + rowH / 2} H${next.x - 10} V${next.cy} H${next.x - 1}`;
      svg.append(sv("path", { d, fill: "none", stroke, "stroke-width": hot ? 2 : 1.5, "marker-end": marker }));
      if (it.flow) {
        const same = next.cy === it.cy;
        svg.append(sv("text", {
          x: same ? it.x + it.w + 6 : it.x + it.w / 2 - 6, y: same ? it.cy - 7 : it.cy + it.w / 2 + 14,
          "text-anchor": same ? "start" : "end", "font-size": 11, "font-weight": 600, fill: hot ? "var(--orange-ink)" : "var(--ink)", text: condition(it.flow),
        }));
      }
    }
    const title = sv("title", { text: nodeName(it.id) });
    if (it.kind === "start") svg.append(sv("g", {}, title, shape.start(it.x + EV, it.cy)));
    else if (it.kind === "end") svg.append(sv("g", {}, title, shape.end(it.x + EV, it.cy)));
    else if (it.kind === "gateway") svg.append(sv("g", {}, title, shape.gateway(it.x + GW, it.cy, "exclusiveGateway")));
    else {
      const g = sv("g", {}, title, shape.task(it.x, it.cy - boxH / 2, boxW, boxH));
      const text = lines(T.activities[it.id] ?? it.id);
      text.forEach((line, i) => g.append(sv("text", {
        x: it.x + boxW / 2, y: it.cy + 4 + (i - (text.length - 1) / 2) * 13, "text-anchor": "middle", "font-size": 11, "font-weight": 600, fill: "var(--ink)", text: line,
      })));
      svg.append(g);
    }
  });
  return svg;
}

/** How a path reads: the loops it takes and how often, or the clean path. */
function pathName(labels) {
  const G = T.groups, E = T.embed;
  const counts = {};
  for (const l of labels) {
    const [gateway, flow] = l.split(">");
    if (flow && isLoop(flow)) counts[gateway] = (counts[gateway] ?? 0) + 1;
  }
  const order = Object.keys(G.loop_parts);
  const parts = Object.keys(counts).sort((a, b) => order.indexOf(a) - order.indexOf(b))
    .map((g) => fill(E.path_times, { part: G.loop_parts[g], n: counts[g] }));
  if (labels.at(-1) === "End_ProposalRejected") parts.push(E.path_rejected);
  if (!parts.length) return E.path_clean;
  const text = new Intl.ListFormat(T.lang, { type: "conjunction" }).format(parts);
  return text[0].toLocaleUpperCase(T.lang) + text.slice(1);
}

/** The directly-follows graph of the log, nodes where the model has them; highlight(labels) lights up one path. */
function followsGraph(edges, points) {
  const layout = buildLayout("as_is", "normal");
  const pad = 30;
  const at = (id) => layout.nodes[id];
  const W = layout.width + 2 * pad, H = layout.height + 2 * pad;
  const svg = sv("svg", { class: "follows", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": T.embed.graph_title },
    sv("defs", {}, arrowMarker("dfg-arrow", "var(--edge)"), arrowMarker("dfg-arrow-back", "var(--orange)"), arrowMarker("dfg-arrow-on", "var(--teal)")));
  const max = Math.max(...edges.map((e) => e.count));
  const R = (id) => (at(id).type === "task" ? 11 : 8);
  const edgeEls = new Map();
  const pairs = new Set(edges.map((e) => `${e.source}|${e.target}`));
  for (const e of edges) {
    const a = at(e.source), b = at(e.target);
    if (!a || !b) continue;
    const [x1, y1, x2, y2] = [a.cx + pad, a.cy + pad, b.cx + pad, b.cy + pad];
    const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy) || 1;
    // bend each edge a little to its left, more when the reverse edge exists, so the two never overlap
    const bend = (pairs.has(`${e.target}|${e.source}`) ? 0.22 : 0.1) * len;
    const mx = (x1 + x2) / 2 - (dy / len) * bend, my = (y1 + y2) / 2 + (dx / len) * bend;
    const unit = (x, y, tx, ty) => { const d = Math.hypot(tx - x, ty - y) || 1; return [(tx - x) / d, (ty - y) / d]; };
    const [sx, sy] = unit(x1, y1, mx, my), [ex, ey] = unit(x2, y2, mx, my);
    const back = b.cx < a.cx - 1; // the edge goes back along the process: a loop
    const width = 1 + 5 * Math.sqrt(e.count / max);
    const path = sv("path", {
      d: `M${x1 + sx * R(e.source)},${y1 + sy * R(e.source)} Q${mx},${my} ${x2 + ex * (R(e.target) + 3)},${y2 + ey * (R(e.target) + 3)}`,
      fill: "none", stroke: back ? "var(--orange)" : "var(--edge)", "stroke-width": width.toFixed(2),
      "marker-end": `url(#${back ? "dfg-arrow-back" : "dfg-arrow"})`, "data-back": String(back),
    }, sv("title", { text: fill(T.embed.edge_title, { from: nodeName(e.source), to: nodeName(e.target), n: NUM(0).format(e.count) }) }));
    svg.append(path);
    edgeEls.set(`${e.source}|${e.target}`, path);
  }
  const nodeEls = new Map();
  for (const p of points) {
    const n = at(p.activity_id);
    if (!n) continue;
    const g = sv("g", { class: "dfg-node" }, sv("title", { text: nodeName(p.activity_id) }),
      sv("circle", { cx: n.cx + pad, cy: n.cy + pad, r: R(p.activity_id), fill: n.type === "task" ? "var(--ink)" : "var(--surface)", stroke: "var(--ink)", "stroke-width": 2 }));
    const label = T.activities[p.activity_id] ?? T.events[p.activity_id];
    if (label) lines(label).forEach((line, i) => g.append(sv("text", {
      x: n.cx + pad, y: n.cy + pad + R(p.activity_id) + 16 + i * 16, "text-anchor": "middle", "font-size": 15, "font-weight": 600, fill: "var(--ink)",
      stroke: "var(--surface)", "stroke-width": 4, "paint-order": "stroke", text: line,
    })));
    svg.append(g);
    nodeEls.set(p.activity_id, g);
  }
  const highlight = (labels) => {
    const ids = labels.map((l) => l.split(">")[0]);
    const on = new Set(ids.slice(1).map((id, i) => `${ids[i]}|${id}`));
    for (const [key, el] of edgeEls) {
      const lit = on.has(key);
      el.classList.toggle("on", lit);
      el.classList.toggle("off", !lit);
      el.setAttribute("marker-end", `url(#${lit ? "dfg-arrow-on" : el.dataset.back === "true" ? "dfg-arrow-back" : "dfg-arrow"})`);
      if (lit) svg.insertBefore(el, svg.querySelector(".dfg-node")); // lit edges over the others, under the nodes
    }
    const visited = new Set(ids);
    for (const [id, el] of nodeEls) el.classList.toggle("off", !visited.has(id));
  };
  return { svg, highlight };
}

/** Panel A of step 2: the graph, the real paths through it, and the chosen path as graph2vec reads it. */
function pathsPanel(results) {
  const E = T.embed;
  const cases = results.clusters.cases;
  const total = cases.points.length;
  const graph = followsGraph(results.clusters.activities.edges, results.clusters.activities.points);
  const chainHost = el("div", { class: "chain-scroll" });
  const chosen = el("h3", {});
  const buttons = [];
  const pick = (k) => {
    const p = cases.paths[k];
    buttons.forEach((b, i) => b.setAttribute("aria-pressed", String(i === k)));
    graph.highlight(p.labels);
    chosen.textContent = fill(E.chosen_path, { name: pathName(p.labels) });
    chainHost.replaceChildren(chainSvg(p.labels));
  };
  const rows = cases.paths.map((p, k) => {
    const b = el("button", { type: "button", class: "path-row", "aria-pressed": "false" },
      el("span", { class: "path-rank", text: NUM(0).format(k + 1) }),
      el("span", { class: "path-name", text: pathName(p.labels) }),
      el("span", { class: "path-count", text: fill(E.path_cases, { n: NUM(0).format(p.case_count), share: pct(p.case_count / total, 0) }) }),
      el("span", { class: "path-days", text: fill(E.path_days, { days: fmt(p.cycle_time) }) }));
    b.addEventListener("click", () => pick(k));
    buttons.push(b);
    return b;
  });
  const shown = cases.paths.reduce((sum, p) => sum + p.case_count, 0);
  const legendEdge = (color, w) => sv("svg", { width: 34, height: 14, "aria-hidden": "true" }, sv("line", { x1: 2, x2: 32, y1: 7, y2: 7, stroke: color, "stroke-width": w, "stroke-linecap": "round" }));
  const legendNode = (filled) => sv("svg", { width: 18, height: 18, "aria-hidden": "true" }, sv("circle", { cx: 9, cy: 9, r: 6, fill: filled ? "var(--ink)" : "var(--surface)", stroke: "var(--ink)", "stroke-width": 2 }));
  const panel = el("section", { class: "panel still", "aria-labelledby": "dfg-title" },
    el("h2", { id: "dfg-title", text: E.graph_title }),
    el("p", { class: "method", text: E.graph_intro }),
    el("div", { class: "follows-scroll" }, graph.svg),
    el("ul", { class: "legend" },
      el("li", {}, legendNode(true), E.legend_task), el("li", {}, legendNode(false), E.legend_other),
      el("li", {}, legendEdge("var(--edge)", 3), E.legend_edge), el("li", {}, legendEdge("var(--orange)", 3), E.legend_back),
      el("li", {}, legendEdge("var(--teal)", 4), E.legend_on)),
    el("h3", { text: E.paths_title }),
    el("p", { class: "fine", text: fill(E.paths_note, { shown: cases.paths.length, total: NUM(0).format(cases.path_count), share: pct(shown / total, 0) }) }),
    el("div", { class: "path-list" }, rows),
    chosen, chainHost);
  pick(0);
  return panel;
}

/** Step 2: the log as a graph with its paths, the handover network between departments, then each project turned into a vector. */
function embedView(results, asIs) {
  const E = T.embed;
  const cases = results.clusters.cases;
  const caseMap = vectorMap(cases.points.map((p) => ({ x: p.x, y: p.y })));
  caseMap.svg.setAttribute("aria-label", fill(E.case_map, { cases: NUM(0).format(cases.points.length) }));
  const graphs = el("section", { class: "panel still", "aria-labelledby": "graph-title" },
    el("h2", { id: "graph-title", text: E.g2v_title }),
    el("p", { class: "method", text: fill(E.graph_method, { iterations: cases.method.wl_iterations, dimensions: cases.method.dimensions }) }),
    el("h3", { text: fill(E.case_map, { cases: NUM(0).format(cases.points.length) }) }),
    el("div", { class: "map-narrow" }, caseMap.svg), el("p", { class: "fine", text: E.case_map_note }));
  return [pathsPanel(results), ...(results.social ? [socialPanel(results, asIs)] : []), graphs];
}

/** Step 2, panel B: the handover network between departments, sized by the centrality measure picked above it. */
function socialPanel(results, asIs) {
  const S = T.social;
  const social = results.social;
  const rows = social.centrality;
  const byLane = Object.fromEntries(rows.map((r) => [r.lane_id, r]));
  const MEASURES = ["betweenness", "degree", "closeness", "pagerank", "in_handovers", "out_handovers"];
  const counts = new Set(["in_handovers", "out_handovers"]);
  const show = (m, v) => (counts.has(m) ? NUM(0).format(v) : fmt(v, 2));
  const lanes = LANES.filter((id) => id in byLane); // process order around the circle
  const W = 680, H = 490, cx = W / 2, cy = 255, ring = 165; // room above the top node for its name at the largest size
  const pos = Object.fromEntries(lanes.map((id, i) => {
    const a = -Math.PI / 2 + (2 * Math.PI * i) / lanes.length;
    return [id, { x: cx + ring * Math.cos(a), y: cy + ring * Math.sin(a) }];
  }));
  const name = (id) => oneLine(T.lanes[id]);
  const svg = sv("svg", { class: "social", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": S.title },
    sv("defs", {}, arrowMarker("sna-arrow", "var(--edge)")));
  const R = 54; // the largest node; the others scale by area
  const max = Math.max(...social.handovers.map((e) => e.count));
  const pairs = new Set(social.handovers.map((e) => `${e.source}|${e.target}`));
  const edgeLayer = sv("g", {}), nodeLayer = sv("g", {});
  svg.append(edgeLayer, nodeLayer);

  const nodes = Object.fromEntries(lanes.map((id) => {
    const circle = sv("circle", { cx: pos[id].x, cy: pos[id].y, stroke: "var(--ink)", "stroke-width": 2 });
    const value = sv("text", { x: pos[id].x, y: pos[id].y + 5, "text-anchor": "middle", "font-size": 15, "font-weight": 700 });
    const label = sv("text", { "text-anchor": "middle", "font-size": 15, "font-weight": 700, fill: "var(--ink)", stroke: "var(--lane)", "stroke-width": 4, "paint-order": "stroke", text: name(id) });
    const title = sv("title", {});
    nodeLayer.append(sv("g", {}, title, circle, value, label));
    return [id, { circle, value, label, title }];
  }));

  const barsHost = el("div", { class: "sna-bars" });
  const explain = el("p", { class: "sna-explain" });
  const buttons = MEASURES.map((m) => {
    const b = el("button", { type: "button", class: "sna-measure", "aria-pressed": "false", text: S.measures[m].name });
    b.addEventListener("click", () => draw(m));
    return b;
  });

  function draw(m) {
    buttons.forEach((b, i) => b.setAttribute("aria-pressed", String(MEASURES[i] === m)));
    const top = Math.max(...rows.map((r) => r[m]));
    const radius = (id) => 12 + (R - 12) * Math.sqrt(top ? byLane[id][m] / top : 0);
    for (const id of lanes) {
      const v = byLane[id][m], p = pos[id], r = radius(id), lead = v === top && v > 0;
      const n = nodes[id];
      n.circle.setAttribute("r", r.toFixed(1));
      n.circle.setAttribute("fill", lead ? "var(--teal)" : v > 0 ? "var(--teal-soft)" : "var(--surface)");
      n.value.textContent = show(m, v);
      n.value.setAttribute("fill", lead ? "#fff" : "var(--ink)");
      n.value.setAttribute("font-size", r < 26 ? 12 : 15);
      // a small node shows its value beside it, not inside
      n.value.setAttribute("x", r < 26 ? p.x + r + 6 : p.x);
      n.value.setAttribute("text-anchor", r < 26 ? "start" : "middle");
      const below = p.y >= cy - 1;
      n.label.setAttribute("x", p.x);
      n.label.setAttribute("y", below ? p.y + r + 20 : p.y - r - 10);
      n.title.textContent = fill(S.node_title, { lane: name(id), measure: S.measures[m].name, value: show(m, v) });
    }
    // edges end at the node's edge, so they follow the sizes
    edgeLayer.replaceChildren(...social.handovers.map((e) => {
      const a = pos[e.source], b = pos[e.target];
      const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy);
      const bend = (pairs.has(`${e.target}|${e.source}`) ? 0.16 : 0.06) * len;
      const mx = (a.x + b.x) / 2 - (dy / len) * bend, my = (a.y + b.y) / 2 + (dx / len) * bend;
      const toward = (p, r) => { const d = Math.hypot(mx - p.x, my - p.y); return [p.x + ((mx - p.x) / d) * r, p.y + ((my - p.y) / d) * r]; };
      const [x1, y1] = toward(a, radius(e.source) + 2), [x2, y2] = toward(b, radius(e.target) + 5);
      return sv("path", {
        d: `M${x1},${y1} Q${mx},${my} ${x2},${y2}`, fill: "none", stroke: "var(--edge)", "stroke-width": (1 + 7 * Math.sqrt(e.count / max)).toFixed(2),
        opacity: 0.75, "marker-end": "url(#sna-arrow)",
      }, sv("title", { text: fill(S.edge_title, { from: name(e.source), to: name(e.target), n: NUM(0).format(e.count) }) }));
    }));
    const sorted = [...rows].sort((a, b) => b[m] - a[m]);
    barsHost.replaceChildren(...sorted.map((r) => el("div", { class: "sna-bar-row" },
      el("span", { class: "sna-name", text: name(r.lane_id) }),
      el("span", { class: "sna-track" }, el("span", { class: "sna-bar", style: `width: ${top ? (r[m] / top) * 100 : 0}%` })),
      el("span", { class: "sna-value", text: show(m, r[m]) }))));
    explain.textContent = S.measures[m].explain;
  }

  // every measure side by side, the highest of each column in bold
  const table = el("table", { class: "sna-table" },
    el("thead", {}, el("tr", {}, el("th", { text: S.lane }), MEASURES.map((m) => el("th", { class: "num", text: S.measures[m].name })))),
    el("tbody", {}, rows.map((r) => el("tr", {}, el("td", { text: name(r.lane_id) }),
      MEASURES.map((m) => el("td", { class: r[m] === Math.max(...rows.map((x) => x[m])) ? "num lead" : "num", text: show(m, r[m]) }))))));

  const best = rows[0];
  const panel = el("section", { class: "panel still", "aria-labelledby": "sna-title" },
    el("h2", { id: "sna-title", text: S.title }),
    el("p", { class: "method", text: S.intro }),
    el("div", { class: "sna-measures", role: "group", "aria-label": S.measure_label }, buttons),
    el("div", { class: "sna-grid" },
      el("div", { class: "sna-map" }, svg),
      el("div", {},
        explain, barsHost,
        best.betweenness > 0 ? el("p", { class: "sna-finding", text: fill(S.finding, { lane: name(best.lane_id), share: pct(best.betweenness, 0), people: asIs.capacities[best.lane_id] }) }) : null)),
    el("h3", { text: S.table_title }),
    el("div", { class: "sna-table-scroll" }, table));
  draw("betweenness");
  return panel;
}

/** Silhouette per k, the chosen k in teal. */
function silhouetteChart(rows, chosen, title) {
  const W = 340, H = 190, left = 30, bottom = 34, top = 22;
  const max = Math.max(...rows.map((r) => r.silhouette)) * 1.15;
  const bw = (W - left - 10) / rows.length;
  const svg = sv("svg", { class: "sil", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": title });
  svg.append(sv("line", { x1: left, x2: W - 6, y1: H - bottom, y2: H - bottom, stroke: "var(--line)" }));
  rows.forEach((r, i) => {
    const h = (r.silhouette / max) * (H - bottom - top);
    const x = left + i * bw + bw * 0.18, w = bw * 0.64, y = H - bottom - h;
    const pick = r.k === chosen;
    svg.append(sv("g", {}, sv("title", { text: `k = ${r.k}: ${fmt(r.silhouette, 3)}` }),
      sv("path", { d: `M${x},${H - bottom} V${y + 4} q0,-4 4,-4 H${x + w - 4} q4,0 4,4 V${H - bottom} z`, fill: pick ? "var(--teal)" : "var(--teal-soft)" }),
      sv("text", { x: x + w / 2, y: y - 6, "text-anchor": "middle", "font-size": 12, "font-weight": pick ? 700 : 500, fill: "var(--ink)", text: fmt(r.silhouette, 2) }),
      sv("text", { x: x + w / 2, y: H - bottom + 16, "text-anchor": "middle", "font-size": 12, "font-weight": pick ? 700 : 500, fill: pick ? "var(--ink)" : "var(--muted)", text: r.k })));
  });
  svg.append(sv("text", { x: left + (W - left) / 2, y: H - 4, "text-anchor": "middle", "font-size": 12, fill: "var(--muted)", text: T.kmeans.k_axis }));
  return svg;
}

/** Step 3: what k-means found on the graph2vec vectors. The findings first, then the project groups, and last how k was picked. */
function kmeansView(results, asIs) {
  const K = T.kmeans, G = T.groups;
  const cases = results.clusters.cases;
  const [kMin, kMax] = cases.method.k_range;
  const list = new Intl.ListFormat(T.lang, { type: "conjunction" });
  const order = Object.keys(G.loop_parts); // loops in process order, the order of loop_parts in the content file
  const loopNames = (ids) => list.format([...ids].sort((a, b) => order.indexOf(a) - order.indexOf(b)).map((id) => G.loop_parts[id]));

  const f = findings(results);
  const said = [
    f.clean ? fill(K.f_clean, { share: pct(f.clean.share, 0), days: fmt(f.clean.days) }) : null,
    fill(f.slowest.ratio ? K.f_slowest : K.f_slowest_alone, { parts: loopNames(f.slowest.loops), days: fmt(f.slowest.days), ratio: fmt(f.slowest.ratio ?? 0) }),
    f.qc ? fill(K.f_qc, { share: pct(f.qc.share, 0), low: fmt(f.qc.low, 0), high: fmt(f.qc.high, 0) }) : null,
    f.features.length ? fill(K.f_features, { features: list.format(f.features.map((x) => G.features[x] ?? x)) }) : null,
  ].filter(Boolean);
  const found = el("section", { class: "panel still", "aria-labelledby": "found-title" },
    el("h2", { id: "found-title", text: K.findings_title }),
    el("div", { class: "findings" }, said.map((text) => el("p", { text }))));

  const choose = el("section", { class: "panel still", "aria-labelledby": "k-title" },
    el("h2", { id: "k-title", text: K.title }),
    el("p", { class: "method", text: fill(K.what_k, { k: cases.k }) }),
    el("p", { class: "method", text: fill(K.method, { k_min: kMin, k_max: kMax }) }),
    el("div", { class: "sil-grid" },
      el("div", {}, el("h3", { text: K.sil_cases }), silhouetteChart(cases.silhouette, cases.k, K.sil_cases), el("p", { class: "fine", text: fill(K.chosen, { k: cases.k }) }))),
    cases.k === kMax ? el("p", { class: "fine", text: fill(K.cap_note, { k: kMax }) }) : null);

  // project groups: the list, slowest first, and the map with the picked group in teal
  const rows = caseGroups(results);
  const overall = overallDays(results);
  const name = (g) => (g.loops.length ? fill(G.loops, { parts: loopNames(g.loops) }) : G.clean);
  const valueName = (feature, value) => G.values[feature]?.[value] ?? String(value);
  const max = Math.max(overall, ...rows.map((g) => g.days)) * 1.08;
  const at = (days) => `${(days / max) * 100}%`;
  const map = vectorMap(casePoints(results).map((p) => ({ x: p.x, y: p.y, cls: `g${p.group}` })));
  map.svg.setAttribute("aria-label", G.map_title);
  const buttons = [];
  const pick = (id) => {
    for (const b of buttons) b.setAttribute("aria-pressed", String(Number(b.dataset.group) === id));
    for (const d of map.dots) {
      const on = d.getAttribute("class") === `g${id}`;
      d.classList.toggle("picked", on);
      if (on) map.svg.append(d); // picked dots on top
    }
  };
  const items = rows.map((g) => {
    const rejected = g.ends.find((e) => e.end_event_id === "End_ProposalRejected");
    const often = g.profile.map((p) => fill(G.often_item, {
      feature: G.features[p.feature] ?? p.feature, value: valueName(p.feature, p.value),
      share: pct(p.share, 0), overall: pct(p.overall_share, 0),
    }));
    const b = el("button", { type: "button", class: "group-row", "data-group": g.id, "aria-pressed": "false" },
      el("span", { class: "group-name", text: name(g) }),
      el("span", { class: "group-count", text: fill(G.count, { n: NUM(0).format(g.cases), share: pct(g.share, 0) }) }),
      el("span", { class: "group-track" },
        el("span", { class: "group-bar", style: `width: ${at(g.days)}` }),
        el("span", { class: "group-overall", style: `left: ${at(overall)}` }),
        el("span", { class: "group-days", style: `left: ${at(g.days)}`, text: fill(G.days, { days: fmt(g.days) }) })),
      rejected ? el("span", { class: "group-sub", text: fill(G.rejected, { share: pct(rejected.share, 0) }) }) : null,
      often.length ? el("span", { class: "group-sub", text: fill(G.often, { items: list.format(often) }) }) : null);
    b.addEventListener("click", () => pick(g.id));
    buttons.push(b);
    return b;
  });
  const projects = el("section", { class: "panel still", "aria-labelledby": "groups-title" },
    el("h2", { id: "groups-title", text: G.title }),
    el("p", { class: "method", text: fill(G.method, { k: rows.length }) }),
    el("div", { class: "groups-grid" },
      el("div", {},
        el("h3", { text: G.cycle_title }),
        el("p", { class: "overall-key" }, sv("svg", { width: 14, height: 18, "aria-hidden": "true" },
          sv("line", { x1: 7, x2: 7, y1: 1, y2: 17, stroke: "var(--ink)", "stroke-width": 1.6, "stroke-dasharray": "3 2" })),
          fill(G.overall, { days: fmt(overall) })),
        el("div", { class: "group-list" }, items)),
      el("div", {}, el("h3", { text: G.map_title }), map.svg, el("p", { class: "fine", text: G.map_note }))),
    el("p", { class: "fine", text: G.note }));
  pick(rows[0].id);

  return [found, projects, choose];
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
      const r = await fetch(u, { cache: "no-store" }); // a rerun of the notebook must show at once
      if (!r.ok) throw new Error(`${u}: HTTP ${r.status}`);
      return r.json();
    }));
  // the as-is model, copied next to the results by the notebook
  const modelResponse = await fetch(new URL(results.models.as_is.bpmn, new URL("../results.json", location.href)), { cache: "no-store" });
  if (!modelResponse.ok) throw new Error(`${results.models.as_is.bpmn}: HTTP ${modelResponse.status}`);
  const asIsXml = await modelResponse.text();
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

  // One address for the whole talk: drop any ?view=... left from the old tabbed page.
  if (location.search) history.replaceState(null, "", location.pathname);
  // An older results file without the clusters section skips steps 2 and 3.
  const steps = STEPS.filter((st) => results.clusters || !["embed", "kmeans"].includes(st));
  const sim = { t: win.start, playing: false, speed: 1, step: steps[0], compare: false };

  const stage = document.getElementById("stage");
  const bar = document.getElementById("bar");
  const playBtn = document.getElementById("play");
  const progress = document.getElementById("progress");
  const qchartHost = document.getElementById("qchart");
  let views = []; // {flow: FlowView, counters}
  let chart = null;

  // step bar: back, the numbered steps, next
  const nav = document.getElementById("views");
  nav.setAttribute("aria-label", T.steps.label);
  const chevron = (d) => sv("svg", { width: 16, height: 16, viewBox: "0 0 16 16", "aria-hidden": "true" },
    sv("path", { d, fill: "none", stroke: "currentColor", "stroke-width": 2.2, "stroke-linecap": "round", "stroke-linejoin": "round" }));
  const backBtn = el("button", { type: "button", class: "step-move", "aria-label": T.steps.back }, chevron("M10 3L5 8l5 5"));
  const nextBtn = el("button", { type: "button", class: "step-move next" }, el("span", { text: T.steps.next }), chevron("M6 3l5 5-5 5"));
  const stepButtons = steps.map((st, i) => {
    const b = el("button", { type: "button", class: "step", "data-step": st },
      el("span", { class: "step-n", text: NUM(0).format(i + 1) }), el("span", { class: "step-name", text: T.steps.names[st] }));
    b.addEventListener("click", () => setStep(st));
    return b;
  });
  const move = (d) => setStep(steps[Math.min(steps.length - 1, Math.max(0, steps.indexOf(sim.step) + d))]);
  backBtn.addEventListener("click", () => move(-1));
  nextBtn.addEventListener("click", () => move(1));
  nav.append(backBtn, el("ol", { class: "step-list" }, stepButtons.map((b) => el("li", {}, b))), nextBtn);

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

  function legend(ids) {
    const withAnd = ids.includes("to_be");
    const tokens = [["work", T.legend.work], ["wait", T.legend.wait], ...(withAnd ? [["park", T.legend.park]] : []), ["live", T.legend.live]];
    const notation = ["start", "end", "task", "xor", ...(withAnd ? ["and"] : []), "flow"];
    return el("div", { class: "legend-block" },
      el("ul", { class: "legend", "data-legend": "tokens" }, tokens.map(([k, label]) => el("li", {}, legendDot(DOT_STYLE[k]), label))),
      el("ul", { class: "legend", "data-legend": "notation" }, notation.map((k) => el("li", {}, legendShape(k), T.legend[k]))),
      el("p", { class: "note", "data-note": "tokens", text: `${T.legend.token} ${T.legend.share}` }),
      el("p", { class: "note", "data-note": "sample", text: fill(T.sample_note, { seed: replay.seed, months: clock(win, win.end).totalMonths }) }));
  }

  function changesList() {
    const caps = scen.to_be.capacities, before = scen.as_is.capacities;
    const qc = "Lane_QualityControl";
    return el("ul", { class: "changes" }, scen.to_be.changes.map((c) => el("li", {},
      el("span", { class: "chip", text: c }), el("b", { text: T.changes[c].name }),
      el("span", { text: fill(T.changes[c].detail, { from: before[qc], to: caps[qc] }) }))));
  }

  function compareToggle() {
    const b = el("button", { type: "button", class: "compare-toggle", "aria-pressed": String(sim.compare), text: sim.compare ? T.steps.compare_off : T.steps.compare_on });
    b.addEventListener("click", () => { sim.compare = !sim.compare; setStep("sim_to_be"); });
    return b;
  }

  function setStep(st) {
    sim.step = st;
    const i = steps.indexOf(st);
    stepButtons.forEach((b) => (b.dataset.step === st ? b.setAttribute("aria-current", "step") : b.removeAttribute("aria-current")));
    backBtn.disabled = i === 0;
    nextBtn.disabled = i === steps.length - 1;
    for (const x of views) x.flow.reset();
    views = [];
    stage.replaceChildren();
    stage.scrollTop = 0;
    const compare = st === "sim_to_be" && sim.compare;
    stage.classList.toggle("compare", compare);
    document.body.classList.toggle("compare", compare);
    document.body.dataset.step = st;
    if (!st.startsWith("sim_")) {
      sim.playing = false;
      bar.hidden = true;
      const still = { bpmn: () => bpmnView(scen.as_is, asIsXml), embed: () => embedView(results, scen.as_is), kmeans: () => kmeansView(results, scen.as_is), result: () => [resultView(results)] };
      stage.append(...still[st]());
      return;
    }
    bar.hidden = false;
    const ids = st === "sim_as_is" ? ["as_is"] : compare ? ["as_is", "to_be"] : ["to_be"];
    views = ids.map((id) => panel(id, compare ? "compact" : "normal"));
    for (const x of views) stage.append(x.node);
    const below = el("div", { class: "below" });
    if (st === "sim_to_be") {
      below.append(changesList());
      // the switch sits in the to-be panel's header, so the transport bar never covers it
      views.find((x) => x.id === "to_be").node.querySelector(".panel-head h2").after(compareToggle());
    }
    below.append(legend(ids));
    if (compare) stage.append(el("div", { class: "panel" }, below));
    else views[0].node.append(below);
    chart = queueChart(ids.map((id) => ({ id, name: scen[id].name, color: COLORS[id], points: series[id] })), sim);
    qchartHost.replaceChildren(chart.node);
    render(performance.now(), 1000);
  }

  // transport
  const speedHost = document.getElementById("speed");
  document.getElementById("speed-label").textContent = T.controls.speed;
  const speedButtons = SPEEDS.map((s) => {
    const b = el("button", { type: "button", "aria-pressed": String(s === sim.speed), text: fill(T.controls.speed_value, { v: NUM(s % 1 ? 1 : 0).format(s) }) });
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
    if (ev.code === "Space" && sim.step.startsWith("sim_")) { ev.preventDefault(); togglePlay(); }
    // arrows, and the page keys a presentation clicker sends
    if (ev.key === "ArrowRight" || ev.key === "PageDown") { ev.preventDefault(); move(1); }
    if (ev.key === "ArrowLeft" || ev.key === "PageUp") { ev.preventDefault(); move(-1); }
    const k = Number(ev.key);
    if (k >= 1 && k <= steps.length) setStep(steps[k - 1]);
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

  setStep(sim.step);
  requestAnimationFrame(frame);
  // For the browser checks: read the clock and the counters the page shows.
  window.demo = { sim, win, figures: () => figures(results), groups: () => caseGroups(results), state: (id) => stateAt(preps[id], sim.t), setStep, steps, togglePlay, views: () => views };
}

main().catch((err) => {
  console.error(err);
  const msg = T?.error ? fill(T.error, { error: err.message }) : `${err.name}: ${err.message}`;
  document.getElementById("stage").replaceChildren(el("p", { class: "error", text: msg }));
});
