# 03: Studio Python API

**What to build:** The rest of the `bpmopt.studio` seam, JSON in and out: `lint_xml`, `default_parameters` (keep given entries, fill missing ones with documented defaults, drop entries for removed elements, mark which are defaults), the full metrics in `simulate_summary` (cycle, processing and waiting time with CI, cycle time efficiency, utilisation per lane, rework per XOR gateway, waiting per activity), `compare` (paired saving and CI, before/after per lane and activity, refuses mismatched seeds or replications), and `apply_suggestion` for catalog change sets. Default values are chosen here and listed with their rationale.

**Blocked by:** 02

**Status:** done

- [x] `lint_xml` matches `lint` on the same file
- [x] A model with no parameters simulates after `default_parameters`, and the defaults are marked
- [x] `apply_suggestion` matches `catalog.resolve` for every change set, and its simulation matches the scenario runner
- [x] `compare` of as-is versus the full design matches the scenario runner's paired saving and CI
- [x] `compare` refuses runs with different seeds or replications
- [x] Nothing on the studio path imports scikit-learn or SHAP

## Comments
- 2026-11-05: claimed. Implementer started.
- 2026-11-05: done.
  - API (`src/bpmopt/studio.py`; an estimate is `{value, ci_low, ci_high}`, a 95% t-interval over replications):
    - `lint_xml(xml)` → `[{rule, severity, element_id, message}]`, same order as `lint`. Unreadable XML raises.
    - `default_parameters(xml, params=None)` → `{params, defaults, dropped}`. `defaults` and `dropped` are entry keys (`"tasks.Task_X"`, `"arrivals"`, ...).
    - `simulate_summary(xml, params, n_cases, seed, replications, progress=None)` → `{n_cases, seed, replications, cycle_time: {mean, median, p90}, processing_time: {mean}, waiting_time: {mean}, cycle_time_efficiency, lanes: [{lane_id, label, capacity, utilisation}], rework: [{gateway_id, label, rate}], waiting_by_activity: [{activity_id, label, mean}], replication_means}`. `cycle_time.mean` and `replication_means` are unchanged from 02, so the parity fixture still holds. Lanes are the ones with a capacity, in model order, empty without an arrival rate. Waiting is longest first. A gateway or task fewer than 2 replications reach is left out.
    - `compare(baseline, variant)` → `{saving, saving_share, baseline: {cycle_time}, variant: {cycle_time}, lanes: [{lane_id, label, capacity_before, capacity_after, before, after}], activities: [{activity_id, label, before, after}]}`. `None` where only one run has the lane or task. Raises `ValueError` when seed, replications **or n_cases** differ (stricter than the spec: a different case count isn't paired either).
    - `apply_suggestion(xml, change_ids, preset)` → `{xml, params, changes}`: the catalog scenario's model file and parameter dict (same as `catalog.resolve`), `changes` in catalog order. Raises when `xml` isn't any catalog scenario's model (hand edit) or names an unknown change.
    - `suggestions(xml, preset)` → `{changes: catalog.entries(), available}`. `available` = `apply_suggestion` would accept `xml`.
    - Package changes: `lint.lint_model(model)`, `scenarios.parse_catalog(raw, model_files, model=, params=)` (`load_catalog` calls it, file API unchanged), `analysis.utilisation(log, params)` (the book's ρ = rate × work per case / capacity, the formula of `test_as_is_parameters`).
  - Deviation from the spec: `apply_suggestion` has no `params` argument. The result is the catalog's parameters whatever the current ones are, so taking them would suggest otherwise. That's also what makes undo exact.
  - Worker (`web/studio/worker.mjs`): any `bpmopt.studio` function by name, `{id, call, args}` → `result` / `error` / `progress` as in 02. The worker adds `progress` and `preset` itself to the functions that take them (by signature). So the page sends `apply_suggestion {xml, change_ids}` and `suggestions {xml}`. The worker fetches the six preset files at start (`PRESET_FILES`, the same list as `PRESETS` in `scripts/build_studio.py`; a test checks both against the catalog).
  - Defaults (one block at the top of `studio.py`, each rationale also in the entry's `rationale`, which starts with `Studio default.`):

    | Entry | Default | Why |
    | --- | --- | --- |
    | task duration | triangular [1, 2, 4] days | short task, about 2 days, sometimes twice that; like the shortest as-is tasks, so a new task doesn't dominate |
    | XOR split | equal shares per outgoing flow | nothing says one branch is more common; easiest to see and change |
    | lane capacity | 1 | one person, so the lane's tasks queue; smallest real lane |
    | arrival rate | busiest lane at ρ = 0.8, 3 significant digits | queues show, but stay below 1 so they settle (p.276); as-is busiest is 0.87. Work per case from a 1,000-case pilot without queues, seed 0. Only once the model has no lint errors |
    | warm-up | 100 / rate days (about 100 arrivals) | queues fill before measuring; 10% extra at 1,000 cases. Only with a default rate |
    | cycle time end, attributes | none | only from an imported file |
    | version | `studio-1` | when no file is given |

  - Browser check (headless Chrome, `python -m http.server`, `studio-check-03.mjs` in the session scratchpad's `pyodide-proof/`): each new call on the preset returns the same JSON as native Python, bit for bit (lint, both default calls, suggestions, apply C1-C4, two summaries, compare). Run still equals the parity fixture (8.6 s, 02 had 7.9 s; the extra metrics cost about 10%). Suggestions stay available after a bpmn-js import/saveXML round trip of the as-is and of the full design, and undo from the round-tripped full design gives back the as-is parameters exactly. A task added with the Modeler makes `apply_suggestion` refuse, `suggestions.available` false, lint shows REACH errors, and `default_parameters` marks only the new task. No console errors.
  - For 04: call `default_parameters(xml, params)` after import and after each diagram edit. An entry is shown as a default while its rationale starts with `Studio default.`, so when the user edits a value, give it a new rationale (e.g. "Set in the studio."). Defaults never recompute once set: the arrival rate is demand, so it mustn't move when the design changes. A lane the file leaves out (unlimited in the file format) gets capacity 1. A TOML writer for export isn't in Pyodide (`tomllib` only reads); `tomli-w` is pure Python on PyPI, or write it in JS.
  - For 05: `lint_xml` raises on XML that isn't one BPMN process, so show the error message and block Run there too.
  - For 06: `compare` raises on mismatched settings; show its message as the "not comparable" reason. The default run with all metrics is about 8.6 s for 1,000 cases × 10 replications.
  - For 07: `suggestions(xml)` gives the panel content and whether it's enabled. Applying replaces all parameters with the catalog's, so warn that hand-set values are lost. "Back to preset" is `apply_suggestion(xml, [])` while still available, or reload the preset files after a hand edit.
