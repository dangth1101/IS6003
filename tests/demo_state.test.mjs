// Node tests of the flow demo's state module (web/demo/state.js). Run by tests/test_demo.py,
// or directly: node --test tests/demo_state.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { prepare, stateAt, counters, qcQueueSeries, clock, along, rest, MONTH } from "../web/demo/state.js";
import { buildLayout, dotPosition, parkPosition, route, TYPE, SPACE, HEADER, WIDTH, CHIP } from "../web/demo/layout.js";

const WINDOW = { start: 10, end: 40 };
const QC = "Lane_QualityControl";
// Case 1: build, then two parallel checks (one finishes early and waits at the join), then go-live.
// Case 2: arrived before the window, went live before it opened, still monitored inside it.
// Case 3: arrives inside the window and is still waiting at the end.
const scenario = {
  id: "toy",
  cases: [
    { id: 1, arrival: 5, cycle_time: 20 },
    { id: 2, arrival: 0, cycle_time: 8 },
    { id: 3, arrival: 30, cycle_time: null },
  ],
  rows: [
    { case: 1, activity: "Task_BuildApplication", lane: "Lane_Development", ready: 5, start: 6, end: 12 },
    { case: 1, activity: "Task_ReviewSourceCode", lane: QC, ready: 12, start: 14, end: 16 },
    { case: 1, activity: "Task_RunFunctionalTests", lane: QC, ready: 12, start: 12, end: 20 },
    { case: 1, activity: "Task_StartOperation", lane: "Lane_ITOperations", ready: 20, start: 20, end: 25 },
    { case: 2, activity: "Task_MonitorOperation", lane: "Lane_ITOperations", ready: 8, start: 8, end: 15 },
    { case: 3, activity: "Task_RegisterRequest", lane: "Lane_BusinessUnit", ready: 30, start: 45, end: 47 },
  ],
};
const prep = prepare(scenario, WINDOW);
const modes = (t) => Object.fromEntries(stateAt(prep, t).items.map((x) => [x.i, x.mode]));

test("a row waits from ready to start and is worked on from start to end", () => {
  assert.deepEqual(modes(13), { 1: "wait", 2: "work", 4: "work" });
  assert.deepEqual(modes(15), { 1: "work", 2: "work" });
});

test("a parallel check that finishes first waits at the join until the next task is ready", () => {
  assert.equal(prep.rows[1].parkUntil, 20);
  assert.deepEqual(modes(17), { 2: "work", 1: "park" });
  assert.equal(prep.rows[2].parkUntil, null);
  assert.equal(modes(20)[1], undefined);
});

test("each row knows the row it came from, for the dot's path", () => {
  assert.equal(prep.rows[1].prev, 0);
  assert.equal(prep.rows[2].prev, 0);
  assert.equal(prep.rows[3].prev, 2); // the check that ended last
  assert.equal(prep.rows[0].prev, null);
});

test("waiting dots sit in arrival order and the QC queue is counted", () => {
  const s = stateAt(prep, 13);
  assert.equal(s.waitCounts.Task_ReviewSourceCode, 1);
  assert.equal(s.counters.waitingQc, 1);
  assert.equal(stateAt(prep, 35).counters.waitingQc, 0);
});

test("a case counts as finished only if its cycle time ends inside the window", () => {
  assert.deepEqual(counters(prep, 24), { inProgress: 1, waitingQc: 0, finished: 0, meanCycle: null }); // case 2 went live before the window
  assert.deepEqual(counters(prep, 25), { inProgress: 0, waitingQc: 0, finished: 1, meanCycle: 20 });
  assert.deepEqual(counters(prep, 40), { inProgress: 1, waitingQc: 0, finished: 1, meanCycle: 20 });
});

test("a working dot turns 'live' once its case went live", () => {
  const monitor = stateAt(prep, 12).items.find((x) => x.task === "Task_MonitorOperation");
  assert.equal(monitor.live, true);
  const build = stateAt(prep, 11).items.find((x) => x.task === "Task_BuildApplication");
  assert.equal(build.live, false);
});

