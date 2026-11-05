# Spec: Simulation studio, an interactive what-if tool for BPMN models

**Status:** ready-for-agent

## Problem Statement

The report page (`web/index.html`) shows results the notebook computed ahead of time. A viewer can toggle the four precomputed redesign changes, but can't load their own model, change a parameter, edit the diagram, or run a simulation. For the submission I want a tool where the lecturer (or I, in the demo) can:

- import a BPMN model, or start from the bank's as-is model;
- simulate it and see where time goes;
- change the diagram the way the optimization suggests, with one click or by hand;
- rerun the simulation and see the result next to the baseline.

The tool must use the same tested simulator as the notebook, so the two can never disagree, and it must stay static (GitHub Pages, no backend), like the report page.

## Solution

A second static page, the **studio**, next to the report page. It runs the `bpmopt` Python package in the browser with Pyodide (CPython compiled to WebAssembly) inside a Web Worker, so the page stays responsive while it simulates. The diagram is shown and edited with the bpmn-js Modeler. A new thin module, `bpmopt.studio`, offers JSON-in / JSON-out functions the page calls: lint, propose default parameters, simulate with replications, and compare two runs under the same seeds.

The flow on the page:

1. Load the as-is preset (one click), or import a `.bpmn` file and, optionally, its `.params.toml`.
2. See lint results live. Errors block simulation; warnings don't.
3. Set parameters by selecting an element: task duration, XOR branch probabilities, lane capacity. Global settings: arrival rate, warm-up, number of cases, replications, seed.
4. Run. See cycle time (mean, median, P90 with 95% CI), processing vs waiting, cycle time efficiency, utilisation per lane, rework per XOR gateway, waiting per activity.
5. Pin that run as the baseline.
6. Apply suggested changes (C1-C4 from the change catalog, one click each, when the model is the as-is preset), and/or edit the diagram by hand.
7. Run again and compare: saving with a paired 95% CI, and before/after per lane and per activity.
8. Export the edited BPMN and its parameter file.

## User Stories

1. As the lecturer, I want to open the studio from a link with no install, so that I can try it during grading.
2. As the lecturer, I want to load the bank's as-is model and its parameters in one click, so that I can start from the case the report is about.
3. As a user, I want to import my own `.bpmn` file, so that I can try the method on another process.
4. As a user, I want to import a `.params.toml` file next to the model, so that I don't have to type every parameter again.
5. As a user, I want missing parameters filled with visible defaults, so that an imported model can run at once and I can see what was assumed.
6. As a user, I want to see the book's lint rules (the same linter as the report) on the current diagram, updated as I edit, so that I keep the model correct.
7. As a user, I want simulation blocked while the model has lint errors, with the reason shown, so that I never get results from a broken model.
8. As a user, I want to select a task and edit its triangular duration (min, mode, max), so that I can test an estimate.
9. As a user, I want to select an XOR split and edit its branch probabilities, so that I can test a different rework rate.
10. As a user, I want to select a lane and edit its capacity, so that I can test adding a person.
11. As a user, I want to set arrival rate, warm-up, number of cases, replications and seed, so that I control the experiment.
12. As a user, I want a progress indicator and a rough time estimate while it runs, so that I know the page hasn't frozen.
13. As a user, I want cycle time mean, median and P90 with 95% CIs over replications, so that I see the uncertainty.
14. As a user, I want processing time, waiting time and cycle time efficiency (§7.1.2), so that I see how much is waiting.
15. As a user, I want utilisation per lane, rework rate per XOR gateway and waiting per activity, so that I see where time is lost.
16. As a user, I want to pin a run as the baseline, so that later runs are compared against it.
17. As a user, I want later runs compared with the baseline under the same seeds (common random numbers), with the saving and a paired 95% CI, so that the difference comes from the design and not from luck.
18. As a user, I want a suggestions panel listing C1-C4 with the driver, the Appendix A heuristic and the Devil's Quadrangle trade-off, so that I know why each change exists.
19. As a user, I want to apply a suggestion with one click and see the diagram and parameters change, so that I can try the optimization without redrawing it.
20. As a user, I want to undo a suggestion, so that I can try combinations.
21. As a user, I want to edit the diagram by hand after applying suggestions (add, remove, reconnect elements), so that I can try my own ideas.
22. As a user, I want a new task I draw to get a default duration I can see and edit, so that it can run.
23. As a user, I want to export the edited BPMN and its parameter file, so that I can keep my design or load it in the notebook.
24. As the lecturer, I want the studio to give the same result as the notebook for the same model, parameters, case count, replications and seed, so that I can trust it.
25. As a user, I want the studio usable at laptop width and readable at phone width, so that it works in a demo.
26. As a user, I want links between the studio and the report page, so that I can move between the story and the tool.
27. As the student, I want all studio text in a content file, so that a Vietnamese version later is a content edit.

## Implementation Decisions

