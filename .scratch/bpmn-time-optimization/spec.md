# Spec: ML-driven time optimization of the app development process

**Status:** ready-for-agent

## Problem Statement

I have a BPMN model of my company's application development process (request → approvals → spec → plan → build → test → deploy → operate). For my IS6003 final assignment I have to optimize this process for time using machine learning, and show the result as a Python notebook plus an HTML page.

The problems I face:

- The current model doesn't follow the textbook (*Fundamentals of BPM*, 2nd ed., Dumas et al.). It has no pool, unlabeled start and end events, "Có/Không" arc labels, compound activities, and no way for a rejected proposal to end. The grader expects strict use of the book.
- I can't use real company data, because the process is internal. So I have no event log to train ML on.
- ML can't redraw a diagram by itself. I need a systematic, defensible chain from data to diagnosis to redesign to evaluation, following a proper research method.
- I have no numbers today. I can't say how long the process takes, where time is lost, or how much a redesign would save.

## Solution

A small Python package, one notebook and one static HTML page, organised by the Design Science Research Methodology (DSRM):

1. Fix the as-is model so it passes an automated check of the book's modeling rules.
2. Generate a synthetic event log by simulating the as-is BPMN file directly, with every parameter documented in an assumptions table.
3. Measure the as-is baseline from the log (cycle time, waiting vs processing time, cycle time efficiency, rework rates), and cross-check it against the book's flow analysis.
4. Apply ML to the log: predict cycle time and rework, then use SHAP to rank the drivers of delay.
5. Redesign the process with the book's heuristics, guided by those drivers. This step is a human decision.
6. Simulate the as-is process and every combination of redesign changes under the same random seeds, and report the time saved with confidence intervals, including an ablation of each change.
7. Show everything on a static HTML page: both models rendered, baseline numbers, ML findings, and a toggle per redesign change that shows the resulting cycle time.

## User Stories

