# 01: Remove the simulation studio

**What to build:** Delete the studio and everything only it uses: `web/studio/`, `src/bpmopt/studio/`, `scripts/build_studio.py`, `tests/test_studio*.py` and studio-only fixtures, the studio sections of `README.md`, and the studio link and labels on the report page (`web/index.html`, `src/bpmopt/content/page.en.toml`, and the regenerated `web/results.json` text). Keep shared code the notebook or other tests still use. Add a note to `.scratch/simulation-studio/spec.md` that the student replaced it with the flow demo on 2026-11-06.

**Blocked by:** None (can start immediately)

**Status:** claimed

- [ ] No file or text references the studio, except the history note in `.scratch/simulation-studio/`
- [ ] Code that nothing uses any more is removed; code the notebook still uses stays
- [ ] Full test suite passes
- [ ] Report page loads with no console errors

## Comments
- 2026-11-06: claimed. Implementer started.
