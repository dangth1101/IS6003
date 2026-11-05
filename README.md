# IS6003: time optimization of the app development process

Plan: `PLAN.md`. Spec and tickets: `.scratch/bpmn-time-optimization/`.

## Layout

- `models/`: the corrected as-is model (`as_is.bpmn`, the source of truth for the process), its change log against the original `current_process.bpmn`, its parameter file (proposed defaults for a bank IT division), and the attribute effects put into those parameters on purpose, to check the ML findings against: `as_is.planted_effects.toml` for the notebook, `as_is_planted_effects.md` to explain them. The redesign: `to_be.bpmn` (full to-be), `to_be_c1.bpmn` and `to_be_c2.bpmn` (one structural change each), the change catalog `to_be.catalog.toml`, and why each change exists in `to_be_changelog.md`
- `src/bpmopt/`: the Python package (BPMN reader, linter, simulator, flow analysis, log analysis, CSV export of the event log, case features and ML, scenario runner, results export)
- `src/bpmopt/schema/results.schema.json`: the results contract between the notebook and the page
- `src/bpmopt/content/page.en.toml`: all page text, copied into every results file
- `tests/`: pytest suite, fixture models in `tests/fixtures/`
- `notebooks/time_optimization.ipynb`: runs the whole study (lint, simulation, baseline, value-added, ML, drivers vs planted effects, redesign, all 16 scenarios with 30 replications, ablation) and writes `web/results.json`, plus the event log as CSV in `notebooks/output/` (not committed). Takes about 8 minutes
- `docs/analysis/phase1-qualitative.md`: Phase 1 draft (value-added, waste, issue register, objective), awaiting the student's review
- `web/`: the static page, `results.json` and the two BPMN models it shows (`web/models/`, copied there by the notebook)
- `web/studio/`: the simulation studio, a second static page that runs `bpmopt` in the browser (Pyodide in a Web Worker) on the bpmn-js Modeler. It loads the committed `bpmopt` wheel, the as-is preset in `presets/` and its text in `studio.en.json`, all built by `scripts/build_studio.py`. Its Python side is `bpmopt.studio` (JSON in, JSON out). Runtime decisions: `docs/research/studio-browser-runtime.md`
- `web/fixtures/`: a fake results file with every section filled, and its models, for building the page and for the tests. The real page never reads it

## Setup

Python 3.12+. `uv.lock` pins every dependency, transitive ones included:

```sh
uv sync --extra dev
```

Without uv, pip works too, but it only pins the direct dependencies listed in `pyproject.toml`:

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

## Run

```sh
.venv/bin/pytest                                              # tests
cd notebooks && ../.venv/bin/jupyter execute time_optimization.ipynb   # regenerate web/results.json
cd web && ../.venv/bin/python -m http.server 8000             # page at http://localhost:8000, studio at /studio/
uv run python scripts/build_studio.py                         # rebuild the studio's wheel, preset and text
```

Rebuild the studio after any change under `src/bpmopt/` or to `models/as_is.*`, and commit `web/studio/`. A test fails while the wheel, the preset or the studio text is stale. The studio's default run (as-is preset, seed 42, 1,000 cases, 10 replications) must give the per-replication means in `tests/fixtures/studio_parity.json`, natively and in the browser; a NumPy or Pyodide bump that changes a random stream shows up there first.

`export_results` lints every model it copies, so the page shows the rule check for each. A rework gateway whose training or test cases all went the same way isn't fitted; its ML task carries `skipped` with the reason instead of scores, and the run goes on.

The page needs a static server. Opening `index.html` as a file doesn't work, because browsers block file fetches. Any static server will do. The page has no backend, but it loads bpmn-js from a CDN, so it needs internet access.

## The report and the studio

Both pages are static and come from the same server:

```sh
cd web && python3 -m http.server 8000
```

- Report: http://localhost:8000/. Its evaluation section links to the studio.
- Studio: http://localhost:8000/studio/. "Back to the report" goes the other way.

The studio downloads Python (Pyodide), NumPy, pandas, SciPy and SimPy from a CDN on the first visit, about 36 MB. That takes 5 to 30 seconds depending on the connection, and the page shows each stage. The browser caches the files, so later visits start in a few seconds. Run stays disabled until Python is ready.

