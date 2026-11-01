# 14: As-is pipeline end to end

**What to build:** The notebook runs the real as-is pipeline top to bottom with one seed: lint both models, generate the synthetic log, compute the baseline, run both ML tasks, write the results file. The page shows real as-is numbers, the value-added data and the ML drivers. The redesign sections still show placeholders. This is the evidence the student uses for the redesign.

**Blocked by:** 05, 08, 09, 10, 11, 12

**Status:** done

- [x] Notebook runs top to bottom from a fresh kernel without errors
- [x] Notebook stays thin: each cell calls the package and explains the step, citing the book section
- [x] Results file validates against the schema
- [x] Page shows the real baseline, value-added classification, ML metrics and ranked drivers
- [x] Notebook includes a short section comparing the ML drivers with the planted effects (threat to validity)

## Comments

- Done. Notebook rewritten: lint both models (original 27 violations, as-is 0), parameters, simulate 2,000 cases (seed 42) and write the CSV to `notebooks/output/` (gitignored), baseline, flow analysis check, value-added, ML, drivers vs planted effects, export. Committed without outputs, like before. `jupyter execute` from a fresh kernel runs clean.
- Baseline (all cases, as computed): mean 140.4, median 136.5, P90 211.3 working days. Processing 111.1, waiting 29.3, CTE 0.79. Closed projects shown next to it for comparison only: mean 154.9, median 140.9, P90 216.9. Headline not redefined; the all-cases vs closed and monitoring questions stay open. Flow analysis 111.7 vs 111.1 simulated with unlimited lanes.
- Skipped gateways: `rework_tasks` no longer raises on a one-class split. The task gets `skipped` with the reason and no models or drivers. Schema: `ml_task` now has an optional `skipped`; with it, models and drivers are forbidden and kind must be classification; without it, both are required. Page shows the reason under the task heading. No gateway is skipped at seed 42. Tests in `tests/test_ml_rework.py`.
- `export_results` now lints each model and writes `models.<key>.lint` (empty = clean). Test in `tests/test_results.py`. New test `test_the_as_is_pipeline_writes_results_that_validate` in `tests/test_as_is_parameters.py` runs the notebook's path on the real files.
- Page: the as-is gateways have no names, so tables showed raw IDs. `bpmnNames` now names an unnamed XOR gateway with one incoming flow "Decision after <task>" (new label `gateway_after`, added to the schema list). Feature label `workload` renamed `team_workload` to match the real attribute; fake results updated. One sentence added to the ML prose about expecting low scores.
- ML on the real log: cycle time R² about 0 on test for all three models (MAE about 42 days). Test loop ROC-AUC 0.64/0.63, release 0.71 (logistic) / 0.57, plan 0.54/0.56, proposal 0.54/0.54.
- Drivers vs planted: test loop top 3 = complexity, security_level, integrations (exactly planted). Cycle time: complexity, security_level lead; integrations third but level with noise; project_type and team_workload not told apart from `requesting_unit`. Plan loop: project_type first. Release loop: project_type second behind team_workload. `requesting_unit` never first, 5th of 6 for cycle time and test loop, 2nd at the proposal loop where nothing is planted. Continuous team_workload picks up SHAP everywhere. Written up in the notebook as a threat to validity.
- Phase 1 draft: numbers refreshed from the proposed parameters and the log, still marked draft, judgments and priorities unchanged. Note for the student: measured CTE 0.79 is above the 0.5 line the objective section set for lowering X, and QC adds more waiting per case (12.3 days) than the approvals (6.5), which bears on review question 3.
- Page checked in headless Chrome on a local static server: diagram draws with value-added colors, baseline tiles, value-added table, ML tables and driver bars show, redesign and evaluation show "Not available yet", no console errors. Also checked a results file with a skipped task and the fake page.
