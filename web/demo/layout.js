// Fixed layout of the two flows, keyed by the element IDs of models/as_is.bpmn and models/to_be.bpmn.
// Coordinates are SVG user units. Lane order and task lanes follow the BPMN files; a test
// (tests/test_demo.py) checks that every task of both models has a place here.

export const WIDTH = 1790;
export const HEADER = 112; // lane name column

export const LANES = ["Lane_BusinessUnit", "Lane_ITManagement", "Lane_Development", "Lane_QualityControl", "Lane_ITOperations"];

// normal: one flow on screen; compact: two flows stacked in compare mode.
export const METRICS = {
  normal: { laneH: [96, 96, 96, 116, 96], boxH: 62, pad: 10, font: 16.5, trayRows: [2, 2, 2, 3, 2], dot: 4.2 },
  compact: { laneH: [66, 66, 66, 82, 66], boxH: 52, pad: 6, font: 15, trayRows: [1, 1, 1, 2, 1], dot: 4 },
};

const BU = "Lane_BusinessUnit", ITM = "Lane_ITManagement", DEV = "Lane_Development", QC = "Lane_QualityControl", OPS = "Lane_ITOperations";

const COMMON = {
  Task_RegisterRequest: [BU, 200],
  Task_ApproveProposal: [ITM, 266],
  Task_ReviseProposal: [OPS, 266],
  Task_HoldKickOff: [BU, 332],
  Task_SpecifyRequirements: [BU, 444],
  Task_DraftPlan: [DEV, 510],
  Task_ApprovePlan: [ITM, 576],
  Task_BuildApplication: [DEV, 642],
  Task_ReviewSourceCode: [QC, 720],
  Task_RunFunctionalTests: [QC, 832],
  Task_RunSecurityTests: [QC, 944],
  Task_RunAcceptanceTests: [QC, 1056],
  Task_ApproveRelease: [ITM, 1290],
  Task_RefineApplication: [DEV, 1290],
  Task_DeployApplication: [OPS, 1380],
  Task_StartOperation: [OPS, 1492],
  Task_MonitorOperation: [OPS, 1606, 92],
  Task_EvaluateProject: [OPS, 1710, 92],
};

const TASKS = {
  as_is: { ...COMMON, Task_FixDefects: [DEV, 944] },
  to_be: { ...COMMON, Task_FixDefects: [DEV, 1190], Task_RetestFixedDefects: [QC, 1190] },
};

const CHECKS = ["Task_ReviewSourceCode", "Task_RunFunctionalTests", "Task_RunSecurityTests", "Task_RunAcceptanceTests"];
const SPLIT_X = 1120; // the decision after testing (as-is) / the join of the parallel checks (to-be)
const GO_LIVE_X = 1550;