test("the QC series samples the queue over the window", () => {
  const series = qcQueueSeries(prep, 1);
  assert.equal(series.length, 31);
  assert.deepEqual(series.find(([t]) => t === 13), [13, 1]);
});

test("the clock counts months of 1/12 of a 250-day year", () => {
  const w = { start: 250, end: 625 };
  assert.deepEqual(clock(w, 250), { month: 1, totalMonths: 18, day: 0, totalDays: 375, progress: 0 });
  assert.equal(clock(w, 250 + MONTH * 6.5).month, 7);
  assert.equal(clock(w, 625).month, 18);
  assert.equal(clock(w, 700).progress, 1);
});

test("along walks a polyline by length", () => {
  const pts = [[0, 0], [10, 0], [10, 10]];
  assert.deepEqual(along(pts, 0), [0, 0]);
  assert.deepEqual(along(pts, 0.5), [10, 0]);
  assert.deepEqual(along(pts, 0.75), [10, 5]);
  assert.deepEqual(along(pts, 1), [10, 10]);
});

test("rest keeps what is left of a polyline, so a dot finishes its path before the next one", () => {
  const pts = [[0, 0], [10, 0], [10, 10]];
  assert.deepEqual(rest(pts, 0.25), [[5, 0], [10, 0], [10, 10]]);
  assert.deepEqual(rest(pts, 0.75), [[10, 5], [10, 10]]);
  assert.deepEqual(rest(pts, 1), [[10, 10]]);
  assert.deepEqual(rest(pts, 0), [[0, 0], [10, 0], [10, 10]]);
});

const replay = JSON.parse(fs.readFileSync(new URL("../web/demo/replay.json", import.meta.url)));

test("on the real replay, the counters at the end match the case list", () => {
  for (const s of replay.scenarios) {
    const p = prepare(s, replay.window);
    const { start, end } = replay.window;
    const done = s.cases.filter((c) => c.cycle_time != null && c.arrival + c.cycle_time >= start && c.arrival + c.cycle_time <= end);
    const c = counters(p, end);
    assert.equal(c.finished, done.length);
    assert.ok(Math.abs(c.meanCycle - done.reduce((x, d) => x + d.cycle_time, 0) / done.length) < 1e-9);
  }
});

test("on the real replay, the as-is QC queue is longer than the to-be one", () => {
  const avg = (s) => {
    const q = qcQueueSeries(prepare(s, replay.window), 1);
    return q.reduce((x, p) => x + p[1], 0) / q.length;
  };
  const [asIs, toBe] = replay.scenarios;
  assert.ok(avg(asIs) > 4 * avg(toBe));
});


// ---------- tokens move along the arcs, through gateways ----------

const flowsOf = (model, from, to) => route(buildLayout(model), from, to)?.flows;

test("a token goes from one task to the next through the gateways between them, along their arcs", () => {
  assert.deepEqual(flowsOf("as_is", "Start_RequestReceived", "Task_RegisterRequest"), ["Flow_RequestReceived"]);
  assert.deepEqual(flowsOf("as_is", "Task_FixDefects", "Task_ReviewSourceCode"), ["Flow_DefectsFixed", "Flow_TestsStarted"]);
  assert.deepEqual(flowsOf("as_is", "Task_RefineApplication", "Task_ReviewSourceCode"), ["Flow_ApplicationRefined", "Flow_ReleaseCandidateReady", "Flow_TestsStarted"]);
  // to-be: the AND-split sends the build's token to every check, the AND-join and the retest join lead on.
  assert.deepEqual(flowsOf("to_be", "Task_BuildApplication", "Task_RunSecurityTests"), ["Flow_ApplicationBuilt", "Flow_ReleaseCandidateReady", "Flow_SecurityTestsStarted"]);
  assert.deepEqual(flowsOf("to_be", "Task_ReviewSourceCode", "Task_ApproveRelease"), ["Flow_CodeReviewed", "Flow_ChecksCompleted", "Flow_TestRoundCompleted", "Flow_TestsPassed"]);
  assert.deepEqual(flowsOf("to_be", "Task_RetestFixedDefects", "Task_FixDefects"), ["Flow_DefectsRetested", "Flow_TestRoundCompleted", "Flow_DefectsFound"]);
});

