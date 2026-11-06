// Fixed layout of the two flows, keyed by the element IDs of models/as_is.bpmn and models/to_be.bpmn.
// Coordinates are SVG user units. Lane order and task lanes follow the BPMN files; a test
// (tests/test_demo.py) checks that every task of both models has a place here.
//
// Every size below comes from one type scale and one spacing scale. At 1366 px the flow is drawn
// at about 0.8 px per unit, so TYPE.sm renders at about 12 px; at 1920 px at about 1.15.

export const TYPE = {
  sm: 15, // people counts, loop rates, queue counts, change chips, notes
  md: 15.5, // task labels, band labels
  lg: 17, // lane names, go-live
  line: 1.2, // line height of two-line labels
  ascent: 0.97, // Be Vietnam Pro: top of the glyph box above the baseline, in em
  descent: 0.25,
};
export const SPACE = { xs: 2, s: 4, m: 8, l: 12, xl: 20 };

export const HEADER = 108; // lane name column: the widest lane word ("Nghiệp vụ") at TYPE.lg plus padding
export const PILL_H = 20;
export const BADGE_H = 16;
export const CHIP = { w: 30, h: 19 };
const BOX_PAD_X = 6;
const LABEL_H = (TYPE.ascent + TYPE.line + TYPE.descent) * TYPE.md; // two lines of a task label

export const LANES = ["Lane_BusinessUnit", "Lane_ITManagement", "Lane_Development", "Lane_QualityControl", "Lane_ITOperations"];

// normal: one flow on screen; compact: two flows stacked in compare mode. They differ only in
// vertical room: the lane padding and how many rows of dots a task box holds.
const MODES = {
  normal: { padTop: 6, padBottom: 4, rows: 2, dot: 4.2, laneTop: 16, laneBottom: 10, waitMax: 4 },
  compact: { padTop: 3, padBottom: 2, rows: 1, dot: 4, laneTop: 3, laneBottom: 2, waitMax: 2 },
};
const RAIL_GAP = SPACE.m; // to-be QC lane: from the shared line above the checks to their tops
const JOIN_GAP = SPACE.s; // and from their bottoms to the join line

export const METRICS = Object.fromEntries(Object.entries(MODES).map(([name, m]) => {
  const dotRow = 2 * m.dot + SPACE.xs;
  const boxH = Math.round(m.padTop + LABEL_H + SPACE.xs + BADGE_H + (m.rows - 1) * dotRow + m.padBottom);
  const lane = m.laneTop + boxH + m.laneBottom;
  // room under the join line for the hollow dots parked on it, inside the C1 frame
  const qcLane = m.laneTop + RAIL_GAP + boxH + JOIN_GAP + m.dot + SPACE.s + m.laneBottom;
  return [name, { ...m, name, boxH, dotRow, laneH: [lane, lane, lane, qcLane, lane], labelTop: m.padTop, labelH: LABEL_H }];
}));

const BU = "Lane_BusinessUnit", ITM = "Lane_ITManagement", DEV = "Lane_Development", QC = "Lane_QualityControl", OPS = "Lane_ITOperations";

// Box widths: the wider line of each two-line label at TYPE.md, measured in the page font, plus padding.
const W = {
  Task_RegisterRequest: 76, Task_ApproveProposal: 94, Task_ReviseProposal: 94, Task_HoldKickOff: 76,
  Task_SpecifyRequirements: 86, Task_DraftPlan: 108, Task_ApprovePlan: 108, Task_BuildApplication: 86,
  Task_ReviewSourceCode: 96, Task_RunFunctionalTests: 94, Task_RunSecurityTests: 80, Task_RunAcceptanceTests: 94,
  Task_FixDefects: 76, Task_RetestFixedDefects: 104, Task_ApproveRelease: 90, Task_RefineApplication: 96,
  Task_DeployApplication: 88, Task_StartOperation: 82, Task_MonitorOperation: 82, Task_EvaluateProject: 82,
};
const LANE_OF = {
  Task_RegisterRequest: BU, Task_ApproveProposal: ITM, Task_ReviseProposal: OPS, Task_HoldKickOff: BU,
  Task_SpecifyRequirements: BU, Task_DraftPlan: DEV, Task_ApprovePlan: ITM, Task_BuildApplication: DEV,
  Task_ReviewSourceCode: QC, Task_RunFunctionalTests: QC, Task_RunSecurityTests: QC, Task_RunAcceptanceTests: QC,
  Task_FixDefects: DEV, Task_RetestFixedDefects: QC, Task_ApproveRelease: ITM, Task_RefineApplication: DEV,
  Task_DeployApplication: OPS, Task_StartOperation: OPS, Task_MonitorOperation: OPS, Task_EvaluateProject: OPS,
};

