# 12: ML task B, rework prediction (Phase 4)

**What to build:** For each rework gateway, predict from case-start attributes whether the case loops back at least once. Reference baseline (majority class), logistic regression and gradient boosting, with a chronological 80/20 split. ROC-AUC and F1 per model. SHAP drivers per gateway. Written to the `ml` section of the results.

**Blocked by:** 07

**Status:** done

- [x] On a simulator log where one attribute drives rework at one gateway, that attribute ranks first for that gateway
- [x] Class imbalance is handled and the handling is stated
- [x] Split is chronological, never random
- [x] Each model's metrics are reported next to the reference baseline
- [x] Output validates against the `ml` part of the schema

## Comments

- Done. `rework_tasks(log, model, seed=...)` in `bpmopt.ml` returns one classification task per rework gateway, in model order, id `rework_<gateway_id>`, with `gateway_id` set. The notebook can do `results["ml"] = ml_section([cycle_time_task(log, seed=seed), *rework_tasks(log, model, seed=seed)])`.
- Label: a case is positive at gateway X when it has a decision row at X with the loop-back flow from `loop_back_flows(model)` (`rework_targets(log, model)`, same reading as `rework_rates`). Only cases that reached X are used, so rejected proposals don't count as "no rework" at the test loop. `training_data` now drops cases missing from the target before the split; cycle time is unaffected.
- Reuses 11's features, chronological split, encoder, gradient boosting settings and `shap_drivers`. Drivers are mean |SHAP| in log-odds.
- Class imbalance: logistic regression and gradient boosting both use `class_weight="balanced"`. The reference (majority class) stays unweighted, so it scores ROC-AUC 0.5 and F1 0 when rework is the minority. Stated in the `rework_tasks` docstring.
- Tests in `tests/test_ml_rework.py`, fixture `proposal_rejected.ml.params.toml`: only complexity drives the test loop (about 1 in 9 fail, no complexity level above 50%), the proposal loop is a fixed 25%. Complexity ranked first at the test loop on 8 of 8 seeds; the proposal loop scores ROC-AUC near 0.5. Removing the class weights makes the F1 test fail (an unweighted model never predicts rework there), checked by hand.
- A gateway where the training or test cases are all one class raises `ValueError` naming the gateway, instead of writing a meaningless AUC. If the as-is model has a rarely reached gateway, 14 may hit this.
- The split is 11's `chronological_split`, tested in `test_features.py`. No separate test here.
- Seen on the fixture: the continuous noise attribute `workload` gets about 0.2 to 0.3 mean |SHAP| even where nothing drives rework. Worth a line in 14 when reading small drivers.
- `test_ml.py` called `build_results` without `model=` after the 11 merge. I fixed it here, and the branch fixed it too in the meantime; the merge kept the branch's version.
