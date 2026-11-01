# IS6003: time optimization of the app development process

Plan: `PLAN.md`. Spec and tickets: `.scratch/bpmn-time-optimization/`.

## Layout

- `src/bpmopt/`: the Python package (BPMN reader, linter, simulator, analysis, results export)
- `tests/`: pytest suite, fixture models in `tests/fixtures/`
- `notebooks/time_optimization.ipynb`: runs the whole path and writes `web/results.json`
- `web/`: the static page, `results.json` and the BPMN models it shows

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