// Horizontal placement, left to right. Each rule names the arrow or label it makes room for.
const GAP = SPACE.xl; // two boxes in one lane: room for an arrow
const CLEAR = SPACE.l; // an arrow passing a box corner
const DOWN_DX = 30; // an arrow into the next lane down enters this far right of the box centre
const UP_DX = 14; // an arrow into the next lane up
const PILL_RESERVE = { Gateway_PlanSplit: 94, Gateway_ReleaseSplit: 114 }; // the two loop rates set beside a box
const REJECT_HALF = 28; // half the width of the "rejected" label under its end event

function placeX() {
  const cx = {};
  const left = (id, x) => { cx[id] = x + W[id] / 2; };
  const L = (id) => cx[id] - W[id] / 2, R = (id) => cx[id] + W[id] / 2;
  const x = {};
  x.start = HEADER + SPACE.xl;
  left("Task_RegisterRequest", x.start + 9 + GAP);
  cx.Task_ApproveProposal = R("Task_RegisterRequest") + CLEAR - DOWN_DX;
  cx.Task_ReviseProposal = cx.Task_ApproveProposal; // the rework loop runs straight down and back
  x.reviseLoop = L("Task_ApproveProposal") - GAP;
  left("Task_HoldKickOff", Math.max(R("Task_RegisterRequest") + GAP, R("Task_ApproveProposal") + CLEAR - UP_DX - W.Task_HoldKickOff / 2));
  x.rejected = cx.Task_HoldKickOff + UP_DX + 26;
  // Specify leaves from its bottom-left corner, clear of the "rejected" label.
  left("Task_SpecifyRequirements", Math.max(R("Task_HoldKickOff") + GAP, x.rejected + REJECT_HALF + SPACE.m - 10));
  x.specifyExit = L("Task_SpecifyRequirements") + 10;
  left("Task_DraftPlan", x.specifyExit + GAP - 2);
  // The plan loop runs down from Approve plan's bottom-left into Draft plan; its rate sits left of
  // Approve plan, between the arrow from Specify and the box.
  left("Task_ApprovePlan", x.specifyExit + SPACE.m + PILL_RESERVE.Gateway_PlanSplit + SPACE.s);
  left("Task_BuildApplication", Math.max(cx.Task_ApprovePlan + UP_DX + CLEAR, R("Task_ApprovePlan") + CLEAR - DOWN_DX - W.Task_BuildApplication / 2));
  x.buildExit = cx.Task_BuildApplication - 2;
  left("Task_ReviewSourceCode", x.buildExit + GAP - 4);
  left("Task_RunFunctionalTests", R("Task_ReviewSourceCode") + GAP);
  left("Task_RunSecurityTests", R("Task_RunFunctionalTests") + GAP);
  left("Task_RunAcceptanceTests", R("Task_RunSecurityTests") + GAP);
  x.split = R("Task_RunAcceptanceTests") + 18;
  // to-be: the fix and retest column after the checks
  const retestCx = x.split + GAP + W.Task_RetestFixedDefects / 2;
  const fixRight = retestCx + W.Task_FixDefects / 2;
  // Approve release's loop rate sits left of the box, right of the arrow coming up from the split.
  const releaseLeft = Math.max(fixRight + GAP + (W.Task_RefineApplication - W.Task_ApproveRelease) / 2, x.split + SPACE.m + PILL_RESERVE.Gateway_ReleaseSplit + SPACE.s);
  cx.Task_ApproveRelease = releaseLeft + W.Task_ApproveRelease / 2;
  cx.Task_RefineApplication = cx.Task_ApproveRelease;
  cx.Task_DeployApplication = Math.max(R("Task_ApproveRelease"), R("Task_RefineApplication")) + CLEAR - DOWN_DX;
  left("Task_StartOperation", R("Task_DeployApplication") + GAP);
  x.goLive = R("Task_StartOperation") + 10;
  left("Task_MonitorOperation", x.goLive + 10);
  left("Task_EvaluateProject", R("Task_MonitorOperation") + GAP);
  x.closed = R("Task_EvaluateProject") + GAP + 2;
  x.width = Math.ceil(x.closed + 9 + SPACE.l);
  const as_is = { ...cx, Task_FixDefects: cx.Task_RunSecurityTests };
  const to_be = { ...cx, Task_FixDefects: retestCx, Task_RetestFixedDefects: retestCx };
  return { as_is, to_be, x };
}

