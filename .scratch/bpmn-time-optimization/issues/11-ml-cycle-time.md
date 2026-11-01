# 11: ML task A, cycle time prediction (Phase 4)

**What to build:** Event log → case-level feature table (attributes known at case start) → cycle time prediction. Reference baseline (predict the mean), a linear model and gradient boosting, with a chronological 80/20 split by case start. MAE and R² per model. SHAP values on the gradient boosting model, aggregated into a ranked list of drivers by mean |SHAP|. Written to the `ml` section of the results.

**Blocked by:** 07

**Status:** ready-for-agent

- [ ] On a simulator log with one planted driver, that driver ranks first
- [ ] No feature uses information from after case start
- [ ] Split is chronological, never random
- [ ] Each model's metrics are reported next to the reference baseline
- [ ] Output validates against the `ml` part of the schema
