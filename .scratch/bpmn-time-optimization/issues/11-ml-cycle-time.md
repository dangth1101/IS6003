# 11: ML task A, cycle time prediction (Phase 4)

**What to build:** Event log → case-level feature table (attributes known at case start) → cycle time prediction. Reference baseline (predict the mean), a linear model and gradient boosting, with a chronological 80/20 split by case start. MAE and R² per model. SHAP values on the gradient boosting model, aggregated into a ranked list of drivers by mean |SHAP|. Written to the `ml` section of the results.

**Blocked by:** 07

**Status:** done

- [x] On a simulator log with one planted driver, that driver ranks first
- [x] No feature uses information from after case start
- [x] Split is chronological, never random
- [x] Each model's metrics are reported next to the reference baseline
- [x] Output validates against the `ml` part of the schema

## Comments

- Done. Tests in `tests/test_features.py` (feature table, split) and `tests/test_ml.py` (planted driver, metrics, schema). Fixture `rework_with_activity.ml.params.toml`: only `project_type` changes the loop-back chance, the other three attributes are noise.
- Dependencies: `scikit-learn==1.9.1`, `shap==0.54.1`. Both work with NumPy 2.5.4 on Python 3.12 and 3.13; shap's TreeExplainer reads `HistGradientBoostingRegressor` directly.
- `bpmopt.features` (generic, for 12 too): `case_features(log)` gives one row per case, indexed by `case_id`, with `start_time` then the attributes in log order. `start_time` is the earliest ready time, same as `cycle_times`. It only orders the split and isn't a model input. `chronological_split(table, train_share)` sorts by `start_time`, ties keep case order. `attribute_names(log)` = columns after `LOG_COLUMNS`.
- `bpmopt.ml`: `cycle_time_task(log, seed=...)` returns one `ml_task` dict (`id = "cycle_time"`). `ml_section(tasks)` wraps tasks into the `ml` section with `TRAIN_SHARE = 0.8`. The notebook does `results["ml"] = ml_section([cycle_time_task(log, seed=seed), *rework_tasks])`.
- For 12, reusable pieces: `training_data(log, target)` joins any per-case target (Series indexed by `case_id`) to the features and splits; `encoder(x)` one-hot encodes label attributes and passes numbers through; `shap_drivers(pipeline, x)` ranks attributes by mean |SHAP| for an encoder + tree-model pipeline. One-hot columns are summed back per attribute before the abs, so drivers are attribute names, as in the fake results. For a binary HGB classifier the SHAP values are in log-odds.
- Gradient boosting uses fixed, conservative settings (`max_depth=3`, `learning_rate=0.05`, `min_samples_leaf=50`). With 800 training cases sklearn's defaults overfit: R² fell below the mean predictor on one seed and the noise attribute `workload` got about 2 days of mean |SHAP|. With these settings it's about 1. No early stopping, since that draws a random validation split.
- SHAP is computed on the test cases.
- Expect modest R² even with a strong planted driver. The number of loop-backs is geometric, so most of the cycle time variance is luck. On the fixture R² is about 0.15 to 0.3 and the linear model is often slightly better than boosting, which is worth a line in the 14 discussion.
- Not added: WIP at arrival as a derived feature (07's note). It's known at case start and could be computed from the log, but the caller asked to keep the table to the drawn attributes for now.
