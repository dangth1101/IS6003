# 13: Scenario runner and ablation (Phase 6 machinery)

**What to build:** A change catalog format (ID, title, driver it targets, Appendix A heuristic, expected effect, Devil's Quadrangle trade-off). A scenario is a set of change IDs that resolves to a process model plus parameter overrides. The runner simulates all 2^k scenarios with common random numbers (the same seed per replication across scenarios), R replications each (default 30), and reports mean, median and P90 cycle time with 95% CIs. Ablation views (each change alone, full minus each) are derived from the full factorial. Built and tested with a fixture catalog of two or three changes on fixture models.

**Blocked by:** 04, 07

**Status:** ready-for-agent

- [ ] With a fixture change that removes a fixed amount of work, the measured saving matches the expected value
- [ ] The empty scenario (no changes) reproduces the as-is result exactly under the same seeds
- [ ] All 2^k scenarios appear in the results and validate against the schema
- [ ] Ablation views are consistent with the factorial results
- [ ] Both parameter-only changes and structural changes (a different model file) are supported
