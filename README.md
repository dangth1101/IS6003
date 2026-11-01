# IS6003: time optimization of the app development process

Plan: `PLAN.md`. Spec and tickets: `.scratch/bpmn-time-optimization/`.

## Layout

- `models/`: the corrected as-is model (`as_is.bpmn`, the source of truth for the process), its change log against the original `current_process.bpmn`, its parameter file (proposed defaults for a bank IT division), and `as_is_planted_effects.md`, the attribute effects put into those parameters on purpose, to check the ML findings against
- `src/bpmopt/`: the Python package (BPMN reader, linter, simulator, flow analysis, log analysis, CSV export of the event log, case features and ML, scenario runner, results export)
- `src/bpmopt/schema/results.schema.json`: the results contract between the notebook and the page
- `src/bpmopt/content/page.en.toml`: all page text, copied into every results file
- `tests/`: pytest suite, fixture models in `tests/fixtures/`
- `notebooks/time_optimization.ipynb`: runs the whole path and writes `web/results.json`
- `web/`: the static page, `results.json` and the BPMN models it shows
- `web/fixtures/`: a fake results file with every section filled, and its models, for building the page

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
cd web && ../.venv/bin/python -m http.server 8000             # page at http://localhost:8000
```

The page needs a static server. Opening `index.html` as a file doesn't work, because browsers block file fetches.

To see the page with the fake data, open http://localhost:8000/?results=fixtures/fake_results.json. Model paths in a results file are relative to that file.

Parameter files (TOML) set arrivals, case attributes, durations, branch probabilities, lane capacities and the warm-up. The format is described at the top of `src/bpmopt/parameters.py`. Every entry needs a rationale, which ends up in the assumptions table on the page. A duration can scale with the case attributes, and a two-way XOR-split can be a logistic of them; every such effect in `models/as_is.params.toml` must be listed in `models/as_is_planted_effects.md` (a test checks).

`bpmopt.event_log.export_csv(log, path)` writes a log as CSV in the layout of the book's event log (Fig. 11.4), with ready, start and end times instead of one timestamp.

Redesign changes go in a change catalog (TOML): one entry per change with its driver, heuristic, expected effect and trade-off, plus the parameter overrides or the BPMN file it needs. The format is described at the top of `src/bpmopt/scenarios.py`, and `tests/fixtures/sequence.catalog.toml` is a small example. `run_scenarios` simulates every combination of changes with the same seeds per replication (30 by default).

To change page text, edit `src/bpmopt/content/page.en.toml` and rerun the notebook. A new label also needs adding to the `labels` list in the schema; a test checks the two match.
