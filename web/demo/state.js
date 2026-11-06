// Per-time state of one replay scenario (web/demo/replay.json), with no DOM: the page
// draws it, and tests/demo_state.test.mjs checks it in Node.
//
// A row is waiting from `ready` to `start` and worked on from `start` to `end`. Times can
// run past the window, so everything is read at a clock t inside [window.start, window.end].

const EPS = 0.011; // times are rounded to 2 decimals

export const QC_LANE = "Lane_QualityControl";

export function prepare(scenario, window) {
  const rows = scenario.rows.map((r, i) => ({ ...r, i, prev: null, parkUntil: null, last: false }));
  const byCase = new Map();
  for (const r of rows) {
    if (!byCase.has(r.case)) byCase.set(r.case, []);
    byCase.get(r.case).push(r);
  }
  for (const list of byCase.values()) {
    for (const r of list) {
      // Predecessor: the row of the same case that ended last when this one became ready.
      let prev = null, nextReady = Infinity;
      for (const q of list) {
        if (q === r) continue;
        if (q.end <= r.ready + EPS && (!prev || q.end > prev.end)) prev = q;
        if (q.ready >= r.end - EPS && q.ready < nextReady) nextReady = q.ready;
      }
      r.prev = prev ? prev.i : null;
      r.last = nextReady === Infinity;
      // A parallel check that finished first waits at the join for the others.
      if (!r.last && nextReady > r.end + 2 * EPS) r.parkUntil = nextReady;
    }
  }
  const cases = scenario.cases.map((c) => ({ ...c, finish: c.cycle_time == null ? null : c.arrival + c.cycle_time }));
  const finishOf = new Map(cases.map((c) => [c.id, c.finish]));
  return { id: scenario.id, window, rows, cases, finishOf };
}

// Everything visible at time t: which rows show a dot, where, and the live counters.
export function stateAt(prep, t) {
  const items = [];
  const work = new Map(), wait = new Map(), park = new Map();
  const push = (map, task, row) => {
    if (!map.has(task)) map.set(task, []);
    map.get(task).push(row);
  };
  let waitingQc = 0;
  for (const r of prep.rows) {
    if (r.ready > t) continue;
    if (t < r.start) {
      push(wait, r.activity, r);
      if (r.lane === QC_LANE) waitingQc++;
    } else if (t < r.end) push(work, r.activity, r);
    else if (r.parkUntil != null && t < r.parkUntil) push(park, r.activity, r);
  }
  const live = (r) => {
    const f = prep.finishOf.get(r.case);
    return f != null && f <= t;
  };
  for (const [mode, map, key] of [["work", work, "start"], ["wait", wait, "ready"], ["park", park, "end"]]) {
    for (const [task, list] of map) {
      list.sort((a, b) => a[key] - b[key] || a.i - b.i);
      list.forEach((r, slot) => items.push({ i: r.i, case: r.case, task, mode, slot, count: list.length, prev: r.prev, live: live(r) }));
    }
  }
  const waitCounts = Object.fromEntries([...wait].map(([task, list]) => [task, list.length]));
  return { t, items, waitCounts, counters: counters(prep, t, waitingQc) };
}

export function counters(prep, t, waitingQc = null) {
  const { start } = prep.window;
  let inProgress = 0, finished = 0, sum = 0;
  for (const c of prep.cases) {
    if (c.arrival > t) continue;
    if (c.finish != null && c.finish <= t) {
      if (c.finish >= start) {
        finished++;
        sum += c.cycle_time;
      }
    } else inProgress++;
  }
  if (waitingQc == null) waitingQc = prep.rows.filter((r) => r.lane === QC_LANE && r.ready <= t && t < r.start).length;
  return { inProgress, waitingQc, finished, meanCycle: finished ? sum / finished : null };
}

// Tasks waiting at QC, sampled every `step` working days over the window (for the queue chart).
export function qcQueueSeries(prep, step = 1) {
  const { start, end } = prep.window;
  const qc = prep.rows.filter((r) => r.lane === QC_LANE && r.start > r.ready);
  const out = [];
  for (let t = start; t <= end + 1e-9; t += step) {
    let n = 0;
    for (const r of qc) if (r.ready <= t && t < r.start) n++;
    out.push([t, n]);
  }
  return out;
}

// Real seconds -> simulated working days. One simulated month is 1/12 of a 250-day year.
export const MONTH = 250 / 12;

export function clock(window, t) {
  const total = Math.round((window.end - window.start) / MONTH);
  const elapsed = Math.max(0, Math.min(t, window.end) - window.start);
  return { month: Math.min(total, Math.floor(elapsed / MONTH) + 1), totalMonths: total, day: Math.round(elapsed), totalDays: Math.round(window.end - window.start), progress: elapsed / (window.end - window.start) };
}

// Walk a polyline by a fraction of its length (dots move along the arrows).
export function along(pts, f) {
  if (pts.length === 1) return pts[0];
  const seg = [];
  let total = 0;
  for (let k = 1; k < pts.length; k++) {
    const d = Math.hypot(pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]);
    seg.push(d);
    total += d;
  }
  let target = Math.max(0, Math.min(1, f)) * total;
  for (let k = 0; k < seg.length; k++) {
    if (target <= seg[k] || k === seg.length - 1) {
      const u = seg[k] ? Math.min(1, target / seg[k]) : 1;
      return [pts[k][0] + (pts[k + 1][0] - pts[k][0]) * u, pts[k][1] + (pts[k + 1][1] - pts[k][1]) * u];
    }
    target -= seg[k];
  }
  return pts[pts.length - 1];
}
