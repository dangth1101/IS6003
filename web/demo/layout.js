// Fixed layout of the two flows in BPMN notation (Dumas et al., ch. 3), keyed by the element and
// flow IDs of models/as_is.bpmn and models/to_be.bpmn. tests/test_demo.py checks that the nodes
// (type and lane) and the sequence flows here are exactly the model's, so the page can't drift.
//
// Coordinates are SVG user units. At 1366 px in compare mode the flow is drawn at about 0.78 px per
// unit, so the one text size (TYPE.size) renders at about 12 px. Every gap below is spent with that
// budget in mind: a test fails if the flow gets too wide for 12 px text.

export const TYPE = {
  size: 15.5, // every text on the flow: labels, lane names, conditions, counts, chips
  pool: 17, // the pool name in its band
  line: 1.2, // line height of two-line labels
  ascent: 0.97, // Be Vietnam Pro: top of the glyph box above the baseline, in em
  descent: 0.25,
};
export const SPACE = { xs: 2, s: 4, m: 8, l: 12, xl: 20 };

export const POOL_W = 20; // the pool's name band (vertical text)
export const HEADER = 108; // pool band plus the lane name column
export const GW = 11; // half the width of a gateway diamond
export const EV = 9; // radius of an event circle
export const CHIP = { w: 30, h: 19 };
const ARROW = 12; // shortest arrow segment
const CLEAR = 12; // a vertical leg passing a box edge
const BOX_GAP = 12; // two boxes next to each other in one lane
const LABEL_H = (TYPE.ascent + TYPE.line + TYPE.descent) * TYPE.size; // two lines of a task label

export const LANES = ["Lane_BusinessUnit", "Lane_ITManagement", "Lane_Development", "Lane_QualityControl", "Lane_ITOperations"];
const BU = "Lane_BusinessUnit", ITM = "Lane_ITManagement", DEV = "Lane_Development", QC = "Lane_QualityControl", OPS = "Lane_ITOperations";

// normal: one flow on screen; compact: two flows stacked in compare mode. They differ only in
// vertical room. A task box holds its label and, under it, `rows` rows of dots.
const MODES = {
  normal: { padTop: 6, padBottom: 4, rows: 3, dot: 4.2, laneTop: 14, laneBottom: 10 },
  compact: { padTop: 3, padBottom: 2, rows: 2, dot: 4, laneTop: 3, laneBottom: 2 },
};
const RAIL = 10; // QC lane: from the rail above the checks to their tops
const UNDER = 8; // to-be QC lane: from the checks' bottoms to the line of the join gateways
const CHANNEL = 7; // QC lane: the loop back from "Hoàn thiện ứng dụng" runs this far under the lowest element

export const METRICS = Object.fromEntries(Object.entries(MODES).map(([name, m]) => {
  const dotStep = 2 * m.dot + 1;
  const boxH = Math.round(m.padTop + LABEL_H + SPACE.xs + 2 * m.dot + (m.rows - 1) * dotStep + m.padBottom);
  const lane = m.laneTop + boxH + m.laneBottom;
  const qc = {
    as_is: m.laneTop + RAIL + boxH + CHANNEL + 1 + m.laneBottom,
    to_be: m.laneTop + RAIL + boxH + UNDER + 2 * GW + CHANNEL + 3 + m.laneBottom,
  };
  return [name, { ...m, name, boxH, dotStep, lane, qc, labelTop: m.padTop, labelH: LABEL_H }];
}));

