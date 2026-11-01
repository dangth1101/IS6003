# 07: Case attributes and the parameter file

**What to build:** Each simulated case gets attributes drawn from distributions in the parameter file: project type, complexity, number of integrations, security level, requesting unit, team workload at start. XOR branch probabilities can be either fixed or a logistic function of case attributes. Task durations are triangular distributions. Every parameter entry carries a rationale, and an assumptions table (parameter, value, rationale) is generated from the file into the results.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] Case attributes appear on every log row of the case
- [ ] An attribute-dependent branch probability shows up in the log (e.g. high complexity loops back more often)
- [ ] Parameter file is human-editable and validated on load, with clear errors for missing or unknown element IDs
- [ ] A parameter entry without a rationale fails validation
- [ ] Assumptions table in the results validates against the schema

## Comments

- From review of 01: `load_parameters` reads `rationale` from the file but doesn't keep or require it yet. That belongs here. The seed is also passed twice (to `simulate` and `build_results`); worth bundling the run config when the parameter file grows.
