# 02: Case and activity groups in the results file and the notebook

**What to build:** `src/bpmopt/clustering.py` builds the `clusters` section; schema version 5; a notebook section that runs it and shows the tables.

**Blocked by:** 01

**Status:** done

- [x] Section validates against the schema, group sizes add up to the case count
- [x] Notebook section between the planted effects and the redesign
- [x] Threat to validity for the groups

## Comments

- 2026-11-07: claimed.
- 2026-11-07: done. `src/bpmopt/clustering.py` builds `clusters` (schema v5): case groups by size with loops, outcomes, profile and the most common path; activity groups in process order. Notebook section 9 runs it, with a note on what the groups show. Threat "The groups depend on choices" added. Full suite passes.
