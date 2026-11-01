# 07: Case attributes and the parameter file

**What to build:** Each simulated case gets attributes drawn from distributions in the parameter file: project type, complexity, number of integrations, security level, requesting unit, team workload at start. XOR branch probabilities can be either fixed or a logistic function of case attributes. Task durations are triangular distributions. Every parameter entry carries a rationale, and an assumptions table (parameter, value, rationale) is generated from the file into the results.

**Blocked by:** 03

**Status:** done

- [x] Case attributes appear on every log row of the case
- [x] An attribute-dependent branch probability shows up in the log (e.g. high complexity loops back more often)
- [x] Parameter file is human-editable and validated on load, with clear errors for missing or unknown element IDs
- [x] A parameter entry without a rationale fails validation
- [x] Assumptions table in the results validates against the schema

## Comments

- From review of 01: `load_parameters` reads `rationale` from the file but doesn't keep or require it yet. That belongs here. The seed is also passed twice (to `simulate` and `build_results`); worth bundling the run config when the parameter file grows.
- Done. Tests in `tests/test_case_attributes.py` (simulator seam), `tests/test_parameters.py` (loading and checks) and `tests/test_results.py` (assumptions table).
- The file format is written out at the top of `src/bpmopt/parameters.py`. Every entry is a table with one value key and a `rationale`. Unknown sections, unknown keys and an empty rationale are errors on load.
- Attributes: `[attributes.<name>] distribution = ...` with `{ choice = [...], weights = [...] }` (all labels or all numbers), `{ poisson = mean }` or `{ triangular = [min, mode, max] }`. No names are hardcoded, so 10 picks the six from the spec. A name can't clash with a log column.
- Log: one column per attribute after `LOG_COLUMNS`, in file order, same value on every row of the case. Drawn at arrival, so they're all known at case start (11, 12). RNG: one stream per case and attribute, `[seed, 3, case_id, crc32(name)]`.
- Branches: each flow is a number, `"rest"` or `{ logistic = { intercept = ..., <numeric attr> = coef, <label attr> = { label = coef } } }`. A logistic branch needs exactly one other branch, set to `"rest"`, so it only fits two-way splits. `Parameters.branch_probabilities` now holds `Branches` objects; call `.probabilities(attributes)` to get a dict.
- Flow analysis raises if a split is logistic, since `T / (1 - E[r])` isn't the mean cycle time when r varies by case. For the 08 cross-check, use a fixed-branch copy of the params or compare per attribute group.
- Durations: `{ fixed = x }` or `{ triangular = [min, mode, max] }`, with `.mean` = (min + mode + max) / 3. Durations don't depend on attributes yet. If 10 wants e.g. build time to scale with complexity, that's a new duration kind; for now complexity only acts through rework.
- Checks against the model: `load_parameters(path, model=...)` or `check_parameters(params, model)`. Missing tasks or XOR-splits, unknown task, lane and gateway IDs, and branch keys that don't match the outgoing flows are listed in one error. `simulate` runs the same check first. For 13: a scenario that removes a task has to drop its entry from the overrides too, or the check fails.
- Assumptions: `assumptions(params)` builds the rows from the parsed values, not the file text, so scenario overrides show as simulated. `build_results` fills the section. Rationales sit in `params.rationales`, keyed by entry (`tasks.Task_X`, `arrivals`); an override in code needs one there too.
- "Team workload at start" is drawn like the others, as the ticket says. The real WIP at arrival could be a derived feature in 11, computed from the log.