test("a token never passes through a task on its way, and ends in an end event", () => {
  assert.equal(flowsOf("as_is", "Task_RegisterRequest", "Task_HoldKickOff"), undefined);
  const rejected = route(buildLayout("as_is"), "Task_ApproveProposal", null);
  assert.deepEqual([rejected.flows, rejected.target], [["Flow_ProposalDecided", "Flow_ProposalRejected"], "End_ProposalRejected"]);
  assert.equal(route(buildLayout("to_be"), "Task_EvaluateProject", null).target, "End_ProjectClosed");
  assert.equal(route(buildLayout("to_be"), "Task_BuildApplication", null), null);
});

test("on the real replay, every step of every project has a path along the arcs", () => {
  for (const s of replay.scenarios) {
    const p = prepare(s, replay.window);
    for (const metrics of ["normal", "compact"]) {
      const layout = buildLayout(s.id, metrics);
      assert.deepEqual(Object.keys(layout.boxes).sort(), [...s.tasks].sort());
      const pairs = new Set(p.rows.filter((r) => r.prev != null).map((r) => `${p.rows[r.prev].activity}>${r.activity}`));
      for (const pair of pairs) {
        const [from, to] = pair.split(">");
        const r = route(layout, from, to);
        assert.ok(r, `${s.id} ${pair}`);
        assert.deepEqual(r.pts[0], layout.flows[r.flows[0]].pts[0]);
        assert.deepEqual(r.pts.at(-1), layout.flows[r.flows.at(-1)].pts.at(-1));
      }
    }
  }
});

// ---------- the drawing ----------

const layouts = () => ["as_is", "to_be"].flatMap((model) => ["normal", "compact"].map((m) => buildLayout(model, m)));
const onBoundary = (n, [x, y]) => {
  if (n.type === "task") {
    const onX = Math.abs(x - n.left) < 0.5 || Math.abs(x - n.right) < 0.5, onY = Math.abs(y - n.top) < 0.5 || Math.abs(y - n.bottom) < 0.5;
    return (onX && y >= n.top - 0.5 && y <= n.bottom + 0.5) || (onY && x >= n.left - 0.5 && x <= n.right + 0.5);
  }
  if (n.type.endsWith("Gateway")) return Math.abs(Math.abs(x - n.cx) + Math.abs(y - n.cy) - n.r) < 0.5 && (Math.abs(x - n.cx) < 0.5 || Math.abs(y - n.cy) < 0.5);
  return Math.abs(Math.hypot(x - n.cx, y - n.cy) - n.r) < 0.5;
};

test("every arc is a solid orthogonal line from the edge of its source to the edge of its target", () => {
  for (const l of layouts()) {
    for (const f of Object.values(l.flows)) {
      assert.ok(onBoundary(l.nodes[f.source], f.pts[0]), `${l.model} ${f.id} start`);
      assert.ok(onBoundary(l.nodes[f.target], f.pts.at(-1)), `${l.model} ${f.id} end`);
      for (let k = 1; k < f.pts.length; k++) {
        const [a, b] = [f.pts[k - 1], f.pts[k]];
        assert.ok(Math.abs(a[0] - b[0]) < 0.01 || Math.abs(a[1] - b[1]) < 0.01, `${l.model} ${f.id} segment ${k}`);
      }
      const last = Math.hypot(f.pts.at(-1)[0] - f.pts.at(-2)[0], f.pts.at(-1)[1] - f.pts.at(-2)[1]);
      assert.ok(last >= 8, `${l.model} ${l.metrics.name} ${f.id}: the arrow head needs ${last} >= 8`);
    }
  }
});

