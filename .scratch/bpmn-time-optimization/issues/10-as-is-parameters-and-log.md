# 10: As-is parameters and synthetic event log (Phase 2)

**What to build:** Proposed default parameters for the corrected as-is model (arrival rate, attribute distributions, durations, branch probabilities with attribute effects, lane capacities, warm-up), each with a rationale marked "proposed default". Planted effects are listed explicitly so later ML results can be discussed honestly. Running the simulator gives a synthetic log of a few thousand cases, exportable as CSV.

**Blocked by:** 04, 06, 07

**Status:** ready-for-agent

- [ ] Parameter file covers every task, XOR split and lane in the corrected model and passes validation
- [ ] Every planted attribute effect is listed in one place, so the report can state what the ML should find
- [ ] Log has at least 2,000 cases after warm-up
- [ ] Mean cycle time and rework rates fall in plausible ranges for a bank IT project (stated in the rationale)
- [ ] CSV export opens and matches the book's event log shape (§11.3)
