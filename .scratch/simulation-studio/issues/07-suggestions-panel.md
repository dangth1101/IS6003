# 07: Suggestions panel

**What to build:** A panel listing C1-C4 from the change catalog with title, driver, Appendix A heuristic, expected effect and Devil's Quadrangle trade-off. Each has apply / undo. Applying changes the diagram (structural changes load the matching catalog model) and the parameters (overrides), and highlights what changed. Available only while the model is the as-is preset with suggestions applied; after a hand edit the panel is disabled and says why, with a "back to preset" option.

**Blocked by:** 04

**Status:** done

- [x] Applying any combination of C1-C4 gives the same model and parameters as `catalog.resolve`
- [x] Undo returns to the previous combination exactly
- [x] After a hand edit the panel is disabled with the reason shown
- [x] Checked in headless Chrome, no console errors

## Comments
- 2026-11-05: claimed. Implementer started.
- 2026-11-05: done.
  - API (`src/bpmopt/studio.py`, tests in `tests/test_studio_suggestions.py`):
    - `suggestions(xml, preset, params=None)` now also returns `applied` (the changes the design carries, catalog order: a structural one when the model has it, a parameter one while every entry it overrides has the catalog's values) and `exact` (params are the catalog's for that set, so a step loses nothing set by hand). Rationales aren't compared. Both `None` when unavailable or without params. The page sends `{xml, params}`.
    - `diff_designs(before_xml, before_params, after_xml, after_params)` → `{added, removed, rerouted, parameters}`: nodes and flows as `{id, label}`, entry keys whose values differ. Layout moves are no change. Expected values in the tests come from `models/to_be_changelog.md`.
  - UI: `web/studio/suggestions-panel.mjs` + `.css`, in `<section id="suggestions">` under the diagram. The panel keeps no applied set of its own: it asks `suggestions` after every diagram edit, import and parameter change. So importing `to_be.bpmn` shows C1 and C2 applied, Ctrl+Z after a hand edit re-enables it. Undo = apply the current set without that change. After a step, the added, reconnected and re-parametrised elements get a green outline (`studio-changed` marker) and a one-line count. A hand-set value shows a note that a step resets it. After a hand edit of the diagram the cards are dimmed and disabled, with the reason and a "Back to the as-is model" button.
  - Shared files: `params-panel.mjs` got an `onParamsChange(params)` option (called after every update). `index.html`: CSS link, section, module wiring, `window.studio.suggestions`. Labels in `studio.en.toml` (block after the lint labels). Wheel rebuilt.
  - Browser check (headless Chrome, `studio-check-07.mjs` + `expected-07.py` in the scratchpad `pyodide-proof/`): walks all 16 combinations with one Apply or Undo click each (Gray code) and back; at every step the panel's params, nodes, flows, applied set and outlined elements equal native Python. A hand-set QC capacity drops C4 and shows the note; applying C4 resets it to 9. A drawn task disables the panel with the reason; Ctrl+Z re-enables it. Back to the as-is model gives the preset parameters. All four applied, Run gives the same replication means as native (105.0 days, 8.6 s). No horizontal scroll at 390 px, no console errors.
  - For 08: the four cards are tall (driver, effect, trade-off text), so Run sits well below the diagram at laptop width. Consider moving Run up or folding the driver and effect into `<details>`. "Back to the as-is model" can't be undone with Ctrl+Z (an import clears the command stack).
