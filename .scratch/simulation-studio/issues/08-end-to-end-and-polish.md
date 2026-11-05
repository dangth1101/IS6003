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
