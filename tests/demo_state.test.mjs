// Node tests of the flow demo's state module (web/demo/state.js). Run by tests/test_demo.py,
// or directly: node --test tests/demo_state.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { prepare, stateAt, counters, qcQueueSeries, clock, along, MONTH } from "../web/demo/state.js";
import { buildLayout, dotPosition } from "../web/demo/layout.js";

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

const replay = JSON.parse(fs.readFileSync(new URL("../web/demo/replay.json", import.meta.url)));

test("on the real replay, every row's task has a place in its layout", () => {
  for (const s of replay.scenarios) {
    for (const metrics of ["normal", "compact"]) {
      const layout = buildLayout(s.id, metrics);
      assert.deepEqual(Object.keys(layout.boxes).sort(), [...s.tasks].sort());
      for (const r of s.rows.slice(0, 200)) assert.ok(dotPosition(layout, r.activity, "work", 0, 1));
    }
  }
});

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
