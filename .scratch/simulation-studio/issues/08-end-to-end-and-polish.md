# 08: End to end and polish

**What to build:** The demo path works start to finish: load the preset, run, pin baseline, apply all four suggestions, add a hand edit, run again, compare, export. With the notebook's case count, replications and seed, the studio's full-design saving matches the report's within rounding. Layout works at laptop width and stays readable at phone width. README covers serving and using the studio. Report page links to it in its evaluation section.

**Blocked by:** 05, 06, 07

**Status:** done

- [x] Demo path checked in headless Chrome with no console errors
- [x] Studio's full-design saving equals the report's for the same settings
- [x] Readable at 390 px width, no horizontal page scroll
- [x] README explains serving both pages and the studio's first-load wait
- [x] All studio text in the content file

## Comments
- 2026-11-05: claimed. Implementer started.
- 2026-11-06: done.
  - Parity: `test_the_studio_gives_the_reports_full_design_saving_with_the_reports_settings` in `tests/test_studio.py` runs `bpmopt.studio` with the meta of `web/results.json` (2,000 cases, 30 runs, seed 42) and gets the report's full-design cycle time, saving and share exactly (36.25 days, 95% CI 32.00 to 40.50). It takes about a minute. In headless Chrome the same settings give the same numbers bit for bit (53 s and 48 s for the two runs).
  - Demo path (headless Chrome, `studio-check-08.mjs` and `native-08.py` in the scratchpad `pyodide-proof/`): load, run, pin, apply C1-C4, double the mode and max of Deploy, draw a task between Deploy and Start live operation, back to preset, restore, run, compare (21.5 days saved), export. The exported pair loads in `load_parameters` and reruns natively to the same replication means and saving. No console errors on either page.
  - Polish:
    - Diagram fit: the page fits on `import.done` into the area right of the palette, at a scale of at least 0.2 (on a phone you see the start and pan). `params-panel.mjs` no longer zooms itself.
    - Run, its settings line and the model check now sit right under the diagram. Suggestion cards fold the driver, effect and trade-off note into `<details>` (the open state survives re-renders); the trade-off chips stay visible. Cards went from about 830 px to about 230 px tall at 1366 px width, and Run is on the first screen at 1366x900.
    - "Back to the as-is model" keeps the edited design and offers "Restore my edited model" (`#restore-edit`) until the next edit or step. `panel.name()` was added so the restore keeps the export's file name.
    - Report page: a `studio_try` label with the report's settings and a link at the end of the evaluation section. The label is in the schema and, added by hand like in 02, in `results.json` and `fake_results.json`. `<link rel="icon" href="data:,">` added, so the report's favicon 404 is gone.
    - README: "The report and the studio" covers serving, the first-load wait, the demo steps and how to get the report's saving in the studio.
    - 02's `studio-check.mjs` now reads `#result-ct-mean` and compares the mean only (03 added median and P90). 07's check still passes except its text check, since that text is folded now.
  - For review: the same scripted hand edit gave slightly different results in two sessions (127.2 vs 126.4 days). Likely cause, not confirmed: a drawn task gets a random ID, and the random streams depend on element IDs. Export and re-import reproduce exactly. A hand-edited design still exports under the last suggestion name (e.g. `as_is_C1_C2_C3_C4.bpmn`).
- 2026-11-06: code review fixes.
  - Errors: studio functions raise `StudioError` (a `ValueError` with code and data, `bpmopt.studio.errors`); the worker passes `{code, data}` and the page renders the `[errors]` table of `studio.en.toml`. No Python message or `HTTP ${status}` reaches the page. `params_from_toml` moved into the seam. Parameter rules the panel can break carry a `rule` (`parameters.ParameterError`).
  - Cycle time end: "Cycle time ends at" under Run settings (a task or the end events), through `set_parameter(..., "cycle_time", {"ends_at": id or None})`.
  - One implementation each: `parameters.element_ids`, `restrict` / `restrict_tables`, `entry_key` / `split_entry`; `analysis.work_per_case`; `scenarios.model_combo`; `Catalog.scenario_tables` (replaces `_preset_design`). `_ModelFiles` lists only the catalog's files.
  - `bpmopt.studio` is now a package (runs, defaults, suggestions, diff, reading, toml_writer, errors); `__init__` re-exports what the worker calls.
  - Page: shared `dom.mjs` (`el`, formatters, entry names) and `errors.mjs`; the results panel takes the pairing settings from `paired_on` and compare's error data; dead `fmt` removed.
  - A hand-edited design (diagram or value) exports as `<name>_edited`. Reset to fixed keeps its basis (10,000 draws, seed 0) in the rationale.
  - Tests: `test_studio_errors.py` (every code, its data and text), cycle time end, rationale, `paired_on`, the default arrival rate pinned, results files' text equals `load_page_text()`.
  - Spec and README updated (random IDs of drawn elements). Browser: 08 demo path and parity pass (36.25 days, exact), 07 passes with its text check reading folded cards, new `studio-check-review.mjs` checks the cycle time end, error texts and export name.
