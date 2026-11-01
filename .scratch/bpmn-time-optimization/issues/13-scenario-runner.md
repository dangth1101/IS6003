# 13: Scenario runner and ablation (Phase 6 machinery)

**What to build:** A change catalog format (ID, title, driver it targets, Appendix A heuristic, expected effect, Devil's Quadrangle trade-off). A scenario is a set of change IDs that resolves to a process model plus parameter overrides. The runner simulates all 2^k scenarios with common random numbers (the same seed per replication across scenarios), R replications each (default 30), and reports mean, median and P90 cycle time with 95% CIs. Ablation views (each change alone, full minus each) are derived from the full factorial. Built and tested with a fixture catalog of two or three changes on fixture models.

**Blocked by:** 04, 07

**Status:** done

- [x] With a fixture change that removes a fixed amount of work, the measured saving matches the expected value
- [x] The empty scenario (no changes) reproduces the as-is result exactly under the same seeds
- [x] All 2^k scenarios appear in the results and validate against the schema
- [x] Ablation views are consistent with the factorial results
- [x] Both parameter-only changes and structural changes (a different model file) are supported

## Comments

- Done. Code in `src/bpmopt/scenarios.py`, tests in `tests/test_scenarios.py`. Fixture catalog `tests/fixtures/sequence.catalog.toml`: C1 takes 2 days off Build application (parameter-only), C2 removes Write specification (structural, `sequence_without_spec.bpmn`), C3 adds a developer (lane capacity).
- API: `load_catalog(path, model=..., params=...)` returns a `Catalog`; `catalog.resolve(ids)` gives `(model, params)` for one scenario; `catalog.entries()` is the `changes` section. `run_scenarios(catalog, n_cases=..., seed=..., replications=30)` returns the `scenarios` section. `ablation(scenarios)` gives per change `alone` (saving with CI) and `full_minus`, computed the same way as the page.
- Catalog file: `version`, one `[changes.<ID>]` table per change with `title`, `driver`, `heuristic = { name, ref }`, `expected_effect`, `trade_off = { time, cost, quality, flexibility, note }`. Each entry is checked against the schema's `change` definition on load, so a typo like `cost = "higher"` fails before any simulation.
- Parameter-only change: `[changes.<ID>.overrides.<section>.<element ID>]` in the parameter file layout, with its own rationale. Only `tasks`, `lanes` and `gateways` can be overridden. Arrivals, attributes and the warm-up are the demand, not the design, so they stay fixed. Two changes overriding the same entry is an error, since their combination would be ambiguous.
- Structural change: `[models]` maps a change ID to a BPMN file (relative to the catalog). With more than one structural change, every combination needs its own file, keyed like `"C1+C2"`; a missing one is an error on load. Task, gateway and lane entries the scenario's model doesn't have are dropped, both from the as-is parameters and from overrides. So a removed task needs nothing, and a speed-up of a task another change removes simply has no effect in that combination.
- `load_catalog` resolves and checks all 2^k scenarios up front, so a broken combination fails at once with the scenario named.
- CRN fix in the simulator: durations now come from one stream per case and task (`[seed, 1, case_id, crc32(task_id)]`), like the gateway streams. Before, a case drew all its durations from one stream in order, so removing a task shifted the draws of every later task in that case. Tested: removing Write specification leaves every other duration and every arrival unchanged, and changing Build application leaves all other durations unchanged even with queues. Existing tests still pass; seeds now give different (equally valid) logs than before.
- Replication r uses seed `SeedSequence([seed, r])` (`replication_seeds`), the same for every scenario. Each replication gives a mean, median and P90 per scenario; the estimate is their mean over R with a 95% t-interval. The saving is paired: as-is mean minus scenario mean per replication, then the t-interval of those differences. The t quantile is computed in the module (closed form for whole df), to avoid adding SciPy for one number.
- For 15: provide a catalog TOML next to the to-be model files, with one BPMN per structural change and one per combination of structural changes (so keep structural changes few; parameter-only changes need no file). New tasks in a variant model need a duration override with a rationale on the change that adds them. Each to-be file should lint clean.
- For 16: `build_results` still writes `meta.replications = 1`; set it to R when adding `changes` and `scenarios`. The runtime grows as 2^k x R x n_cases, so check it on the real model before picking n_cases.