A demo takes about five minutes:

1. The as-is model loads by itself. Click Run (1,000 cases, 10 runs, seed 42, about 9 seconds).
2. Click "Pin as baseline" under the results.
3. Apply C1 to C4 under "Suggested changes". Each one changes the diagram and the parameters, and outlines what changed in green. "Why, expected effect and trade-off" opens the reasoning.
4. Edit by hand: select a task and change its duration, or draw a task into a flow. A new task gets a default duration of [1, 2, 4] days. The suggestions switch off after a diagram edit; "Back to the as-is model" turns them on again, and "Restore my edited model" brings the edit back.
5. Run again. The comparison shows the saving with a paired 95% CI and the before and after per lane and per activity.
6. Export BPMN and Export parameters save the design. Both files load in the notebook (`read_bpmn`, `load_parameters`) and import back into the studio.

To reproduce the report's saving in the studio, set 2,000 cases, 30 runs and seed 42 under Run settings, run the as-is model, pin it, apply all four changes and run again. The saving equals the report's exactly (36.3 days, 95% CI 32.0 to 40.5). Each run takes about a minute in the browser. `tests/test_studio.py` checks the same thing natively against `web/results.json`.

## Publish on GitHub Pages

The page is everything in `web/`. GitHub Pages can only serve a branch from its root or from `/docs`, so push `web/` to a branch of its own, `gh-pages`:

1. Rerun the notebook, run the tests and commit `web/` on `main`.
2. Push `web/` as the root of the `gh-pages` branch:

   ```sh
   git subtree push --prefix web origin gh-pages
   ```

3. Once, on GitHub: Settings → Pages → Build and deployment → Source "Deploy from a branch", branch `gh-pages`, folder `/ (root)`.
4. After a minute or two the page is at https://dangth1101.github.io/IS6003/.

After the next notebook run, commit and repeat step 2. Paths in the page are relative, so it works under the `/IS6003/` sub-path. `web/fixtures/` is published too, but only shows with `?results=fixtures/fake_results.json`.

To redeploy on every push to `main` instead, use a GitHub Actions workflow with `actions/upload-pages-artifact` (path `web`) and `actions/deploy-pages`, and set the Pages source to "GitHub Actions".

To see the page with the fake data, open http://localhost:8000/?results=fixtures/fake_results.json. Model paths in a results file are relative to that file.

Parameter files (TOML) set arrivals, case attributes, durations, branch probabilities, lane capacities, the warm-up and where the cycle time ends (`[cycle_time] ends_at`, a task; the as-is model stops at go-live). The format is described at the top of `src/bpmopt/parameters.py`. Every entry needs a rationale, which ends up in the assumptions table on the page. A duration can scale with the case attributes, and a two-way XOR-split can be a logistic of them; every such effect in `models/as_is.params.toml` must be listed in `models/as_is.planted_effects.toml` and in the table of `models/as_is_planted_effects.md` (a test checks both).

`bpmopt.event_log.export_csv(log, path)` writes a log as CSV in the layout of the book's event log (Fig. 11.4), with ready, start and end times instead of one timestamp.

Redesign changes go in a change catalog (TOML): one entry per change with its driver, heuristic, expected effect and trade-off, plus the parameter overrides or the BPMN file it needs. The format is described at the top of `src/bpmopt/scenarios.py`, and `tests/fixtures/sequence.catalog.toml` is a small example. `run_scenarios` simulates every combination of changes with the same seeds per replication (30 by default) and keeps each replication's mean, so any two scenarios can be compared run by run. `ablation` reads each change's saving alone and what the full design loses without it, and `headline` picks the change the full design needs most and the fastest combination. `build_results(..., catalog=catalog, scenarios=scenarios)` adds them to the results, with each change's overrides in the assumptions table, and the results file checks them against the scenarios. A saving share is the mean saving over the as-is mean cycle time, with the saving's CI over the same mean (`saving_share`).

To change page text, edit `src/bpmopt/content/page.en.toml` and rerun the notebook. A new label also needs adding to the `labels` list in the schema; a test checks the two match. Don't type results into the text: section paragraphs and threats take placeholders such as `{alone_C2}` that the page fills from `results.json` (the list is at the top of the content file), and a test rejects numbers other than citations.