- **Runtime:** Pyodide, pinned version from a CDN, loaded in a Web Worker. The page talks to the worker with messages (load model, lint, simulate, compare, progress, error). No backend.
- **Package delivery:** `bpmopt` is loaded into Pyodide as a pure-Python wheel built from `src/`. The wheel is committed under the studio folder and rebuilt by a script; a test fails if the committed wheel is stale against the source. Only the modules the studio needs may be imported in the browser (no scikit-learn or SHAP on that path).
- **Dependency versions:** Pyodide ships its own NumPy, pandas, SciPy. If they differ from the pinned versions, the research ticket decides how to handle it (e.g. a version-tolerant code path or a matching Pyodide release). SimPy and jsonschema come from PyPI via micropip, pinned.
- **Python seam, `bpmopt.studio`** (JSON-serialisable in and out, no file paths):
  - `lint_xml(xml)` → list of violations (rule, severity, element, message).
  - `default_parameters(xml, params=None)` → a full parameter set for the model: given entries are kept, missing ones get documented defaults (rationale "studio default"), and entries for elements no longer in the model are dropped. Returns which entries are defaults.
  - `simulate_summary(xml, params, n_cases, seed, replications, progress=None)` → the metrics in user stories 13-15, each with mean over replications and a 95% CI, plus the per-replication cycle time means (kept for pairing).
  - `compare(baseline, variant)` → saving (days and share of the baseline mean) with a paired 95% CI, plus before/after per lane and per activity. Both runs must share seed and replications; otherwise it refuses.
  - `apply_suggestion(xml, params, change_ids)` → the as-is preset's model and parameters for that set of catalog changes, using the existing catalog (`models/to_be.catalog.toml` and its model files). Only valid when the current model is the unmodified preset or a preset with suggestions applied; the page disables suggestions once the diagram is hand-edited, and says why.
  - Reading BPMN and parameters from strings / dicts is added to `bpmn` and `parameters` without changing their file-based APIs.
- **Same numbers as the notebook:** the studio's simulate path is the same `simulate` + replication seeds (`replication_seeds`) as the scenario runner, so the same inputs give the same per-replication means.
- **Parameters in the UI:** tasks (triangular min/mode/max, plus any attribute scaling from an imported file shown read-only), XOR splits (fixed probabilities editable; logistic branches from an imported file shown read-only with a "reset to fixed" option), lanes (capacity), arrivals (rate), warm-up, cycle time end (as in the file, or the end events by default). Case attributes come only from an imported parameter file; an imported model without one has none.
- **Defaults for a new or imported model:** documented in the studio module and shown on the page (e.g. task triangular [1, 2, 4] days, XOR splits equal branches, lane capacity 1, arrival rate chosen so the busiest lane is below full). Exact values are decided in the ticket and listed with their rationale.
- **Performance defaults:** 1,000 cases and 10 replications, editable. The worker reports progress per replication.
- **Page:** `web/studio/` with its own `index.html`. bpmn-js Modeler pinned from a CDN, a chart library pinned as on the report page. Layout: diagram in the middle, element/parameter panel on the side, lint and results below. The report page and the studio link to each other. All UI text lives in a content file (like `src/bpmopt/content/page.en.toml`).
- **Report page:** unchanged except the link. It stays the submission's write-up; the studio is the demo.

## Testing Decisions

- **Main seam: `bpmopt.studio`, tested with pytest** like the rest of the package. Inputs are BPMN XML strings and parameter dicts; outputs are JSON-shaped dicts. Tests:
  - `simulate_summary` on the as-is preset gives the same per-replication means as `run_scenarios` for the empty scenario with the same seed, cases and replications.
  - `apply_suggestion` for each catalog change set gives the same model and parameters as `catalog.resolve`, and its simulation matches the scenario runner.
  - `compare` of the as-is with the full design matches the scenario runner's paired saving and CI.
  - `default_parameters` fills a model with no parameters so it simulates, keeps given entries untouched, drops entries for removed elements, and marks which entries are defaults.
  - `lint_xml` gives the same violations as `lint` on the file.
  - `compare` refuses runs with different seeds or replications.
- **Wheel freshness:** a test rebuilds or hashes the package and fails when the committed wheel is stale.
- **Browser path:** checked in headless Chrome against a local static server: Pyodide loads, the preset runs, a suggestion applies, a hand edit (add a task) runs, the comparison shows, no console errors. This is an acceptance check per ticket, not a unit test.
- **Prior art:** `tests/test_scenarios.py`, `tests/test_to_be_model.py`, `tests/test_results.py`.

## Out of Scope

- ML (cycle time prediction, SHAP) in the studio. It stays in the notebook.
- Automatic suggestions for an arbitrary imported model. Suggestions exist only for the as-is preset (C1-C4).
- Editing case attributes or logistic branch formulas in the UI (shown read-only when imported).
- BPMN elements outside the supported subset (the linter already rejects them).
- Any backend, accounts, saving to a server, or sharing state between viewers.
- Vietnamese text (a later content edit).

## Further Notes

- Part of the IS6003 submission (student decision, 2026-11-05). The report page and notebook are done; this is the interactive demo.
- First load downloads Pyodide and its packages (tens of MB); say so on the page and show progress.
- Browser speed is lower than native Python; keep defaults small and let the user raise them.
- Like the report page, the studio needs a static server (file:// blocks fetches). The README's serving instructions cover both pages.