// Box widths: the wider line of each label (two lines, split as in demo.vi.json) at TYPE.size,
// weight 600, measured in the page font, plus 6 units of padding on each side.
const W = {
  Task_RegisterRequest: 76, Task_ApproveProposal: 71, Task_ReviseProposal: 71, Task_HoldKickOff: 76,
  Task_SpecifyRequirements: 85, Task_DraftPlan: 83, Task_ApprovePlan: 83, Task_BuildApplication: 85,
  Task_ReviewSourceCode: 88, Task_RunFunctionalTests: 93, Task_RunSecurityTests: 80, Task_RunAcceptanceTests: 93,
  Task_FixDefects: 64, Task_RetestFixedDefects: 103, Task_ApproveRelease: 90, Task_RefineApplication: 96,
  Task_DeployApplication: 88, Task_StartOperation: 82, Task_MonitorOperation: 82, Task_EvaluateProject: 82,
};
const COND_W = { loopTest: 93, approved: 88 }; // label widths: "có lỗi (37%)" above the arc into "Sửa lỗi", "được duyệt"

// The elements of each model: BPMN type and lane, as in the .bpmn files.
const COMMON = {
  Start_RequestReceived: ["startEvent", BU], Task_RegisterRequest: ["task", BU], Gateway_ProposalJoin: ["exclusiveGateway", ITM],
  Task_ApproveProposal: ["task", ITM], Gateway_ProposalSplit: ["exclusiveGateway", ITM], Task_ReviseProposal: ["task", OPS],
  End_ProposalRejected: ["endEvent", ITM], Task_HoldKickOff: ["task", BU], Task_SpecifyRequirements: ["task", BU],
  Gateway_PlanJoin: ["exclusiveGateway", DEV], Task_DraftPlan: ["task", DEV], Task_ApprovePlan: ["task", ITM],
  Gateway_PlanSplit: ["exclusiveGateway", ITM], Task_BuildApplication: ["task", DEV], Gateway_ReleaseJoin: ["exclusiveGateway", QC],
  Task_ReviewSourceCode: ["task", QC], Task_RunFunctionalTests: ["task", QC], Task_RunSecurityTests: ["task", QC],
  Task_RunAcceptanceTests: ["task", QC], Gateway_TestSplit: ["exclusiveGateway", QC], Task_FixDefects: ["task", DEV],
  Task_ApproveRelease: ["task", ITM], Gateway_ReleaseSplit: ["exclusiveGateway", ITM], Task_RefineApplication: ["task", DEV],
  Task_DeployApplication: ["task", OPS], Task_StartOperation: ["task", OPS], Task_MonitorOperation: ["task", OPS],
  Task_EvaluateProject: ["task", OPS], End_ProjectClosed: ["endEvent", OPS],
};
const NODES = {
  as_is: { ...COMMON, Gateway_TestJoin: ["exclusiveGateway", QC] },
  to_be: {
    ...COMMON, Gateway_ChecksSplit: ["parallelGateway", QC], Gateway_ChecksJoin: ["parallelGateway", QC],
    Gateway_RetestJoin: ["exclusiveGateway", QC], Task_RetestFixedDefects: ["task", QC],
  },
};
// Chips on changed tasks, in the bottom right corner of the box.
const CHANGED = { as_is: {}, to_be: { Task_RetestFixedDefects: "C2", Task_SpecifyRequirements: "C3" } };
const CHECKS = ["Task_ReviewSourceCode", "Task_RunFunctionalTests", "Task_RunSecurityTests", "Task_RunAcceptanceTests"];

