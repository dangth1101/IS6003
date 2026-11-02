# 15: Redesign (Phase 5)

**What to build:** The student decides the redesign from the ML drivers, the baseline and the qualitative analysis. Each change goes into the change catalog with the driver it targets, the Appendix A heuristic, the expected effect and its Devil's Quadrangle trade-off (§8.1.3). The to-be BPMN model lints clean. Each change is switchable on its own, either as a parameter override or as a separate model variant, so the scenario runner can simulate every combination.

**Blocked by:** 13, 14

**Status:** ready-for-human

- [ ] Every change points to a driver from ticket 14 and a named heuristic from Appendix A
- [ ] No change removes a quality check without stating the trade-off
- [ ] To-be model lints with zero errors
- [ ] Every combination of changes resolves to a valid model and parameter set
- [ ] Number of changes is small enough that 2^k scenarios stay practical (about 3 to 5)

## Comments

- Redesign candidates from the student's answers (`models/as_is_changelog.md`, answered questions 3 and 4): rerun only the failed check after "Fix defects" (the as-is model reruns all four, and the student says this can be optimized), and run the checks in parallel. Both target the QC lane, which is now the main queue (Phase 1 draft, issues 1 to 3).
