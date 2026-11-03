# 15: Redesign (Phase 5)

**What to build:** The student decides the redesign from the ML drivers, the baseline and the qualitative analysis. Each change goes into the change catalog with the driver it targets, the Appendix A heuristic, the expected effect and its Devil's Quadrangle trade-off (§8.1.3). The to-be BPMN model lints clean. Each change is switchable on its own, either as a parameter override or as a separate model variant, so the scenario runner can simulate every combination.

**Blocked by:** 13, 14

**Status:** done

- [x] Every change points to a driver from ticket 14 and a named heuristic from Appendix A
- [x] No change removes a quality check without stating the trade-off
- [x] To-be model lints with zero errors
- [x] Every combination of changes resolves to a valid model and parameter set
- [x] Number of changes is small enough that 2^k scenarios stay practical (about 3 to 5)

## Comments

- Redesign candidates from the student's answers (`models/as_is_changelog.md`, answered questions 3 and 4): rerun only the failed check after "Fix defects" (the as-is model reruns all four, and the student says this can be optimized), and run the checks in parallel. Both target the QC lane, which is now the main queue (Phase 1 draft, issues 1 to 3).
- Done. The student delegated the design to Claude and approved keeping all four changes on 2026-11-03 (2^4 = 16 scenarios). C1 run the four checks in parallel (Parallelism, A.3, structural), C2 retest only what was fixed (Activity elimination, A.2, structural, the student's idea), C3 triage risky cases into an extended requirements version (Triage, A.2, parameters: `Task_SpecifyRequirements` and `Gateway_TestSplit`), C4 one more QC tester (Extra resources, A.4, `Lane_QualityControl` 8 to 9). Why and what each costs: `models/to_be_changelog.md`.
- Files: catalog `models/to_be.catalog.toml`; models `models/to_be.bpmn` (full to-be, C1+C2, process `Process_AppDevelopment_ToBe`), `models/to_be_c1.bpmn`, `models/to_be_c2.bpmn`, all with DI. Tests in `tests/test_to_be_model.py`.
- G7: the to-be files have 31 to 33 flow nodes, so each has one G7 warning and nothing else; the as-is still lints fully clean. The student accepted this (sub-processes are outside the supported subset). Tests assert "no errors, only G7". "Retest" was added to the linter's G6 verb list.
- C3 is written so a simple internal app (complexity 1, security level 1) is unchanged: the requirements base is scaled by 0.8 with the coefficients raised, and the `Gateway_TestSplit` intercept goes from -3.0 to -2.6 while complexity drops 0.6 to 0.4 and security level 0.5 to 0.3. Only steps above 1 pay more upfront and get fewer defects. Effect sizes are assumptions; list them in the threats to validity.
- For 16: load with `load_catalog(MODELS / "to_be.catalog.toml", model=read_bpmn(MODELS / "as_is.bpmn"), params=load_parameters(MODELS / "as_is.params.toml"))`, then `run_scenarios(catalog, n_cases=..., seed=42, replications=R)`, `ablation(scenarios)`, `catalog.entries()` for `changes`. Point `models.to_be.bpmn` at `models/to_be.bpmn` and copy it to `web/models/to_be.bpmn`, since the page loads models from `web/models/` (only `as_is.bpmn` is there now).
- Runtime on this laptop, all 16 scenarios: 300 cases x R=5 took 10 s (0.13 s per run); 1,000 cases x R=10 took 61 s (0.38 s per run). Roughly linear in cases, so 2,000 cases x R=30 is about 6 minutes.
- Rough savings, 1,000 cases x R=10, seed 42 (as-is mean 147.9 days): C1 alone 21.8 [18.3, 25.4], C2 alone 34.1 [17.0, 51.1], C3 alone 21.3 [6.5, 36.1], C4 alone 17.6 [3.9, 31.2], full design 42.8 [26.1, 59.6], best combination C1+C2+C4 45.7. The CIs are wide because the as-is runs close to QC saturation, so replications vary a lot; R=30 should narrow them.
- Worth saying on the page: the changes overlap. Once C1 and C2 drain the QC queue (QC busy about 0.49 in the full design), C4 adds about 0.5 days and C3 costs about 2.8 (`full_minus`), because C3 puts more work on the business unit lane (0.75 to 0.83). C3 still pays off on its own and in pairs with C1. The student kept all four; the ablation shows this honestly.
