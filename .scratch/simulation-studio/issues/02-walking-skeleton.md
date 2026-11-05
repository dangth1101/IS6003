# 02: Studio walking skeleton

**What to build:** The thinnest end-to-end path. `web/studio/index.html` loads Pyodide in a Web Worker, installs the committed `bpmopt` wheel, and shows the as-is preset in the bpmn-js Modeler. A Run button simulates it through a new `bpmopt.studio.simulate_summary(xml, params, n_cases, seed, replications)` and shows mean cycle time with its 95% CI. Adds reading BPMN and parameters from strings / dicts, the wheel build script, and the wheel freshness test. The report page and the studio link to each other.

**Blocked by:** 01

**Status:** done

- [x] `simulate_summary` on the as-is preset gives the same per-replication means as `run_scenarios` for the empty scenario (same seed, cases, replications)
- [x] `read_bpmn` and `load_parameters` keep their file APIs; new string / dict entry points are tested
- [x] A test fails when the committed wheel is stale against `src/`
- [x] In headless Chrome on a local server: Pyodide loads with visible progress, the preset renders, Run shows the mean cycle time, no console errors
- [x] Studio text comes from a content file

## Comments
- 2026-11-05: claimed. Implementer started.
- 2026-11-05: done.
  - API: `bpmopt.studio.simulate_summary(xml, params, n_cases, seed, replications, progress=None)` returns `{n_cases, seed, replications, cycle_time: {mean: {value, ci_low, ci_high}}, replication_means}`. `cycle_time` is shaped like a scenario's, so 03 can add `median` / `p90` next to `mean`. `progress(done, total)` is called after each replication.
  - New readers: `bpmn.parse_bpmn(xml)` and `parameters.parse_parameters(raw, model=None)`. `read_bpmn` and `load_parameters` now call them; their APIs didn't change. `scenarios._estimate` is now public as `estimate`, so the studio's CI code is the runner's.
  - Files: `src/bpmopt/studio.py`, `src/bpmopt/content/studio.en.toml`, `scripts/build_studio.py`, `tests/test_studio.py`, `tests/fixtures/studio_parity.json`, and `web/studio/` (`index.html`, `worker.mjs`, the wheel, `presets/as_is.*`, `studio.en.json`).
  - Rebuild: `uv run python scripts/build_studio.py` after any change under `src/bpmopt/` or to `models/as_is.*`, then commit `web/studio/`. The wheel build is reproducible, so an unchanged source gives the same bytes. Tests fail while the wheel, the presets or `studio.en.json` are stale, or when the worker names a different wheel file.
  - Parity fixture: `tests/fixtures/studio_parity.json` (as-is, seed 42, 1,000 cases, 10 replications), made with `run_scenarios` on the empty scenario. pytest and the browser check both match it exactly. Don't regenerate it without finding out why the numbers moved.
  - Worker protocol: the page posts `{id, call, args}` where `call` is a `bpmopt.studio` function name, and gets back `result` / `error` / `progress`. `params_from_toml` turns a parameter file's text into the dict the studio takes (04 can use it for import). The worker sends loading stages as label keys.
  - Report page: one link added (`studio_link` label in `page.en.toml` and in the schema). I added the label to `web/results.json` and `web/fixtures/fake_results.json` by hand, the same line the notebook writes, so no notebook rerun was needed.
  - Browser check (headless Chrome 156, `python -m http.server`): loaded in 7.1 s with 4 visible stages, 48 shapes in the Modeler, Run took 7.9 s (10 replications), shown 147.9 days (95% CI 126.6 to 169.1), replication means and CI equal the fixture bit for bit, no console errors. No horizontal scroll at 390 px. The report page loads and its link opens the studio; its only console error is the old `favicon.ico` 404. The check script (puppeteer-core, not in the repo) is `studio-check.mjs` in the session scratchpad's `pyodide-proof/`; it reads the results element's `data-summary` to compare full-precision numbers.
  - For 03: the studio module must keep off `ml`, `features`, `results` and `planted` (a test checks a fresh interpreter). `apply_suggestion` needs the catalog files in the browser: add them to `PRESETS` in `scripts/build_studio.py` (and to the preset test), or pass their text in. `load_catalog` reads by path today.
  - For 08: the Modeler palette covers the left edge of the diagram after `fit-viewport`.
