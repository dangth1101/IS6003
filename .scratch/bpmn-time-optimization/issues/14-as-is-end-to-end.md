# 14: As-is pipeline end to end

**What to build:** The notebook runs the real as-is pipeline top to bottom with one seed: lint both models, generate the synthetic log, compute the baseline, run both ML tasks, write the results file. The page shows real as-is numbers, the value-added data and the ML drivers. The redesign sections still show placeholders. This is the evidence the student uses for the redesign.

**Blocked by:** 05, 08, 09, 10, 11, 12

**Status:** ready-for-agent

- [ ] Notebook runs top to bottom from a fresh kernel without errors
- [ ] Notebook stays thin: each cell calls the package and explains the step, citing the book section
- [ ] Results file validates against the schema
- [ ] Page shows the real baseline, value-added classification, ML metrics and ranked drivers
- [ ] Notebook includes a short section comparing the ML drivers with the planted effects (threat to validity)