test("no arc runs through an element it does not connect", () => {
  const crosses = (a, b, n, pad = 1) => {
    const [x0, x1] = [Math.min(a[0], b[0]), Math.max(a[0], b[0])], [y0, y1] = [Math.min(a[1], b[1]), Math.max(a[1], b[1])];
    return x1 > n.left + pad && x0 < n.right - pad && y1 > n.top + pad && y0 < n.bottom - pad;
  };
  for (const l of layouts()) {
    for (const f of Object.values(l.flows)) {
      for (const n of Object.values(l.nodes)) {
        if (n.id === f.source || n.id === f.target) continue;
        for (let k = 1; k < f.pts.length; k++) assert.ok(!crosses(f.pts[k - 1], f.pts[k], n), `${l.model} ${l.metrics.name} ${f.id} crosses ${n.id}`);
      }
    }
  }
});

test("every element sits inside its lane, right of the lane names, and no two overlap", () => {
  for (const l of layouts()) {
    const list = Object.values(l.nodes);
    for (const n of list) {
      const lane = l.lanes[n.lane];
      assert.ok(n.left > HEADER && n.right < WIDTH, n.id);
      assert.ok(n.top >= lane.top && n.bottom <= lane.bottom, `${l.model} ${l.metrics.name} ${n.id}`);
    }
    for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
      const [a, b] = [list[i], list[j]];
      const overlap = Math.min(a.right, b.right) - Math.max(a.left, b.left) > 0 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0;
      assert.ok(!overlap, `${l.model} ${a.id} / ${b.id}`);
    }
  }
});

test("dots stay in the box's strip below its label, waiting ones first, wrapping onto the next row", () => {
  for (const l of layouts()) {
    const m = l.metrics;
    for (const b of Object.values(l.boxes)) {
      const labelBottom = b.top + m.labelTop + m.labelH;
      for (let total = 1; total <= 24; total++) {
        const pts = Array.from({ length: total }, (_, k) => dotPosition(l, b.id, k, total));
        for (const [x, y] of pts) assert.ok(x - m.dot >= b.left && x + m.dot <= b.right && y - m.dot >= labelBottom && y + m.dot <= b.bottom, `${l.model} ${b.id} ${total}`);
        if (b.chip) for (const [x] of pts) assert.ok(x + m.dot <= b.chip.x - 1 || x - m.dot >= b.chip.x + CHIP.w + 1, `${b.id} dot on its chip`);
        // the first dot is bottom left; a full row wraps upwards
        assert.ok(pts.every(([x, y]) => y <= pts[0][1] && (y < pts[0][1] || x >= pts[0][0])));
      }
      const few = [0, 1, 2].map((k) => dotPosition(l, b.id, k, 3));
      assert.ok(few[0][0] < few[1][0] && few[1][0] < few[2][0] && few[0][1] === few[2][1], b.id);
    }
  }
});

test("a check that finished first waits on its arc just before the AND-join", () => {
  for (const m of ["normal", "compact"]) {
    const l = buildLayout("to_be", m);
    const join = l.nodes.Gateway_ChecksJoin;
    const spots = [0, 1, 2, 3, 4, 5].map((k) => parkPosition(l, "Task_RunSecurityTests", k));
    for (const [x, y] of spots) assert.ok(y === join.cy && x < join.left && x > l.nodes.Task_ReviewSourceCode.cx, `${x}`);
    assert.ok(spots.every((p, k) => k === 0 || spots[k - 1][0] - p[0] >= 2 * l.metrics.dot));
  }
  assert.equal(parkPosition(buildLayout("as_is"), "Task_RunSecurityTests", 0), null);
});

test("every lane is tall enough for its name and head count, the to-be QC lane also for the C4 chip", () => {
  const block = (lines) => TYPE.size * (TYPE.ascent + (lines - 1) * TYPE.line + TYPE.descent);
  for (const l of layouts()) {
    for (const lane of Object.values(l.lanes)) assert.ok(l.metrics.laneTop + block(3) + SPACE.xs <= lane.h, lane.id);
    if (l.model === "to_be") assert.ok(l.metrics.laneTop + block(3) + SPACE.s + CHIP.h <= l.lanes.Lane_QualityControl.h);
  }
});

test("the flow is narrow enough for 12 px text across a 1366 px screen (1360 px of panel)", () => {
  assert.ok((1360 / WIDTH) * TYPE.size >= 12, `width ${WIDTH}`);
});