const PLACE = placeX();
export const WIDTH = PLACE.x.width;
const CHECKS = ["Task_ReviewSourceCode", "Task_RunFunctionalTests", "Task_RunSecurityTests", "Task_RunAcceptanceTests"];

export function buildLayout(model, metricsName = "normal") {
  const m = METRICS[metricsName];
  const X = PLACE.x;
  const lanes = {};
  let y = 0;
  LANES.forEach((id, i) => {
    lanes[id] = { id, top: y, h: m.laneH[i], bottom: y + m.laneH[i] };
    y += m.laneH[i];
  });
  const height = y;
  const qc = lanes[QC];
  const railY = qc.top + m.laneTop; // to-be: shared line above the parallel checks
  const boxTop = (lane) => (lane === QC ? railY + RAIL_GAP : lanes[lane].top + m.laneTop);

  const boxes = {};
  for (const [id, cx] of Object.entries(PLACE[model])) {
    const lane = LANE_OF[id], w = W[id];
    const top = boxTop(lane), bottom = top + m.boxH;
    boxes[id] = { id, lane, cx, w, top, bottom, left: cx - w / 2, right: cx + w / 2, cy: (top + bottom) / 2, strip: strip(m, cx, w, bottom) };
  }
  const b = boxes;
  const joinY = b.Task_ReviewSourceCode.bottom + JOIN_GAP; // to-be: shared line below the checks
  const split = { x: X.split, y: b.Task_ReviewSourceCode.cy };
  const start = { x: X.start, y: b.Task_RegisterRequest.cy };
  const rejected = { x: X.rejected, y: b.Task_ApproveProposal.cy };
  const closed = { x: X.closed, y: b.Task_EvaluateProject.cy };

  // Edges carry their points; the page draws them with rounded corners and moves dots along them.
  // A loop's `label` is where its rate goes: on the arrow (anchor middle) or beside a box (anchor end).
  const edges = [];
  const add = (from, to, pts, extra = {}) => edges.push({ from, to, pts, ...extra });
  const top = (id, dx = DOWN_DX) => [b[id].cx + dx, b[id].top];
  const bottomAt = (id, dx) => [b[id].cx + dx, b[id].bottom];
  const leftMid = (id) => [b[id].left, b[id].cy];
  const rightMid = (id) => [b[id].right, b[id].cy];
  // Next lane down: leave the right side, enter from the top. Next lane up: leave the right side, enter from below.
  const down = (from, to) => add(from, to, [rightMid(from), [b[to].cx + DOWN_DX, b[from].cy], top(to)]);
  const up = (from, to) => add(from, to, [rightMid(from), [b[to].cx + UP_DX, b[from].cy], bottomAt(to, UP_DX)]);
  const same = (from, to) => add(from, to, [rightMid(from), leftMid(to)]);
  // A loop between two stacked boxes: down from the upper box's bottom-left corner, its rate to the left.
  const stackedLoop = (from, to, gateway) => {
    const x = b[from].left + SPACE.l;
    add(from, to, [[x, b[from].bottom], [x, b[to].top]],
      { loop: gateway, label: { x: b[from].left - SPACE.s, y: b[from].bottom - PILL_H / 2 - 1, anchor: "end" } });
  };

  add("start", "Task_RegisterRequest", [[start.x + 9, start.y], leftMid("Task_RegisterRequest")], { arrow: true });
  down("Task_RegisterRequest", "Task_ApproveProposal");
  up("Task_ApproveProposal", "Task_HoldKickOff");
  add("Task_ApproveProposal", "rejected", [rightMid("Task_ApproveProposal"), [rejected.x - 10, rejected.y]]);
  add("Task_ApproveProposal", "Task_ReviseProposal", [bottomAt("Task_ApproveProposal", DOWN_DX), top("Task_ReviseProposal")],
    { loop: "Gateway_ProposalSplit", label: { x: b.Task_ApproveProposal.cx + DOWN_DX, y: (lanes[DEV].top + lanes[DEV].bottom) / 2, anchor: "middle" } });
  add("Task_ReviseProposal", "Task_ApproveProposal",
    [leftMid("Task_ReviseProposal"), [X.reviseLoop, b.Task_ReviseProposal.cy], [X.reviseLoop, b.Task_ApproveProposal.cy], leftMid("Task_ApproveProposal")], { loop: true });
  same("Task_HoldKickOff", "Task_SpecifyRequirements");
  add("Task_SpecifyRequirements", "Task_DraftPlan",
    [[X.specifyExit, b.Task_SpecifyRequirements.bottom], [X.specifyExit, b.Task_DraftPlan.cy], leftMid("Task_DraftPlan")]);
  up("Task_DraftPlan", "Task_ApprovePlan");
  stackedLoop("Task_ApprovePlan", "Task_DraftPlan", "Gateway_PlanSplit");
  down("Task_ApprovePlan", "Task_BuildApplication");
  stackedLoop("Task_ApproveRelease", "Task_RefineApplication", "Gateway_ReleaseSplit");
  down("Task_ApproveRelease", "Task_DeployApplication");
  same("Task_DeployApplication", "Task_StartOperation");
  same("Task_StartOperation", "Task_MonitorOperation");
  same("Task_MonitorOperation", "Task_EvaluateProject");
  add("Task_EvaluateProject", "closed", [rightMid("Task_EvaluateProject"), [closed.x - 10, closed.y]]);

  const toRelease = [[split.x, split.y], [split.x, b.Task_ApproveRelease.cy], leftMid("Task_ApproveRelease")];
  const bands = [];
  const band = { x: b.Task_ReviewSourceCode.left - 10, w: b.Task_RunAcceptanceTests.right - b.Task_ReviewSourceCode.left + 20,
    label: [(b.Task_ReviewSourceCode.left + b.Task_RunAcceptanceTests.right) / 2, qc.bottom + SPACE.s + TYPE.ascent * TYPE.md] };
  const intoReview = (x) => [[x, qc.top], [X.buildExit, qc.top], [X.buildExit, b.Task_ReviewSourceCode.cy], leftMid("Task_ReviewSourceCode")];
  if (model === "as_is") {
    add("Task_BuildApplication", "Task_ReviewSourceCode", [[X.buildExit, b.Task_BuildApplication.bottom], [X.buildExit, b.Task_ReviewSourceCode.cy], leftMid("Task_ReviewSourceCode")]);
    for (let i = 0; i < 3; i++) same(CHECKS[i], CHECKS[i + 1]);
    add("Task_RunAcceptanceTests", "Task_ApproveRelease", [rightMid("Task_RunAcceptanceTests"), ...toRelease]);
    const fixRight = rightMid("Task_FixDefects");
    add("Task_RunAcceptanceTests", "Task_FixDefects",
      [rightMid("Task_RunAcceptanceTests"), [split.x, split.y], [split.x, b.Task_FixDefects.cy], fixRight],
      { loop: "Gateway_TestSplit", label: { x: (split.x + fixRight[0]) / 2, y: b.Task_FixDefects.cy, anchor: "middle" }, hot: true });
    const fixOut = b.Task_FixDefects.cx - 30, refineOut = b.Task_RefineApplication.cx - 30;
    add("Task_FixDefects", "Task_ReviewSourceCode", [[fixOut, b.Task_FixDefects.bottom], ...intoReview(fixOut)], { loop: true, hot: true });
    add("Task_RefineApplication", "Task_ReviewSourceCode", [[refineOut, b.Task_RefineApplication.bottom], ...intoReview(refineOut)], { loop: true });
    bands.push({ kind: "bottleneck", ...band, y: qc.top + SPACE.xs, h: qc.h - 2 * SPACE.xs });
  } else {
    const refineOut = [b.Task_RefineApplication.cx - 30, b.Task_RefineApplication.bottom];
    for (const c of CHECKS) {
      add("Task_BuildApplication", c, [[X.buildExit, b.Task_BuildApplication.bottom], [X.buildExit, railY], [b[c].cx + DOWN_DX, railY], top(c)]);
      add("Task_RefineApplication", c, [refineOut, [refineOut[0], railY], [b[c].cx + DOWN_DX, railY], top(c)], { loop: true, silent: true });
      const toJoin = [bottomAt(c, 0), [b[c].cx, joinY], [split.x, joinY], [split.x, split.y]];
      add(c, "join", toJoin, { line: true, noArrow: true });
      add(c, "Task_ApproveRelease", [...toJoin, ...toRelease.slice(1)], { silent: true });
      add(c, "Task_FixDefects", [...toJoin, [split.x, b.Task_FixDefects.cy], leftMid("Task_FixDefects")], { silent: true });
    }
    add("Task_RefineApplication", "rail", [refineOut, [refineOut[0], railY], [b.Task_ReviewSourceCode.cx + DOWN_DX, railY]], { loop: true, line: true, noArrow: true });
    add("join", "Task_FixDefects", [[split.x, split.y], [split.x, b.Task_FixDefects.cy], leftMid("Task_FixDefects")],
      { loop: "Gateway_TestSplit", label: { x: split.x - SPACE.m, y: b.Task_FixDefects.cy, anchor: "end" }, line: true });
    add("join", "Task_ApproveRelease", toRelease, { line: true });
    add("Task_FixDefects", "Task_RetestFixedDefects", [bottomAt("Task_FixDefects", DOWN_DX), top("Task_RetestFixedDefects")], { loop: true });
    const fromRetest = [leftMid("Task_RetestFixedDefects"), [split.x, split.y]];
    add("Task_RetestFixedDefects", "join", fromRetest, { loop: true, line: true });
    add("Task_RetestFixedDefects", "Task_ApproveRelease", [...fromRetest, ...toRelease.slice(1)], { silent: true });
    add("Task_RetestFixedDefects", "Task_FixDefects", [...fromRetest, [split.x, b.Task_FixDefects.cy], leftMid("Task_FixDefects")], { silent: true });
    bands.push({ kind: "change", change: "C1", ...band, y: qc.top + 1, h: qc.h - 2 });
  }

  return {
    model, metrics: m, width: WIDTH, height, lanes, boxes, edges, bands,
    markers: { start, rejected, closed, split, goLive: X.goLive },
    rails: model === "to_be" ? { railY, joinY, checks: CHECKS } : null,
    changed: model === "to_be" ? { Task_RetestFixedDefects: "C2", Task_SpecifyRequirements: "C3" } : {},
  };
}