export function buildLayout(model, metricsName = "normal") {
  const m = METRICS[metricsName];
  const lanes = {};
  let y = 0;
  LANES.forEach((id, i) => {
    lanes[id] = { id, top: y, h: m.laneH[i], bottom: y + m.laneH[i], trayRows: m.trayRows[i] };
    y += m.laneH[i];
  });
  const height = y;

  const boxes = {};
  for (const [id, [lane, cx, w = 96]] of Object.entries(TASKS[model])) {
    const L = lanes[lane];
    const bottom = L.bottom - m.pad, top = bottom - m.boxH;
    boxes[id] = { id, lane, cx, w, top, bottom, left: cx - w / 2, right: cx + w / 2, cy: (top + bottom) / 2, trayRows: L.trayRows };
  }
  const b = boxes;
  const cy = (lane) => b[Object.keys(b).find((k) => b[k].lane === lane)].cy;
  const qc = lanes[QC];
  const railY = qc.top + 7; // to-be: shared line above the parallel checks
  const joinY = qc.bottom - 4; // to-be: shared line below them
  const split = { x: SPLIT_X, y: cy(QC) };
  const start = { x: 132, y: cy(BU) };
  const rejected = { x: 380, y: cy(ITM) };
  const closed = { x: 1772, y: cy(OPS) };

  // Edges carry their points; the page draws them with rounded corners and moves dots along them.
  const edges = [];
  const add = (from, to, pts, extra = {}) => edges.push({ from, to, pts, ...extra });
  const top = (id, dx = 30) => [b[id].cx + dx, b[id].top];
  const bottomAt = (id, dx) => [b[id].cx + dx, b[id].bottom];
  const leftMid = (id) => [b[id].left, b[id].cy];
  const rightMid = (id) => [b[id].right, b[id].cy];
  // Next lane down: leave the right side, enter from the top. Next lane up: leave the right side, enter from below.
  const down = (from, to) => add(from, to, [rightMid(from), [b[to].cx + 30, b[from].cy], top(to)]);
  const up = (from, to) => add(from, to, [rightMid(from), [b[to].cx + 14, b[from].cy], bottomAt(to, 14)]);
  const same = (from, to) => add(from, to, [rightMid(from), leftMid(to)]);

  add("start", "Task_RegisterRequest", [[start.x + 9, start.y], leftMid("Task_RegisterRequest")], { arrow: true });
  down("Task_RegisterRequest", "Task_ApproveProposal");
  up("Task_ApproveProposal", "Task_HoldKickOff");
  add("Task_ApproveProposal", "rejected", [rightMid("Task_ApproveProposal"), [rejected.x - 10, rejected.y]]);
  add("Task_ApproveProposal", "Task_ReviseProposal", [bottomAt("Task_ApproveProposal", 30), top("Task_ReviseProposal")],
    { loop: "Gateway_ProposalSplit", label: [296, cy(DEV)] });
  add("Task_ReviseProposal", "Task_ApproveProposal",
    [leftMid("Task_ReviseProposal"), [196, b.Task_ReviseProposal.cy], [196, b.Task_ApproveProposal.cy], leftMid("Task_ApproveProposal")], { loop: true });
  same("Task_HoldKickOff", "Task_SpecifyRequirements");
  add("Task_SpecifyRequirements", "Task_DraftPlan",
    [bottomAt("Task_SpecifyRequirements", -24), [420, b.Task_DraftPlan.cy], leftMid("Task_DraftPlan")]);
  up("Task_DraftPlan", "Task_ApprovePlan");
  add("Task_ApprovePlan", "Task_DraftPlan", [bottomAt("Task_ApprovePlan", -36), top("Task_DraftPlan")],
    { loop: "Gateway_PlanSplit", label: [540, lanes[DEV].top + 2] });
  down("Task_ApprovePlan", "Task_BuildApplication");
  add("Task_ApproveRelease", "Task_RefineApplication", [bottomAt("Task_ApproveRelease", 30), top("Task_RefineApplication")],
    { loop: "Gateway_ReleaseSplit", label: [1320, lanes[DEV].top + 2] });
  down("Task_ApproveRelease", "Task_DeployApplication");
  same("Task_DeployApplication", "Task_StartOperation");
  same("Task_StartOperation", "Task_MonitorOperation");
  same("Task_MonitorOperation", "Task_EvaluateProject");
  add("Task_EvaluateProject", "closed", [rightMid("Task_EvaluateProject"), [closed.x - 10, closed.y]]);

  const toRelease = [[split.x, split.y], [split.x, b.Task_ApproveRelease.cy], leftMid("Task_ApproveRelease")];
  const bands = [];
  if (model === "as_is") {
    const intoReview = (x, yFrom) => [[x, yFrom], [640, qc.top], [640, b.Task_ReviewSourceCode.cy], leftMid("Task_ReviewSourceCode")];
    add("Task_BuildApplication", "Task_ReviewSourceCode", [bottomAt("Task_BuildApplication", -2), [640, b.Task_ReviewSourceCode.cy], leftMid("Task_ReviewSourceCode")]);
    for (let i = 0; i < 3; i++) same(CHECKS[i], CHECKS[i + 1]);
    add("Task_RunAcceptanceTests", "Task_ApproveRelease", [rightMid("Task_RunAcceptanceTests"), ...toRelease]);
    add("Task_RunAcceptanceTests", "Task_FixDefects",
      [rightMid("Task_RunAcceptanceTests"), [split.x, split.y], [split.x, b.Task_FixDefects.cy], rightMid("Task_FixDefects")],
      { loop: "Gateway_TestSplit", label: [split.x, qc.top - 20], hot: true });
    add("Task_FixDefects", "Task_ReviewSourceCode", [bottomAt("Task_FixDefects", -30), [914, qc.top], ...intoReview(914, qc.top).slice(1)], { loop: true, hot: true });
    add("Task_RefineApplication", "Task_ReviewSourceCode", [bottomAt("Task_RefineApplication", -30), [1260, qc.top], ...intoReview(1260, qc.top).slice(1)], { loop: true });
    bands.push({ kind: "bottleneck", x: b.Task_ReviewSourceCode.left - 10, y: qc.top + 3, w: b.Task_RunAcceptanceTests.right - b.Task_ReviewSourceCode.left + 20, h: qc.h - 6,
      label: [(b.Task_ReviewSourceCode.left + b.Task_RunAcceptanceTests.right) / 2, qc.bottom + 18] });
  } else {
    for (const c of CHECKS) {
      add("Task_BuildApplication", c, [bottomAt("Task_BuildApplication", -2), [640, railY], [b[c].cx + 30, railY], top(c)]);
      add("Task_RefineApplication", c, [bottomAt("Task_RefineApplication", -30), [1260, railY], [b[c].cx + 30, railY], top(c)], { loop: true, silent: true });
      const toJoin = [bottomAt(c, 0), [b[c].cx, joinY], [split.x, joinY], [split.x, split.y]];
      add(c, "join", toJoin, { line: true, noArrow: true });
      add(c, "Task_ApproveRelease", [...toJoin, ...toRelease.slice(1)], { silent: true });
      add(c, "Task_FixDefects", [...toJoin, [split.x, b.Task_FixDefects.cy], leftMid("Task_FixDefects")], { silent: true });
    }
    add("Task_RefineApplication", "rail", [bottomAt("Task_RefineApplication", -30), [1260, railY], [b.Task_ReviewSourceCode.cx + 30, railY]], { loop: true, line: true, noArrow: true });
    add("join", "Task_FixDefects", [[split.x, split.y], [split.x, b.Task_FixDefects.cy], leftMid("Task_FixDefects")],
      { loop: "Gateway_TestSplit", label: [split.x - 58, b.Task_FixDefects.cy], line: true });
    add("join", "Task_ApproveRelease", toRelease, { line: true });
    add("Task_FixDefects", "Task_RetestFixedDefects", [bottomAt("Task_FixDefects", 30), top("Task_RetestFixedDefects")], { loop: true });
    const fromRetest = [leftMid("Task_RetestFixedDefects"), [split.x, split.y]];
    add("Task_RetestFixedDefects", "join", fromRetest, { loop: true, line: true });
    add("Task_RetestFixedDefects", "Task_ApproveRelease", [...fromRetest, ...toRelease.slice(1)], { silent: true });
    add("Task_RetestFixedDefects", "Task_FixDefects", [...fromRetest, [split.x, b.Task_FixDefects.cy], leftMid("Task_FixDefects")], { silent: true });
    bands.push({ kind: "change", change: "C1", x: b.Task_ReviewSourceCode.left - 10, y: qc.top + 1, w: b.Task_RunAcceptanceTests.right - b.Task_ReviewSourceCode.left + 20, h: qc.h - 2,
      label: [(b.Task_ReviewSourceCode.left + b.Task_RunAcceptanceTests.right) / 2, qc.bottom + 18] });
  }

  return {
    model, metrics: m, width: WIDTH, height, lanes, boxes, edges, bands,
    markers: { start, rejected, closed, split, goLive: GO_LIVE_X },
    rails: model === "to_be" ? { railY, joinY, checks: CHECKS } : null,
    changed: model === "to_be" ? { Task_RetestFixedDefects: "C2", Task_SpecifyRequirements: "C3" } : {},
  };
}

// Where a dot sits: on its task while worked on, in the tray above it while waiting,
// and (to-be checks) on the join line while the other checks of its round finish.
export function dotPosition(layout, task, mode, slot, count) {
  const box = layout.boxes[task];
  const m = layout.metrics;
  if (!box) return null;
  const step = m.dot * 2.3;
  if (mode === "work") {
    const perRow = 9, n = Math.min(count, perRow);
    const row = Math.floor(slot / perRow), col = slot % perRow;
    return [box.cx - ((n - 1) * step) / 2 + col * step, box.bottom - m.dot - 5 - row * step];
  }
  if (mode === "wait") {
    const perRow = 5, row = Math.floor(slot / perRow);
    if (row >= box.trayRows) return null; // beyond the tray: only the count shows it
    return [box.cx - 20 + (slot % perRow) * step, box.top - m.dot - 3 - row * step];
  }
  // park
  if (layout.rails && layout.rails.checks.includes(task)) return [box.cx - 28 - slot * step, layout.rails.joinY];
  return [box.right + 6, box.cy - slot * step];
}
