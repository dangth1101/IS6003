# 03: Studio Python API

**What to build:** The rest of the `bpmopt.studio` seam, JSON in and out: `lint_xml`, `default_parameters` (keep given entries, fill missing ones with documented defaults, drop entries for removed elements, mark which are defaults), the full metrics in `simulate_summary` (cycle, processing and waiting time with CI, cycle time efficiency, utilisation per lane, rework per XOR gateway, waiting per activity), `compare` (paired saving and CI, before/after per lane and activity, refuses mismatched seeds or replications), and `apply_suggestion` for catalog change sets. Default values are chosen here and listed with their rationale.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] `lint_xml` matches `lint` on the same file
- [ ] A model with no parameters simulates after `default_parameters`, and the defaults are marked
- [ ] `apply_suggestion` matches `catalog.resolve` for every change set, and its simulation matches the scenario runner
- [ ] `compare` of as-is versus the full design matches the scenario runner's paired saving and CI
- [ ] `compare` refuses runs with different seeds or replications
- [ ] Nothing on the studio path imports scikit-learn or SHAP

## Comments