// The status strip along the bottom of a task box: the queue count and waiting dots on the left,
// the dots being worked on to the right of them. Rows are listed bottom-up.
function strip(m, cx, w, bottom) {
  const y0 = bottom - m.padBottom - BADGE_H / 2;
  return { x0: cx - w / 2 + BOX_PAD_X, x1: cx + w / 2 - BOX_PAD_X, rows: Array.from({ length: m.rows }, (_, k) => y0 - k * m.dotRow) };
}

export const badgeWidth = (n) => (n >= 10 ? 28 : 20);
const queueWidth = (m, waiting) => badgeWidth(waiting) + SPACE.xs + Math.min(waiting, m.waitMax) * m.dot * 2.3 + SPACE.xs;

// Where a dot sits: in its task's strip while worked on or waiting (past the visible queue only
// the count shows it), and (to-be checks) on the join line while the other checks of its round finish.
// `waiting` is how many wait at the task: the queue takes the bottom row, so the worked-on dots go
// to the row above it (normal) or to the right of it (compact, one row).
export function dotPosition(layout, task, mode, slot, count, waiting = 0) {
  const box = layout.boxes[task];
  const m = layout.metrics;
  if (!box) return null;
  const r = m.dot, step = r * 2.3, s = box.strip;
  if (mode === "wait") {
    if (slot >= m.waitMax) return null;
    return [s.x0 + badgeWidth(count) + SPACE.xs + r + slot * step, s.rows[0]];
  }
  if (mode === "work") {
    let rows = s.rows.map((y) => ({ y, x0: s.x0 }));
    if (waiting > 0) {
      const beside = { y: s.rows[0], x0: Math.min(s.x0 + queueWidth(m, waiting), s.x1 - 2 * r) };
      const room = s.x1 - (s.x0 + queueWidth(m, waiting)) >= 2 * r;
      // the rows above the queue first, then what is left of its own row
      rows = rows.length > 1 && !room ? rows.slice(1) : [...rows.slice(1), beside];
    }
    // Fill rows in order; past the last row, squeeze the dots of the last row together.
    let first = 0;
    for (let k = 0; k < rows.length; k++) {
      const { y, x0 } = rows[k];
      const cap = Math.max(1, Math.floor((s.x1 - x0 - 2 * r) / step) + 1);
      const last = k === rows.length - 1;
      const inRow = last ? count - first : Math.min(cap, count - first);
      if (slot < first + inRow) {
        const st = inRow > 1 ? Math.min(step, (s.x1 - x0 - 2 * r) / (inRow - 1)) : 0;
        return [(x0 + s.x1) / 2 - ((inRow - 1) * st) / 2 + (slot - first) * st, y];
      }
      first += inRow;
    }
  }
  // park
  if (layout.rails && layout.rails.checks.includes(task)) return [box.cx - 28 - slot * step, layout.rails.joinY];
  return [box.right + 6, Math.max(box.top + r, box.bottom - r - 3 - slot * step)];
}
