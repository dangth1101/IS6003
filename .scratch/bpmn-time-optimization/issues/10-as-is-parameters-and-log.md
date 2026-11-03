# 10: As-is parameters and synthetic event log (Phase 2)

**What to build:** Proposed default parameters for the corrected as-is model (arrival rate, attribute distributions, durations, branch probabilities with attribute effects, lane capacities, warm-up), each with a rationale marked "proposed default". Planted effects are listed explicitly so later ML results can be discussed honestly. Running the simulator gives a synthetic log of a few thousand cases, exportable as CSV.

**Blocked by:** 04, 06, 07

**Status:** done

- [x] Parameter file covers every task, XOR split and lane in the corrected model and passes validation
- [x] Every planted attribute effect is listed in one place, so the report can state what the ML should find
- [x] Log has at least 2,000 cases after warm-up
- [x] Mean cycle time and rework rates fall in plausible ranges for a bank IT project (stated in the rationale)
- [x] CSV export opens and matches the book's event log shape (§11.3)

## Comments

- Done. Parameters in `models/as_is.params.toml` (version `proposed-1`), planted effects in `models/as_is_planted_effects.md`, tests in `tests/test_as_is_parameters.py`, `tests/test_event_log.py`, plus scaled-duration tests in `tests/test_case_attributes.py`.
- Context: a bank IT division, about one request a week (rate 0.25 per working day), one working year of warm-up (250 days). Every rationale starts with "Proposed default." and a test checks it. The target ranges sit at the top of the parameter file and the tests check the same numbers.
- Seed 42, 2,000 cases after warm-up, simulates in under 1 s. Closed projects: mean 155 working days, median 141, P90 217. All cases (10% rejected early): mean 140, cycle time efficiency 0.79.
- Rework on that log: 20% of proposal decisions ask for changes, 10% of requests rejected, 19% of plans sent back, 38% of test rounds find defects (37% of built projects fail at least once), 8% of releases rejected. Waiting is about 21% of the cycle time.
- Utilisation rho = rate x work per case / capacity: business unit 0.78, IT management 0.80, development 0.81, IT operations 0.79, QC 0.88 (the bottleneck). All below 1; a test keeps them in 0.7-0.95 with QC highest. Mean cycle time by quarter of the log moves between 127 and 151 days with no trend, so the queues settle.
- New duration kind for "integrations lengthen development": `{ triangular = [...], scale = { attr = coef, label_attr = { label = coef } } }`, which multiplies the draw by 1 + the terms. Same term syntax as logistic. Its `.mean` is the base mean times the mean factor over the attribute distributions, which is exact because the factor is linear and independent of the base draw, so flow analysis still works on scaled durations. The draw uses the same per-case stream as before, so common random numbers hold.
- Planted: complexity on requirements, build and test failure; integrations on build and test failure; team_workload on build (weak); security_level on security-test time and test failure; project_type on plan rework (new_system) and release rework (regulatory). `requesting_unit` has no effect: the negative control. A test checks the doc and the parameter file match both ways.
- Honest caveat for 11 and 14: a linear fit of cycle time on the attributes gives R² of only about 0.15. Rework loop counts and queueing add a lot of noise no attribute explains. Complexity, security level and integrations stand out; project_type and team_workload are about as big as the noise on requesting_unit. That is worth discussing, not hiding.
- CSV: `bpmopt.event_log.export_csv(log, path)`. Columns follow Fig. 11.4 (case_id, event_id, activity, resource = lane) with ready/start/end instead of one timestamp (§11.5 pp.443-444), attributes last (p.422). Times rounded to 4 decimals; the 2,000-case log is about 52,000 rows, gateway decision rows included.
- Merge with 08/12/13: the flow analysis averages over attribute draws, so it now takes a scaled duration's mean for the drawn case (security level raises both test time and test failure, so the population mean would come out low). New test in `tests/test_flow_analysis.py`. 08's as-is cross-check in `tests/test_as_is_model.py` now runs with unlimited lanes, since flow analysis has no waiting. `apply_overrides` passes the attributes so a scenario can override a scaled duration.
- For 14: the notebook still says the parameters are placeholders and uses `N_CASES = 100`. Set it to 2,000, update that text, and write the CSV with `export_csv` if the report needs the file. `web/results.json` still holds placeholder-run numbers until the notebook reruns.
- Open for the student: all values are estimates. The ones that move the results most are the QC capacity (8) and functional test time, since QC is the bottleneck, and the test-failure logistic.
- Arrival rate lowered from 0.25 to 0.234 per working day (student decision, parameters `proposed-3`): utilisation now business unit 0.78, IT management 0.77, development 0.81, IT operations 0.79, QC 0.87; log, planted effects and target ranges still hold.
