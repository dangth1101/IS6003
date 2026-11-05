# 02: Studio walking skeleton

**What to build:** The thinnest end-to-end path. `web/studio/index.html` loads Pyodide in a Web Worker, installs the committed `bpmopt` wheel, and shows the as-is preset in the bpmn-js Modeler. A Run button simulates it through a new `bpmopt.studio.simulate_summary(xml, params, n_cases, seed, replications)` and shows mean cycle time with its 95% CI. Adds reading BPMN and parameters from strings / dicts, the wheel build script, and the wheel freshness test. The report page and the studio link to each other.

**Blocked by:** 01

**Status:** claimed

- [ ] `simulate_summary` on the as-is preset gives the same per-replication means as `run_scenarios` for the empty scenario (same seed, cases, replications)
- [ ] `read_bpmn` and `load_parameters` keep their file APIs; new string / dict entry points are tested
- [ ] A test fails when the committed wheel is stale against `src/`
- [ ] In headless Chrome on a local server: Pyodide loads with visible progress, the preset renders, Run shows the mean cycle time, no console errors
- [ ] Studio text comes from a content file

## Comments
- 2026-11-05: claimed. Implementer started.