1. As the student, I want the as-is model to pass a check of the book's modeling rules, so that the grader can't fault my starting point.
2. As the student, I want a linter that reports each violation with its rule (e.g. 7PMG G3) and the element ID, so that I know exactly what to fix.
3. As the student, I want the linter to flag missing pools, unlabeled events, yes/no arc labels, OR gateways and models over 30 elements, so that the book's checkable rules are enforced automatically.
4. As the student, I want the linter to check that every node is reachable from a start event and can reach an end event, so that the model has no dead activities or livelocks (book §5.4.1).
5. As the student, I want the compound test activity split into code review, functional testing, security testing and acceptance, so that I can measure each one's time separately.
6. As the student, I want a "Proposal rejected" end event, so that the model has one end event per outcome (G3) and rejected requests don't loop forever.
7. As the student, I want all labels in English for now, verb-object for activities and object + past participle for events, so that the model follows the book's labeling rules (§5.4.3) and can be translated later.
8. As the student, I want a value-added classification (VA / BVA / NVA) for every activity, stored as data, so that the qualitative analysis (§6.1) can feed into the numbers and the page.
9. As the student, I want an issue register and a waste analysis written up, so that Phase 1 of the plan is documented the way the book does it (§6.2–6.3).
10. As the student, I want to run the as-is BPMN file through a simulator, so that the diagram I draw is exactly the process I simulate.
11. As the student, I want the simulator to support start and end events, tasks, XOR gateways, AND gateways, sequence flows and lanes, so that it covers everything my models use.
12. As the student, I want each lane to act as a resource pool with a set capacity, so that queues and waiting time appear when work piles up.
13. As the student, I want task durations defined as distributions in a parameter file keyed by element ID, so that I can change estimates without touching code.
14. As the student, I want XOR branch probabilities that can depend on case attributes (e.g. complexity raises the chance of failing tests), so that the log contains realistic patterns for ML to find.
15. As the student, I want each case to get attributes (project type, complexity, number of integrations, security level, requesting unit, team workload at start), so that ML has features to learn from.
16. As the student, I want a configurable arrival rate of new requests, so that cases overlap and compete for resources.
17. As the student, I want every parameter to carry a rationale, so that an assumptions table can be generated straight from the parameter file.
18. As the student, I want proposed default parameter values that I can correct later, so that work isn't blocked on my estimates.
19. As the student, I want the simulator to give the same log for the same seed, so that results are reproducible.
20. As the student, I want an event log with case ID, activity, lane, ready time, start time, end time and the case attributes, so that waiting time and processing time can be told apart.
21. As the student, I want the log exportable as CSV, so that it looks like the book's event log format (§11.3, Fig. 11.4) and can be inspected by hand.
22. As the student, I want a baseline table with mean, median and 90th-percentile cycle time, processing time and waiting time, so that I have numbers to beat.
23. As the student, I want cycle time efficiency computed (§7.1.2), so that I can show how much of the cycle time is waiting.
24. As the student, I want the rework rate per XOR gateway and the mean waiting time per activity, so that I can see where time is lost.
25. As the student, I want the theoretical cycle time from the book's flow analysis (§7.1.1), computed from the model and its mean durations, so that I can show the simulator agrees with the book when capacity is unlimited.
26. As the student, I want a model that predicts a case's cycle time from its attributes at case start, so that ML is applied to the time problem directly.
27. As the student, I want a model per rework gateway that predicts whether a case will loop back at least once, so that I can find which kinds of project cause rework.
28. As the student, I want simple reference baselines (predict the mean, predict the majority class), so that the ML metrics have context.
29. As the student, I want a linear/logistic model and a gradient boosting model for each task, so that I show a systematic comparison rather than one arbitrary model.
30. As the student, I want the train/test split to follow case start time, so that the model never learns from the future.
31. As the student, I want MAE and R² for cycle time, and ROC-AUC and F1 for rework, so that the evaluation uses standard metrics.
32. As the student, I want SHAP values for the gradient boosting models and a ranked list of delay drivers, so that the ML output becomes evidence for the redesign.
33. As the student, I want a check that the ML recovers an effect I deliberately put into the simulator, so that I can show the method works and discuss what that means for synthetic data.
34. As the student, I want a change catalog where each redesign change records its delay driver, the book heuristic it applies (Appendix A), its expected effect and its Devil's Quadrangle trade-off (§8.1.3), so that every change is justified.
35. As the student, I want the to-be model to pass the same linter as the as-is model, so that both follow the book equally strictly.
36. As the student, I want each redesign change switchable on its own, so that I can simulate every combination of changes.
37. As the student, I want every scenario simulated with the same random seeds and many replications, so that differences come from the design and not from luck.
38. As the student, I want mean, median and 90th-percentile cycle time with 95% confidence intervals per scenario, so that I can claim a saving with stated uncertainty.
39. As the student, I want an ablation (each change alone, and the full design minus each change), so that I can say which change contributes most.
40. As the student, I want a warm-up period discarded from each simulation run, so that the empty-system start doesn't bias the results.
41. As the student, I want the notebook to run top to bottom with one seed and produce all results, so that the grader can reproduce everything.
42. As the student, I want the notebook to stay thin and call the package, so that the logic is tested and the notebook reads like a report.
43. As the student, I want the notebook to write one results file that follows a fixed schema, so that the HTML page can be built in parallel against fake data.
44. As a viewer of the page, I want to see the as-is and to-be models drawn as BPMN diagrams, so that I can compare them visually.
45. As a viewer of the page, I want the problem, the research method and the objective explained in plain words at the top, so that I understand what was done before the numbers.
46. As a viewer of the page, I want the baseline numbers and where waiting time builds up, so that I see the problem in numbers.
47. As a viewer of the page, I want the ML results shown as metrics next to the reference baselines and a ranked chart of delay drivers, so that I see what ML found.
48. As a viewer of the page, I want a toggle per redesign change that updates the cycle time and its confidence interval, so that I can explore the ablation myself.
49. As a viewer of the page, I want the change catalog shown next to the toggles, so that I know why each change exists and what it costs.
50. As a viewer of the page, I want the assumptions table and the threats to validity listed, so that I can judge how far the results can be trusted.
51. As a viewer of the page, I want the lint results for both models, so that I see they follow the book.
52. As the lecturer, I want the page to work with no backend, so that I can open it from GitHub Pages or a local static server.
53. As the lecturer, I want every book concept on the page and in the notebook to cite its section, so that I can check it was applied correctly.
54. As the student, I want to change all labels and text to Vietnamese later without changing code, so that language is a content edit.

