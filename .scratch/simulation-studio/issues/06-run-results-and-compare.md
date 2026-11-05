# 06: Run results and baseline comparison

**What to build:** The results view for a run (cycle time mean / median / P90 with CI, processing vs waiting, cycle time efficiency, utilisation per lane, rework per gateway, waiting per activity), with progress per replication and a rough time estimate while it runs. "Pin as baseline" keeps a run; later runs show the saving with its paired CI and before/after per lane and per activity. A run with different seed or replications than the baseline is not compared, and the page says why.

**Blocked by:** 03, 04

**Status:** done

- [x] Progress updates during a run and the page stays responsive
- [x] The comparison numbers match `compare` for the same two runs
- [x] Changing the seed after pinning shows the "not comparable" message instead of a saving
- [x] Checked in headless Chrome, no console errors

## Comments
- 2026-11-05: claimed. Implementer started.
- 2026-11-05: done.
  - UI in its own module: `web/studio/results-panel.mjs` + `results-panel.css`. `createResultsPanel({container, t, lang, compare})`; the page calls `startRun(run)` (returns a timer whose `status(done, total)` gives the progress text with time left), `show(summary, seconds)` after a run, and `runChanged(run)` from the params panel's `onRunChange`. No Python change; the wheel only changed because the content file is package data.
  - Shows six tiles (mean, median, P90, processing, waiting, CTE, each with its CI), utilisation per lane (bars), rework per XOR split (table), waiting per activity (bars). Each chart has a "Show as a table" view. Bars and CI plot follow the report page (no chart library there either, CSS bars). This run is the accent, the baseline grey.
  - Pin keeps the shown run. A later run is sent with the baseline to `compare`: saving and share tiles with CI, a CI plot of both means, a cycle time table, and before/after bars per lane and per activity (rework gets a baseline column too). When `compare` refuses, its message is shown as the reason. Changing seed, runs or cases after pinning shows a note before the run.
  - Time estimate: after the first replication, that run's own speed; before it, the last run's speed, or 8.6 s per 10,000 case-runs on the first run.
  - Unlabelled elements (the as-is XOR splits have no name) show their ID.
  - Browser check (headless Chrome, `studio-check-06.mjs` in the session scratchpad's `pyodide-proof/`): preset run still equals the parity fixture; 10 progress updates with time left; longest frame gap during a run 34 ms; page `compare` JSON equals native `studio.compare` on the same two summaries bit for bit (QC capacity 8 to 10: saving 21.3 days, 95% CI 5.7 to 36.9); seed 43 shows the note before and "differ in seed 42 vs 43" after, no saving; replications change shows the note; no horizontal scroll at 390 px; light and dark checked by eye; no console errors.
  - For 07: after `apply_suggestion` + `panel.load`, a run compares with a pinned baseline like any other run, so no extra wiring.
  - For 08: `#results` keeps `data-summary`, and adds `data-compare` (absent when not compared). IDs for checks: `#pin-baseline`, `#baseline-box`, `#baseline-mismatch`, `#comparison`, `#compare-saving`, `#not-comparable`, `#compare-lanes`, `#compare-activities`.
