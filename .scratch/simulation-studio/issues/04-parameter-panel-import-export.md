# 04: Parameter panel, import and export

**What to build:** Selecting a task, XOR split or lane opens a side panel to edit its parameters (triangular duration; fixed branch probabilities; capacity). Attribute scaling and logistic branches from an imported file are shown read-only, with "reset to fixed" for logistic branches. A settings panel holds arrival rate, warm-up, cases, replications and seed. Import a `.bpmn` and, optionally, a `.params.toml`; missing entries are filled by `default_parameters` and shown as defaults. A newly drawn task gets a default duration. Export the current BPMN and parameter file.

**Blocked by:** 02, 03

**Status:** done

- [x] Editing a duration, probability or capacity changes the next run's result in the expected direction
- [x] Importing a model without a parameter file runs at once, with every default visible
- [x] Exported BPMN + parameters re-import to the same result under the same seed
- [x] Exported parameters load in the notebook's `load_parameters`
- [x] Checked in headless Chrome, no console errors

## Comments
- 2026-11-05: claimed. Implementer started.
- 2026-11-05: done.
  - API (`src/bpmopt/studio.py`, tests in `tests/test_studio_params.py`):
    - `set_parameter(xml, params, entry, fields)` → `{params, defaults, dropped}`. `entry` is `tasks.<id>`, `gateways.<id>`, `lanes.<id>`, `arrivals` or `warm_up`; `fields` replaces the entry (e.g. `{"duration": {"triangular": [1, 2, 4]}}`) with the rationale `Set in the studio.`, so it stops being a default. The result goes through `default_parameters` and `parse_parameters(..., model)`, so a bad value or an unknown element raises a `ValueError` that names the entry.
    - `fixed_branches(params, gateway_id)` is "reset to fixed". Each logistic branch becomes its mean probability over 10,000 attribute draws (seed 0), to 3 decimals. `rest` and fixed branches stay. As-is: tests 0.346, plan 0.184, release 0.089.
    - `params_to_toml(params)`: our own small writer instead of `tomli-w`, so no new dependency or micropip install. Same layout as the hand-written files. Round trip tested on every parameter file in the repo.
  - UI: `web/studio/params-panel.mjs` + `params-panel.css`, in an `<aside id="params-panel">` next to the diagram. Interface is in the module header: `load({xml?, params, name})`, `params()` (waits for pending updates), `run()`. Parameter updates go through a queue, so a diagram edit and a value edit can't overwrite each other. Defaults are listed (click one to select it) and drawn with a dashed amber outline on the diagram.
  - Import: one picker for `.bpmn`, `.params.toml` or both. A model without a parameter file starts from studio defaults only. A broken file shows `Couldn't import <file>: ...` and keeps the last good parameters.
  - Browser check (headless Chrome, `studio-check-04.mjs` in the scratchpad `pyodide-proof/`): 28 checks, no console errors. The preset still matches the parity fixture. Longer kick-off, more proposal rework and more QC capacity each moved the next run the expected way. Logistic and scaling show read-only, and reset works. `models/to_be.bpmn` imported bare gets 31 defaults, listed and marked, and runs. A drawn task gets [1, 2, 4], and undo drops it. Export, then `load_parameters` natively, then re-import gives the same parameters, defaults and replication means. No horizontal scroll at 390 px.
  - For 06: Run reads `panel.params()` and `panel.run()`. Settings changes call `onRunChange`, so a pinned baseline can tell when seed, cases or runs no longer match.
  - For 07: after `apply_suggestion`, call `panel.load({xml, params})`. It imports the diagram and refills, so the suggestion's parameters replace the panel's.
  - For 08: most test fixtures (e.g. `tests/fixtures/proposal_rejected.bpmn`) have no diagram layout (DI), so bpmn-js refuses them with "no diagram to display" and the import shows that error. Only files with DI can be imported. Auto-layout is out of scope here.
