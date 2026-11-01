# 05: Results contract and full page on fake data

**What to build:** The full JSON schema for the results file as described in the spec (`meta`, `assumptions`, `models` with lint results, `value_added`, `baseline` with the flow analysis cross-check, `ml`, `changes`, `scenarios`, `threats`). A realistic fake results file that passes the schema. The complete static page built against it, with sections in DSRM order: problem and method, as-is model and baseline, ML findings, redesign (to-be model and change catalog), evaluation (one toggle per change showing cycle time with CI, plus the ablation), assumptions and threats.

**Blocked by:** 01

**Status:** done

- [x] Schema covers every section listed in the spec
- [x] Fake results file validates against the schema in a test
- [x] Page renders both BPMN models with bpmn-js, using pinned CDN versions
- [x] Toggling any combination of changes shows that scenario's cycle time mean, median and P90 with CI
- [x] All visible text comes from the results file or the BPMN labels, so translation is a content change
- [x] Page works on GitHub Pages and on a local static server, with no backend
- [x] Page is readable at phone width

## Comments

- From review of 01: the page skeleton still has hardcoded text (title, captions, error message). Move it into the results file here. Also, `meta.schema_version` was added in 01 (not in the spec list), and `format: date-time` isn't enforced because `jsonschema.validate` runs without a format checker.
- Done. Schema v2 in `src/bpmopt/schema/results.schema.json`. Fake file `web/fixtures/fake_results.json`, with its models in `web/fixtures/models/`. Open it with `?results=fixtures/fake_results.json`. Without the parameter the page loads `results.json`.
- Required now: `meta`, `text`, `models`, `baseline` (only `cycle_time` inside it). Every other section is optional until its ticket fills it, but once present its shape is fixed. Ticket 16 should make all sections required.
- New `text` section holds every page string. Its source is `src/bpmopt/content/page.en.toml`, which `build_results` copies in. A Vietnamese page is a `page.vi.toml` plus `build_results(..., lang="vi")`. A test checks that the keys the page reads with `t("...")` are exactly the labels the schema requires, so a new label needs both.
- Only the load error when `results.json` itself fails has no wording. It shows the raw error, because there is no text to show yet. The serving hint lives in the README.
- `validate_results` now runs a format checker (`date-time` enforced, `rfc3339-validator` added as a pinned dependency) and rules a schema can't express: scenarios must be the full factorial of the change catalog, each combination exactly once, and every CI must contain its estimate.
- For tickets that fill sections: `scenarios[].saving` is the paired (common random numbers) difference in mean cycle time vs the empty scenario, with CI. The page derives the ablation from it. `baseline.rework[].rate` is the share of cases that loop back at least once. ML model ids are `reference`, `linear`, `gradient_boosting`. Lint `element_id` is null for whole-model rules. Activity and gateway names come from the BPMN, so results only carry IDs.
- `meta` gained `replications` and `warm_up` (spec list) and an optional `fake` flag that shows a notice. `warm_up` comes from the parameter file (ticket 04, after the merge). `replications` is 1 until ticket 13 writes R. `schema_version` kept and added to the spec. `baseline.cycle_time` now has median and P90 too.
- Fake as-is model is an English copy of `current_process.bpmn` with the same element IDs. The to-be model is a small placeholder until ticket 15. The fake page text is a copy of the content file; regenerate or edit it by hand if the content changes.
- Checked in headless Chrome on a local static server: both diagrams draw, value-added colors apply, toggles show the right scenario (C1+C2 gives 95.6 days, 22.8 saved), no console errors, no horizontal scroll at 390px wide, dark mode readable. Not tried on GitHub Pages itself, but every path is relative and there is no backend.
