# 08: Baseline analysis (Phase 3)

**What to build:** Event log → baseline metrics: cycle time, processing time and waiting time (mean, median, P90), cycle time efficiency (§7.1.2), rework rate per XOR gateway, and mean waiting time per activity. Also the cross-check between the simulated mean and the flow analysis value. All of it goes into the `baseline` section of the results.

**Blocked by:** 03, 04

**Status:** done

- [x] Tested on simulator logs with known parameters: configured rework rates and durations are recovered within tolerance
- [x] Cycle time efficiency is 1.0 with unlimited capacity and no rework, and drops when waiting appears
- [x] Per-activity waiting time is highest at the lane with the tightest capacity in a fixture
- [x] Output validates against the `baseline` part of the schema

## Comments

- Done. `baseline_metrics(log, model)` and `flow_analysis_check(model, params, n_cases=, seed=)` in `src/bpmopt/analysis.py`. `build_results` now takes `model` and fills the whole `baseline` section. Schema: every baseline field is required now. Tests in `tests/test_baseline.py`, all on simulator logs.
- Log format: each XOR-split decision is now a zero-duration row (`element_type = "exclusiveGateway"`) with the flow taken in a new `flow_id` column. Other rows have `flow_id` empty. XOR-joins and AND gateways get no row. I went with this over inferring rework from repeated tasks: a loop with no task on the back arc, or a task that also runs elsewhere, makes inference guesswork.
- For 12: `loop_back_flows(model)` in `flow_analysis.py` gives rework split ID -> loop-back flow ID. A case "loops back at least once at gateway X" when it has a row with `activity_id == X` and `flow_id ==` that flow. Train only on cases that reached X.
- Rework rate = share of the cases that reached the gateway which looped back at least once. Cases that never got there (rejected earlier) are left out, so the rate estimates the configured r. Only rework gateways are listed, not plain decisions.
- Processing time per case = time during which at least one task of the case is in progress (merged task intervals). Parallel AND work counts once, like the book's TCT taking the max over AND branches (p.262). Waiting = CT - processing, the book's "no work being done to advance the process" (p.261). Without this, a model with an AND-block gets CTE above 1.
- CTE = mean processing time / mean cycle time, the book's Eq. 7.5 with both terms averaged over cases.
- Waiting per activity = mean of start - ready per task run, longest first. A reworked task counts once per run.
- Flow analysis check: simulates the model again with every lane unlimited (same seed and case count), since flow analysis ignores contention (§7.1.7, p.273).
- Early end events (open point from 03): CT stays the mean over all cases (book p.256), not per outcome. A case that ends early counts with its time up to its end; anything after a possible early end is weighted by the chance the case is still running. The book says nothing on this, its blocks all end in a join, so it is marked as our derivation in the code. Several end events on exclusive paths give the same CT as merging them with an XOR-join before one end event, so it stays inside (7.1)-(7.4). A rework split with a third branch to an end event (the "Proposal rejected" shape) is treated as the loop split followed by an XOR-split over the non-loop arcs, probabilities divided by 1 - r. Fixtures `proposal_rejected` (8.4 by hand) and `early_exit_in_block` (11.8) check both the formula and the simulator. Per-outcome CT is a filter on the log by end event if the page ever wants it.
- Logistic splits (after merging 07): flow analysis runs the formulas per attribute vector, then averages over 5,000 attribute draws from the parameter file with a fixed seed (`theoretical_cycle_time(..., n_draws=, seed=)`). Plugging the mean probability in would underestimate rework, since 1/(1 - r) is convex: on `rework_with_activity.logistic` that gives 11.2 days against the true 17.4. Marked as our extension of §7.1.1. With only fixed splits nothing is drawn and the result is the plain formula. Durations don't depend on attributes, so they're unaffected.
- Flow analysis is now also stricter: a join must have exactly as many inputs as the block branches that reach it, else `ValueError`.
- After merging 06: the cross-check works on `models/as_is.bpmn` with its placeholder parameters (96.25 days by flow analysis, 96.49 simulated over 20,000 cases). A test in `tests/test_as_is_model.py` keeps it that way. The notebook now prints the full baseline and the check. With placeholder parameters there is no capacity limit yet, so CTE is 1 and waiting is 0 until ticket 10.
