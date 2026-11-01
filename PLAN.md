# IS6003 Final: Time optimization of the app development process with ML

Research method: Design Science Research Methodology (Peffers et al., 2007).
Process work follows *Fundamentals of BPM*, 2nd ed. (Dumas et al.). Page numbers below are the book's printed pages.

Deliverables: one Python notebook (data, training, evaluation) and one static HTML page that shows the results.

## Phase 0: Fix the as-is model (book §5.4, p.189–193)
- [x] Wrap lanes in a pool (§3.4)
- [x] Label start and end events as object + past participle
- [x] Replace Có/Không with explicit conditions on the outgoing arcs (p.190)
- [x] Split compound activities, especially the test task (code review, testing, security, acceptance)
- [x] Add an end event for a rejected proposal (G3)
- [ ] Check which lane "Bổ sung / điều chỉnh đề xuất" belongs in (open question in `models/as_is_changelog.md`)
- [x] Run the 7PMG checklist (G1–G7)

Done when: `models/as_is.bpmn` passes the checklist.

## Phase 1: Problem and objective (DSRM 1–2, book Ch. 6)
- [ ] Value-added analysis per activity (§6.1)
- [ ] Waste analysis (§6.2)
- [ ] Issue register (§6.3.2)
- [ ] Objective written as a cycle time target

Done when: there's a one-paragraph problem statement and a measurable objective.

## Phase 2: Synthetic event log (book §7.3.2, §11.3)
Real data can't be used, so we generate the log by simulating the as-is model.
- [ ] Case attributes (features): project type, complexity, number of integrations, security level, requesting unit, team workload
- [ ] Activity durations from expert estimates (distribution per activity)
- [ ] Gateway probabilities that depend on case attributes, e.g. rework is more likely for complex projects
- [ ] Resource capacity per lane, so waiting time shows up
- [ ] Simulator (SimPy) writes a log: case_id, activity, start, end, resource, attributes
- [ ] Assumptions table: every parameter, its value, and why

Done when: the log has a few thousand cases and every number traces to the assumptions table.

## Phase 3: As-is baseline (book Ch. 7, §11.5)
- [ ] Cycle time, processing time, waiting time per case
- [ ] Cycle time efficiency (§7.1.2)
- [ ] Rework rate per gateway

Done when: there's a baseline table.

## Phase 4: ML diagnosis
Goal: show ML applied to the problem in a systematic way, not to win on accuracy.
- [ ] Task A: predict case cycle time at case start (regression)
- [ ] Task B: predict rework at each gateway (classification)
- [ ] Reference baselines (mean / majority class) so the metrics have context
- [ ] Models: linear/logistic, then gradient boosting
- [ ] Split by case start time, not randomly, to avoid leaking the future
- [ ] Metrics: MAE for A, ROC-AUC for B
- [ ] SHAP to rank the delay drivers

Done when: there's a ranked list of delay drivers that feeds Phase 5.

## Phase 5: Redesign (book Ch. 8, Appendix A)
- [ ] Map each delay driver to a redesign heuristic
- [ ] Check each change against the Devil's Quadrangle (§8.1.3)
- [ ] Draw `models/to_be.bpmn` to Phase 0 standards
- [ ] Table: change, heuristic, expected time effect, trade-off

Done when: every change in the to-be model points to a driver and a heuristic.

## Phase 6: Evaluation by simulation (DSRM 5, book §7.3)
- [ ] Simulate the as-is model and every combination of to-be changes (2^k scenarios)
- [ ] Same random seeds across scenarios so differences come from the design
- [ ] Many replications per scenario, report mean and 95% CI
- [ ] Ablation: each change alone, and the full design minus each change
- [ ] Export `web/results.json`

Done when: we can say "to-be is X% faster (95% CI …), and change Y contributes most".

## Phase 7: Notebook and HTML page (DSRM 4 and 6)
- [ ] Clean notebook, top to bottom: log → baseline → ML → simulation
- [ ] `web/index.html`: as-is and to-be models (bpmn-js), baseline numbers, ML drivers, a toggle per change that reads the precomputed scenario results
- [ ] Report sections follow the DSRM steps

## Threats to validity (keep updating)
- Synthetic data: the ML partly learns back the assumptions we put in the generator.
- Expert estimates for durations and probabilities are not measured values.
