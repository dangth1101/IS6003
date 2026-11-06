# 01: Remove the simulation studio

**What to build:** Delete the studio and everything only it uses: `web/studio/`, `src/bpmopt/studio/`, `scripts/build_studio.py`, `tests/test_studio*.py` and studio-only fixtures, the studio sections of `README.md`, and the studio link and labels on the report page (`web/index.html`, `src/bpmopt/content/page.en.toml`, and the regenerated `web/results.json` text). Keep shared code the notebook or other tests still use. Add a note to `.scratch/simulation-studio/spec.md` that the student replaced it with the flow demo on 2026-11-06.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] No file or text references the studio, except the history note in `.scratch/simulation-studio/`
- [x] Code that nothing uses any more is removed; code the notebook still uses stays
- [x] Full test suite passes
- [x] Report page loads with no console errors

## Comments
- 2026-11-06: claimed. Implementer started.
- 2026-11-06: done. Removed `web/studio/`, `src/bpmopt/studio/`, `src/bpmopt/content/studio.en.toml`, `scripts/build_studio.py`, the four `tests/test_studio*.py`, `tests/fixtures/studio_parity.json`, `docs/research/studio-browser-runtime.md`, the studio parts of `README.md`, and the studio link, labels and schema keys on the report page (`web/index.html`, `page.en.toml`, `results.schema.json`). The `text` section of `web/results.json` and `web/fixtures/fake_results.json` was resynced from `load_page_text()` with a small script, no notebook rerun.
- Shared code: everything the studio added to `analysis.py` (`utilisation`, `work_per_case`), `bpmn.py` (`parse_bpmn`), `lint.py` (`lint_model`), `parameters.py` (`parse_parameters`, `ParameterError`, `entry_key`, `element_ids`, `restrict`, ...) and `scenarios.py` (`parse_catalog`, `scenario_tables`, public `estimate`, ...) was only used by the studio, so those five files are back to their pre-studio version (fea642a). That's the code that produced the committed results, and the notebook and other tests never used the new names. Kept the `<link rel="icon" href="data:,">` on the report page, since it avoids a favicon 404 in the console.
- Checks: 248 tests pass; report page in headless Chrome at 1366 px has no console errors or failed requests, and no studio link or text.