// Horizontal placement, left to right. Each rule names the arrow or label it makes room for.
function placeX(model) {
  const x = {}; // centre x of every node
  const w = (id) => W[id] ?? (id.startsWith("Gateway") ? 2 * GW : 2 * EV);
  const L = (id) => x[id] - w(id) / 2, R = (id) => x[id] + w(id) / 2;
  const left = (id, at) => { x[id] = at + w(id) / 2; };
  const c = {}; // named leg positions

  x.Start_RequestReceived = HEADER + 6 + EV;
  left("Task_RegisterRequest", R("Start_RequestReceived") + ARROW);
  x.Gateway_ProposalJoin = L("Task_RegisterRequest") + 14; // straight down from the request box
  left("Task_ApproveProposal", R("Gateway_ProposalJoin") + ARROW);
  x.Gateway_ProposalSplit = R("Task_ApproveProposal") + ARROW + GW;
  x.Task_ReviseProposal = x.Gateway_ProposalSplit; // straight down: "cần sửa"
  x.End_ProposalRejected = R("Gateway_ProposalSplit") + ARROW + EV;
  // straight up, then right: "được duyệt" sits above that corner, right of the request box
  left("Task_HoldKickOff", Math.max(x.Gateway_ProposalSplit + ARROW, R("Task_RegisterRequest") + COND_W.approved + 2 * SPACE.s));
  left("Task_SpecifyRequirements", R("Task_HoldKickOff") + BOX_GAP);
  c.specifyExit = R("Task_SpecifyRequirements") - CLEAR; // down into the plan join's left corner
  x.Gateway_PlanJoin = c.specifyExit + ARROW + GW;
  left("Task_DraftPlan", R("Gateway_PlanJoin") + ARROW);
  c.draftUp = R("Task_DraftPlan") + ARROW + 1; // up into the plan approval's bottom
  left("Task_ApprovePlan", c.draftUp - 20);
  x.Gateway_PlanSplit = R("Task_ApprovePlan") + ARROW + GW;
  x.Task_BuildApplication = x.Gateway_PlanSplit; // straight down: "được duyệt"
  x.Gateway_ReleaseJoin = L("Task_BuildApplication") + 14; // straight down from the build box
  const second = x.Gateway_ReleaseJoin + 2 * GW + ARROW; // the test join (as-is) or the AND-split (to-be)
  left("Task_ReviewSourceCode", second + GW + ARROW);
  for (let k = 1; k < 4; k++) left(CHECKS[k], R(CHECKS[k - 1]) + BOX_GAP);
  const a = R("Task_RunAcceptanceTests");

  if (model === "as_is") {
    x.Gateway_TestJoin = second;
    x.Gateway_TestSplit = a + ARROW + GW;
    // "có lỗi" runs up and left into the fix box, which sits above the checks; its label goes above that arc.
    x.Task_FixDefects = x.Gateway_TestSplit - COND_W.loopTest - SPACE.s - W.Task_FixDefects / 2;
  } else {
    x.Gateway_ChecksSplit = second;
    x.Gateway_ChecksJoin = a - 10; // on the line under the checks, below the acceptance box's right end
    left("Task_RetestFixedDefects", a + ARROW + 1);
    x.Gateway_RetestJoin = L("Task_RetestFixedDefects") + 12; // straight down from the retest box
    x.Task_FixDefects = x.Gateway_RetestJoin + 5 - W.Task_FixDefects / 2; // straight down into the retest box
    x.Gateway_TestSplit = Math.max(R("Task_RetestFixedDefects") + CLEAR, R("Task_FixDefects") + COND_W.loopTest + SPACE.s);
  }
  // After the tests: "đạt" leaves the split's right corner and runs up into the release approval.
  c.passUp = x.Gateway_TestSplit + GW + ARROW;
  left("Task_ApproveRelease", c.passUp - 20);
  left("Task_RefineApplication", c.passUp + CLEAR);
  c.refineIn = R("Task_RefineApplication") - 14; // "bị từ chối" comes down into it from above
  x.Gateway_ReleaseSplit = Math.max(c.refineIn + CLEAR + GW, R("Task_ApproveRelease") + ARROW + GW, R("Task_RefineApplication") + CLEAR);
  x.Task_DeployApplication = x.Gateway_ReleaseSplit; // straight down: "được duyệt"
  left("Task_StartOperation", R("Task_DeployApplication") + BOX_GAP);
  c.goLive = R("Task_StartOperation") + 7;
  left("Task_MonitorOperation", R("Task_StartOperation") + BOX_GAP);
  left("Task_EvaluateProject", R("Task_MonitorOperation") + BOX_GAP - 2);
  x.End_ProjectClosed = R("Task_EvaluateProject") + ARROW + EV;
  c.width = Math.ceil(R("End_ProjectClosed") + 6); // clear of the go-live frame and the pool edge
  return { x, c };
}

