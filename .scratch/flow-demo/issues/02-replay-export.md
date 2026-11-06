# 02: Replay data export

**What to build:** A public package function that simulates the as-is model and the full to-be (C1-C4 via the catalog) with the same parameters and seed, keeps one time window after warm-up, and writes `web/demo/replay.json`: per scenario the task rows (case ID, activity ID, lane, ready, start, end), each case's arrival and (if finished) cycle time, plus the window bounds and seed. Wire it into the notebook (or a script the README names) so it is regenerated with the results.

**Blocked by:** None (can start immediately)

**Status:** claimed

- [ ] Rows match `simulate` for that seed
- [ ] Both scenarios have the same case arrivals
- [ ] Only rows that overlap the window are kept, and the window is long enough to show the QC queue building (about one to one and a half simulated years)
- [ ] File size stays small enough to load instantly (well under 2 MB)
- [ ] Tested through the public function

## Comments
- 2026-11-06: claimed. Implementer started.