## Implementation Decisions

- **Research method:** DSRM (Peffers et al., 2007). The plan's phases map onto its steps: problem identification (Phases 0–1), objectives (Phase 1), design and development (Phases 2–5), demonstration (Phase 7), evaluation (Phase 6), communication (report + page). The BPM lifecycle from the book supplies the process content.
- **Shape:** one Python package holds all logic, one notebook drives it, one static HTML page presents the results. No backend, no Streamlit.
- **Modules:**
  - *BPMN reader:* parses the supported BPMN subset (pool, lanes, start and end events, tasks, XOR and AND gateways, sequence flows with condition labels) into an in-memory process graph. Element IDs are the keys everything else uses.
  - *Linter:* takes a BPMN file and returns a list of violations (rule ID, element ID, message). Rules: 7PMG G1–G7 where they can be checked automatically (element count, routing paths per element, one start per trigger and one end per outcome, structuredness as far as detectable, no OR gateways, verb-object activity labels as a heuristic, more than 30 elements), event labels present and not generic ("Start", "End"), no yes/no arc labels on XOR splits (p.190), lanes inside a pool, every node reachable and able to reach an end.
  - *Parameters:* one human-editable file. Arrival rate; case attribute distributions; per-task duration distributions (triangular min/mode/max, in working days); per-XOR-split branch probabilities, either fixed or a logistic function of case attributes; per-lane capacity; warm-up length. Every entry has a rationale field. The assumptions table is generated from this file.
  - *Simulator:* discrete-event simulation (SimPy) that executes the process graph with the parameters. Interface: process model + parameters + number of cases + seed → event log. Lanes are resource pools.
  - *Event log:* a table with one row per activity execution: case ID, activity ID, activity label, lane, ready time, start time, end time, plus the case attributes repeated per row. Exportable to CSV.
  - *Analysis:* event log → baseline metrics (cycle, processing and waiting time with mean, median and P90; cycle time efficiency; rework rate per XOR gateway; waiting time per activity). Process graph + mean parameters → theoretical cycle time by the book's flow analysis (sequence, XOR, AND and rework block formulas, §7.1.1).
  - *ML:* event log → case-level feature table → two tasks. Task A: regression of cycle time from attributes known at case start. Task B: one classifier per rework gateway, predicting at least one loop-back. Reference baselines (mean / majority class), linear and logistic models, and gradient boosting (scikit-learn's histogram gradient boosting, to keep dependencies light). Chronological 80/20 split by case start. Metrics: MAE and R² (A), ROC-AUC and F1 (B). SHAP on the gradient boosting models, aggregated into a ranked list of drivers.
  - *Scenarios:* a change catalog (ID, title, driver it targets, Appendix A heuristic, expected effect, Devil's Quadrangle trade-off). A scenario is a set of change IDs and resolves to a (process model, parameter overrides) pair. The runner simulates all 2^k scenarios with common random numbers (same seed per replication across scenarios), with R replications each (default 30), and reports mean, median and P90 cycle time with 95% CIs. The ablation views (each alone, full minus each) are derived from the full factorial results. How structural changes combine into one model per scenario is decided in the redesign ticket, which must make every change independently switchable.
  - *Results export:* writes one results file (JSON) that the page reads.
- **Results contract (JSON, validated by a JSON schema):**
  - `meta`: seed, replications, case count, warm-up, parameter file version, generated-at time
  - `assumptions`: rows of parameter, value, rationale
  - `models`: as-is and to-be BPMN file references, plus lint results for each
  - `value_added`: activity ID → VA / BVA / NVA
  - `baseline`: the metrics above, plus the flow analysis cross-check
  - `ml`: for each task, the metrics of each model next to the reference baseline, plus the ranked drivers with mean |SHAP|
  - `changes`: the change catalog
  - `scenarios`: a list of {change IDs, cycle time mean / median / P90 with CI bounds}
  - `threats`: a list of threats to validity
  All human-readable text lives in this file or in the BPMN labels, so a translation later is a content change.
- **HTML page:** a single static page that loads the results file and both BPMN files and renders the models with bpmn-js (pinned version from a CDN) and the charts with a pinned chart library. Sections follow DSRM: problem and method, as-is model and baseline, ML findings, redesign (to-be model + change catalog), evaluation (toggles + ablation), assumptions and threats. Served from GitHub Pages or a local static server. Opening it as a plain file isn't supported, because browsers block file fetches.
- **Time unit:** working days on a continuous clock, with no holiday or working-hours calendar.
- **Models in the repo:** the corrected as-is model replaces the current file's role as the source of truth. The original file is kept unchanged for reference.
- **Language:** English for all labels, code, notebook and page text for now.
- **Dependencies:** Python 3.11+, SimPy, pandas, NumPy, scikit-learn, SHAP, a JSON schema validator, pytest. No other ML frameworks.

## Testing Decisions

- A good test checks behavior through a seam and doesn't know about internal helpers. Inputs are a BPMN file plus parameters, outputs are an event log, a lint report or a results file.
- **Seam 1, simulator** (main seam). Small fixture BPMN files: a pure sequence, an XOR block, an AND block, a rework loop. Tests:
  - same seed gives the same log;
  - every case starts at a start event and finishes at an end event;
  - with unlimited capacity, the mean simulated cycle time matches the book's flow analysis formula within tolerance;
  - a configured rework probability shows up in the log within tolerance;
  - limited capacity creates waiting time and unlimited capacity doesn't;
  - an attribute-dependent branch probability shows up in the log.
- **Through the simulator seam:** the analysis and ML modules are tested on logs from the simulator with known parameters, not on mocks. The baseline metrics must recover the configured rates. The ML must rank a deliberately planted driver first.
- **Seam 2, linter.** One fixture per rule that violates only that rule, plus one clean fixture. The as-is and to-be models of the project must lint clean, and that is a test too.
- **Seam 3, results contract.** The results file the notebook writes validates against the schema. The fake results file the page is built against validates against the same schema.
- **Prior art:** the codebase has none yet. The book's worked flow analysis examples (§7.1, Figs. 7.1–7.8) give expected values for the flow analysis tests.
- The notebook itself isn't unit-tested. It must run top to bottom without errors as a final check.

## Out of Scope

- Any real company data, or any interviews whose answers are recorded as data.
- Vietnamese translation. That comes later as a content change.
- Optimizing cost, quality or flexibility. These only appear as trade-offs in the Devil's Quadrangle discussion.
- Automated process discovery (e.g. the α-algorithm) and conformance checking.
- Searching for an optimal design automatically (reinforcement learning, genetic algorithms). The redesign is a human decision guided by ML.
- BPMN elements outside the supported subset: OR gateways, intermediate and boundary events, sub-processes, message flows, data objects.
- Working-hours calendars, holidays and individual resource schedules.
- Any backend, Streamlit, or deployment beyond static hosting.

## Further Notes

- **Threats to validity**, to state in the report and on the page: the data is synthetic, so the ML partly recovers effects we put into the simulator; parameters are expert estimates, not measurements; the time model ignores calendars; lane capacity is simplified to identical resources.
- **Default parameter values** are proposals the student will correct. Their rationale fields should say "proposed default" until then.
- **Redesign (Phase 5) is a human ticket.** It depends on the ML drivers and the baseline, so its changes can't be specified ahead of time.
- The repo is public at github.com/dangth1101/IS6003, so GitHub Pages can host the page.
- Book page references in this spec use the book's printed page numbers. The PDF page is the printed page + 24.