const PLACE = { as_is: placeX("as_is"), to_be: placeX("to_be") };
// Both flows share one width, so in compare mode they are drawn at the same scale.
export const WIDTH = Math.max(PLACE.as_is.c.width, PLACE.to_be.c.width);

export function buildLayout(model, metricsName = "normal") {
  const m = METRICS[metricsName];
  const { x, c } = PLACE[model];
  const lanes = {};
  let y = 0;
  for (const id of LANES) {
    const h = id === QC ? m.qc[model] : m.lane;
    lanes[id] = { id, top: y, h, bottom: y + h };
    y += h;
  }
  const height = y;
  const qc = lanes[QC];
  const boxTop = (lane) => lanes[lane].top + m.laneTop + (lane === QC ? RAIL : 0);
  const railY = boxTop(QC) - RAIL + 1; // the line above the checks
  const q1 = boxTop(QC) + m.boxH / 2; // centre line of the QC boxes
  const under = boxTop(QC) + m.boxH + UNDER + GW; // to-be: line of the join gateways under the checks
  const channel = (model === "to_be" ? under + GW + 2 : boxTop(QC) + m.boxH) + CHANNEL; // the refine loop

  const nodes = {};
  for (const [id, [type, lane]] of Object.entries(NODES[model])) {
    const cx = x[id];
    let cy = boxTop(lane) + m.boxH / 2;
    if (model === "to_be" && ["Gateway_ChecksJoin", "Gateway_RetestJoin", "Gateway_TestSplit"].includes(id)) cy = under;
    const n = { id, type, lane, cx, cy };
    if (type === "task") {
      const w = W[id], top = boxTop(lane);
      Object.assign(n, { w, top, bottom: top + m.boxH, left: cx - w / 2, right: cx + w / 2 });
      n.strip = strip(m, n, !!CHANGED[model][id]);
      if (CHANGED[model][id]) n.chip = { x: n.right - CHIP.w - 3, y: n.bottom - CHIP.h - 3 };
    } else {
      const r = type.endsWith("Gateway") ? GW : EV;
      Object.assign(n, { r, top: cy - r, bottom: cy + r, left: cx - r, right: cx + r });
    }
    nodes[id] = n;
  }
  const N = nodes;
  const top = (id, dx = 0) => [N[id].cx + dx, N[id].top];
  const bottom = (id, dx = 0) => [N[id].cx + dx, N[id].bottom];
  const leftMid = (id) => [N[id].left, N[id].cy];
  const rightMid = (id) => [N[id].right, N[id].cy];
  const at = (px, id) => [px, N[id].cy];

  // Sequence flows, by BPMN ID. `label` is where the condition of an XOR-split arc goes.
  const flows = {};
  let c1 = null;
  const flow = (id, source, target, pts, extra = {}) => { flows[id] = { id, source, target, pts, ...extra }; };
  const lab = (px, py, anchor = "start") => ({ x: px, y: py, anchor });
  const above = (py) => py - SPACE.s - 3 - TYPE.descent * TYPE.size; // baseline of a label just above a line at py
  const lowInLane = (lane) => lanes[lane].bottom - TYPE.descent * TYPE.size - 2; // baseline at the bottom of a lane
  const besideLeg = (lane) => lanes[lane].top + lanes[lane].h / 2 + 0.36 * TYPE.size; // mid-lane baseline

  flow("Flow_RequestReceived", "Start_RequestReceived", "Task_RegisterRequest", [rightMid("Start_RequestReceived"), leftMid("Task_RegisterRequest")]);
  flow("Flow_RequestRegistered", "Task_RegisterRequest", "Gateway_ProposalJoin", [bottom("Task_RegisterRequest", x.Gateway_ProposalJoin - x.Task_RegisterRequest), top("Gateway_ProposalJoin")]);
  flow("Flow_ProposalSubmitted", "Gateway_ProposalJoin", "Task_ApproveProposal", [rightMid("Gateway_ProposalJoin"), leftMid("Task_ApproveProposal")]);
  flow("Flow_ProposalDecided", "Task_ApproveProposal", "Gateway_ProposalSplit", [rightMid("Task_ApproveProposal"), leftMid("Gateway_ProposalSplit")]);
  const ps = N.Gateway_ProposalSplit;
  flow("Flow_ProposalApproved", "Gateway_ProposalSplit", "Task_HoldKickOff", [top("Gateway_ProposalSplit"), at(ps.cx, "Task_HoldKickOff"), leftMid("Task_HoldKickOff")],
    { label: lab(N.Task_HoldKickOff.left - SPACE.s, above(N.Task_HoldKickOff.cy), "end") });
  flow("Flow_ProposalChangesRequested", "Gateway_ProposalSplit", "Task_ReviseProposal", [bottom("Gateway_ProposalSplit"), top("Task_ReviseProposal")],
    { label: lab(ps.cx + 8, besideLeg(DEV)), loop: true });
  flow("Flow_ProposalRejected", "Gateway_ProposalSplit", "End_ProposalRejected", [rightMid("Gateway_ProposalSplit"), leftMid("End_ProposalRejected")],
    { label: lab(ps.cx + 8, Math.min(ps.cy + EV + SPACE.s + TYPE.ascent * TYPE.size, lowInLane(ITM))) });
  flow("Flow_ProposalRevised", "Task_ReviseProposal", "Gateway_ProposalJoin", [leftMid("Task_ReviseProposal"), at(x.Gateway_ProposalJoin, "Task_ReviseProposal"), bottom("Gateway_ProposalJoin")]);
  flow("Flow_KickOffHeld", "Task_HoldKickOff", "Task_SpecifyRequirements", [rightMid("Task_HoldKickOff"), leftMid("Task_SpecifyRequirements")]);
  flow("Flow_RequirementsSpecified", "Task_SpecifyRequirements", "Gateway_PlanJoin", [[c.specifyExit, N.Task_SpecifyRequirements.bottom], at(c.specifyExit, "Gateway_PlanJoin"), leftMid("Gateway_PlanJoin")]);
  flow("Flow_PlanStarted", "Gateway_PlanJoin", "Task_DraftPlan", [rightMid("Gateway_PlanJoin"), leftMid("Task_DraftPlan")]);
  flow("Flow_PlanDrafted", "Task_DraftPlan", "Task_ApprovePlan", [rightMid("Task_DraftPlan"), at(c.draftUp, "Task_DraftPlan"), [c.draftUp, N.Task_ApprovePlan.bottom]]);
  flow("Flow_PlanDecided", "Task_ApprovePlan", "Gateway_PlanSplit", [rightMid("Task_ApprovePlan"), leftMid("Gateway_PlanSplit")]);
  const pl = N.Gateway_PlanSplit, buY = N.Task_HoldKickOff.cy;
  flow("Flow_PlanApproved", "Gateway_PlanSplit", "Task_BuildApplication", [bottom("Gateway_PlanSplit"), top("Task_BuildApplication")],
    { label: lab(pl.cx + 8, Math.min(pl.cy + GW + TYPE.ascent * TYPE.size, lowInLane(ITM))) });
  flow("Flow_PlanChangesRequested", "Gateway_PlanSplit", "Gateway_PlanJoin", [top("Gateway_PlanSplit"), [pl.cx, buY], [x.Gateway_PlanJoin, buY], top("Gateway_PlanJoin")],
    { label: lab((pl.cx + x.Gateway_PlanJoin) / 2, above(buY), "middle"), loop: true });
  flow("Flow_ApplicationBuilt", "Task_BuildApplication", "Gateway_ReleaseJoin", [bottom("Task_BuildApplication", x.Gateway_ReleaseJoin - x.Task_BuildApplication), top("Gateway_ReleaseJoin")]);

  const ts = N.Gateway_TestSplit;
  const fixUnder = N.Task_FixDefects.left + 12;
  const refineOut = N.Task_RefineApplication.right - 14;
  if (model === "as_is") {
    flow("Flow_ReleaseCandidateReady", "Gateway_ReleaseJoin", "Gateway_TestJoin", [rightMid("Gateway_ReleaseJoin"), leftMid("Gateway_TestJoin")]);
    flow("Flow_TestsStarted", "Gateway_TestJoin", "Task_ReviewSourceCode", [rightMid("Gateway_TestJoin"), leftMid("Task_ReviewSourceCode")]);
    flow("Flow_CodeReviewed", "Task_ReviewSourceCode", "Task_RunFunctionalTests", [rightMid("Task_ReviewSourceCode"), leftMid("Task_RunFunctionalTests")]);
    flow("Flow_FunctionsTested", "Task_RunFunctionalTests", "Task_RunSecurityTests", [rightMid("Task_RunFunctionalTests"), leftMid("Task_RunSecurityTests")]);
    flow("Flow_SecurityTested", "Task_RunSecurityTests", "Task_RunAcceptanceTests", [rightMid("Task_RunSecurityTests"), leftMid("Task_RunAcceptanceTests")]);
    flow("Flow_AcceptanceTested", "Task_RunAcceptanceTests", "Gateway_TestSplit", [rightMid("Task_RunAcceptanceTests"), leftMid("Gateway_TestSplit")]);
    flow("Flow_DefectsFound", "Gateway_TestSplit", "Task_FixDefects", [top("Gateway_TestSplit"), at(ts.cx, "Task_FixDefects"), rightMid("Task_FixDefects")],
      { label: lab((ts.cx + N.Task_FixDefects.right) / 2, above(N.Task_FixDefects.cy), "middle"), loop: true, hot: true });
    flow("Flow_DefectsFixed", "Task_FixDefects", "Gateway_TestJoin", [[fixUnder, N.Task_FixDefects.bottom], [fixUnder, railY], [x.Gateway_TestJoin, railY], top("Gateway_TestJoin")], { hot: true });
    flow("Flow_ApplicationRefined", "Task_RefineApplication", "Gateway_ReleaseJoin",
      [[refineOut, N.Task_RefineApplication.bottom], [refineOut, channel], [x.Gateway_ReleaseJoin, channel], bottom("Gateway_ReleaseJoin")]);
  } else {
    const cs = N.Gateway_ChecksSplit, cj = N.Gateway_ChecksJoin;
    flow("Flow_ReleaseCandidateReady", "Gateway_ReleaseJoin", "Gateway_ChecksSplit", [rightMid("Gateway_ReleaseJoin"), leftMid("Gateway_ChecksSplit")]);
    // AND-split: one arc straight into the first check, the others over the rail above the checks.
    flow("Flow_CodeReviewStarted", "Gateway_ChecksSplit", "Task_ReviewSourceCode", [rightMid("Gateway_ChecksSplit"), leftMid("Task_ReviewSourceCode")]);
    const viaRail = (id, task) => flow(id, "Gateway_ChecksSplit", task, [top("Gateway_ChecksSplit"), [cs.cx, railY], [N[task].cx, railY], top(task)]);
    viaRail("Flow_FunctionalTestsStarted", "Task_RunFunctionalTests");
    viaRail("Flow_SecurityTestsStarted", "Task_RunSecurityTests");
    viaRail("Flow_AcceptanceTestsStarted", "Task_RunAcceptanceTests");
    // AND-join: every check down to the line under them, then right into the join.
    const toJoin = (id, task) => flow(id, task, "Gateway_ChecksJoin", [bottom(task), [N[task].cx, under], leftMid("Gateway_ChecksJoin")]);
    toJoin("Flow_CodeReviewed", "Task_ReviewSourceCode");
    toJoin("Flow_FunctionsTested", "Task_RunFunctionalTests");
    toJoin("Flow_SecurityTested", "Task_RunSecurityTests");
    toJoin("Flow_AcceptanceTested", "Task_RunAcceptanceTests");
    flow("Flow_ChecksCompleted", "Gateway_ChecksJoin", "Gateway_RetestJoin", [rightMid("Gateway_ChecksJoin"), leftMid("Gateway_RetestJoin")]);
    flow("Flow_TestRoundCompleted", "Gateway_RetestJoin", "Gateway_TestSplit", [rightMid("Gateway_RetestJoin"), leftMid("Gateway_TestSplit")]);
    flow("Flow_DefectsFound", "Gateway_TestSplit", "Task_FixDefects", [top("Gateway_TestSplit"), at(ts.cx, "Task_FixDefects"), rightMid("Task_FixDefects")],
      { label: lab((ts.cx + N.Task_FixDefects.right) / 2, above(N.Task_FixDefects.cy), "middle"), loop: true });
    flow("Flow_DefectsFixed", "Task_FixDefects", "Task_RetestFixedDefects", [bottom("Task_FixDefects", x.Gateway_RetestJoin - x.Task_FixDefects), top("Task_RetestFixedDefects", x.Gateway_RetestJoin - x.Task_RetestFixedDefects)]);
    flow("Flow_DefectsRetested", "Task_RetestFixedDefects", "Gateway_RetestJoin", [bottom("Task_RetestFixedDefects", x.Gateway_RetestJoin - x.Task_RetestFixedDefects), top("Gateway_RetestJoin")]);
    flow("Flow_ApplicationRefined", "Task_RefineApplication", "Gateway_ReleaseJoin",
      [[refineOut, N.Task_RefineApplication.bottom], [refineOut, channel], [x.Gateway_ReleaseJoin, channel], bottom("Gateway_ReleaseJoin")]);
    c1 = { x: cs.left - SPACE.s, y: qc.top + SPACE.xs, w: cj.right + SPACE.m - cs.left + SPACE.s, h: under + GW + 3 - qc.top - SPACE.xs };
  }
  flow("Flow_TestsPassed", "Gateway_TestSplit", "Task_ApproveRelease", [rightMid("Gateway_TestSplit"), [c.passUp, ts.cy], [c.passUp, N.Task_ApproveRelease.bottom]],
    { label: lab(c.passUp + 8, ts.cy - GW - SPACE.s) });
  flow("Flow_ReleaseDecided", "Task_ApproveRelease", "Gateway_ReleaseSplit", [rightMid("Task_ApproveRelease"), leftMid("Gateway_ReleaseSplit")]);
  const rs = N.Gateway_ReleaseSplit;
  flow("Flow_ReleaseApproved", "Gateway_ReleaseSplit", "Task_DeployApplication", [bottom("Gateway_ReleaseSplit"), top("Task_DeployApplication")],
    { label: lab(rs.cx + 8, besideLeg(DEV)) });
  flow("Flow_ReleaseRejected", "Gateway_ReleaseSplit", "Task_RefineApplication", [top("Gateway_ReleaseSplit"), [rs.cx, buY], [c.refineIn, buY], [c.refineIn, N.Task_RefineApplication.top]],
    { label: lab(rs.cx + 8, buY + 0.36 * TYPE.size), loop: true });
  flow("Flow_ApplicationDeployed", "Task_DeployApplication", "Task_StartOperation", [rightMid("Task_DeployApplication"), leftMid("Task_StartOperation")]);
  flow("Flow_OperationStarted", "Task_StartOperation", "Task_MonitorOperation", [rightMid("Task_StartOperation"), leftMid("Task_MonitorOperation")]);
  flow("Flow_OperationMonitored", "Task_MonitorOperation", "Task_EvaluateProject", [rightMid("Task_MonitorOperation"), leftMid("Task_EvaluateProject")]);
  flow("Flow_ProjectEvaluated", "Task_EvaluateProject", "End_ProjectClosed", [rightMid("Task_EvaluateProject"), leftMid("End_ProjectClosed")]);

  // Highlight frames (not BPMN elements): the bottleneck or C1 around the checks, and the part after go-live.
  const frames = [];
  const checksL = N.Task_ReviewSourceCode.left - SPACE.m, checksR = N.Task_RunAcceptanceTests.right + SPACE.m;
  const ops = lanes[OPS];
  const frameLabel = [(checksL + checksR) / 2, ops.top + m.laneTop / 2 + SPACE.s + TYPE.ascent * TYPE.size];
  if (model === "as_is") frames.push({ kind: "bottleneck", x: checksL, y: boxTop(QC) - SPACE.s, w: checksR - checksL, h: m.boxH + SPACE.s + 3, label: frameLabel });
  else frames.push({ ...c1, kind: "change", change: "C1", label: [c1.x + c1.w / 2, frameLabel[1]] });
  frames.push({ kind: "golive", x: c.goLive, y: SPACE.xs, w: WIDTH - c.goLive - SPACE.xs, h: height - 2 * SPACE.xs });

  return {
    model, metrics: m, width: WIDTH, height, lanes, nodes, flows, frames,
    boxes: Object.fromEntries(Object.values(nodes).filter((n) => n.type === "task").map((n) => [n.id, n])),
    changed: CHANGED[model],
    goLive: c.goLive,
  };
}

