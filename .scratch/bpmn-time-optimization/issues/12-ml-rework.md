# 12: ML task B, rework prediction (Phase 4)

**What to build:** For each rework gateway, predict from case-start attributes whether the case loops back at least once. Reference baseline (majority class), logistic regression and gradient boosting, with a chronological 80/20 split. ROC-AUC and F1 per model. SHAP drivers per gateway. Written to the `ml` section of the results.

**Blocked by:** 07

**Status:** ready-for-agent

- [ ] On a simulator log where one attribute drives rework at one gateway, that attribute ranks first for that gateway
- [ ] Class imbalance is handled and the handling is stated
- [ ] Split is chronological, never random
- [ ] Each model's metrics are reported next to the reference baseline
- [ ] Output validates against the `ml` part of the schema
