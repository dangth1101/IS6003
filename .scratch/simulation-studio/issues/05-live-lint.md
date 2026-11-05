# 05: Live lint panel

**What to build:** The linter runs on the current diagram after each edit (debounced) and lists violations with rule, severity and message. Clicking a violation selects its element. Errors disable Run and say why; warnings don't.

**Blocked by:** 03

**Status:** done

- [x] The as-is preset shows no violations; the full to-be shows only the G7 warning
- [x] Drawing an unconnected task shows the reachability error and disables Run
- [x] Clicking a violation selects the element in the diagram
- [x] Checked in headless Chrome, no console errors

## Comments
- 2026-11-05: claimed. Implementer started.
- 2026-11-05: done.
  - UI in its own module: `web/studio/lint-panel.mjs` + `lint-panel.css`. `createLintPanel({container, modeler, lint, t, onChange})` lints 300 ms after each `commandStack.changed` and on `import.done`, drops stale answers, and reports `{status: "checking" | "checked" | "unreadable", ...}`. `blocksRun(state)` and `runBlockedReason(state, t)` gate Run: anything but a checked model without errors blocks, "checking" included, so a click right after an edit can't run an unchecked model.
  - `index.html`: Run is gated by one `updateRun()` over `runGate = {ready, running, lint}`. The modeler is on `window.studio.modeler` for headless checks.
  - Python: `lint_xml` now raises one `ValueError` starting "Not a readable BPMN document: ..." for bad XML, a flow without ends, or not exactly one process. The panel shows it and Run says why it's blocked. Test in `tests/test_studio.py`; wheel rebuilt.
  - A process-level violation (G7, POOL) names the process; clicking it selects the pool.
  - The label test now scans `index.html` and every `*.mjs` in `web/studio/` for `t("...")`.
  - Browser check (headless Chrome, `studio-check-05.mjs` in the session scratchpad's `pyodide-proof/`): as-is shows no violations, Run on. Imported full to-be shows only G7 (warning), Run on, click selects `Participant_Bank`. A task drawn from the palette gives two REACH errors (plus G6 and G7 warnings), Run off with "Fix the model errors below to run.", click selects the task. Undo clears it. No horizontal scroll at 390 px, no console errors.
  - For 06-08: change Run's enabled state only through `runGate` + `updateRun()`, not `$("run").disabled`. Any new UI module's `t("key")` labels are checked against the content file.