// The status strip under a task's label: rows of dots, bottom row first, waiting dots first.
// A box with a change chip keeps its dots left of the chip.
function strip(m, box, chip = false) {
  const y0 = box.bottom - m.padBottom - m.dot;
  return { x0: box.left + 6 + m.dot, x1: box.right - 6 - m.dot - (chip ? CHIP.w + SPACE.s : 0), rows: Array.from({ length: m.rows }, (_, k) => y0 - k * m.dotStep) };
}

// Where dot number `index` of `total` sits in a task's strip. The waiting dots come first, then the
// ones being worked on; rows fill from the bottom, and past the last row the dots squeeze together.
export function dotPosition(layout, task, index, total) {
  const box = layout.boxes[task];
  if (!box) return null;
  const m = layout.metrics, s = box.strip;
  const span = s.x1 - s.x0;
  const step = 2.3 * m.dot;
  const fit = Math.floor(span / step) + 1;
  const perRow = Math.max(fit, Math.ceil(total / s.rows.length));
  const row = Math.min(s.rows.length - 1, Math.floor(index / perRow));
  const col = index - row * perRow;
  const st = perRow > fit ? span / (perRow - 1) : step;
  return [s.x0 + col * st, s.rows[row]];
}

// A parked dot: a check of the to-be that finished first waits on its arc just before the AND-join.
export function parkPosition(layout, task, slot) {
  const f = Object.values(layout.flows).find((fl) => fl.source === task && layout.nodes[fl.target]?.type === "parallelGateway");
  if (!f) return null;
  const [ex, ey] = f.pts.at(-1);
  return [ex - GW / 2 - layout.metrics.dot - 2 - slot * 2.3 * layout.metrics.dot, ey];
}

// The path a token follows from one node to a task (or, with `to` null, to an end event), through
// gateways only: the BPMN token flow of Dumas et al., Fig. 3.2. Null if there is no such path.
export function route(layout, from, to) {
  const isGateway = (id) => layout.nodes[id]?.type.endsWith("Gateway");
  const out = {};
  for (const f of Object.values(layout.flows)) (out[f.source] ??= []).push(f);
  const queue = [[from, []]];
  const seen = new Set([from]);
  while (queue.length) {
    const [node, path] = queue.shift();
    for (const f of out[node] ?? []) {
      const next = [...path, f];
      const done = to == null ? layout.nodes[f.target]?.type === "endEvent" : f.target === to;
      if (done) return { flows: next.map((x) => x.id), target: f.target, pts: join(next.map((x) => x.pts)) };
      if (isGateway(f.target) && !seen.has(f.target)) { seen.add(f.target); queue.push([f.target, next]); }
    }
  }
  return null;
}

function join(paths) {
  const pts = [];
  for (const p of paths) for (const q of p) {
    const last = pts.at(-1);
    if (!last || Math.hypot(last[0] - q[0], last[1] - q[1]) > 0.01) pts.push(q);
  }
  return pts;
}
