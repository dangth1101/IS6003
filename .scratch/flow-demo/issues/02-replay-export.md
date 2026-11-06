# 02: Replay data export

**What to build:** A public package function that simulates the as-is model and the full to-be (C1-C4 via the catalog) with the same parameters and seed, keeps one time window after warm-up, and writes `web/demo/replay.json`: per scenario the task rows (case ID, activity ID, lane, ready, start, end), each case's arrival and (if finished) cycle time, plus the window bounds and seed. Wire it into the notebook (or a script the README names) so it is regenerated with the results.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Rows match `simulate` for that seed
- [x] Both scenarios have the same case arrivals
- [x] Only rows that overlap the window are kept, and the window is long enough to show the QC queue building (about one to one and a half simulated years)
- [x] File size stays small enough to load instantly (well under 2 MB)
- [x] Tested through the public function

## Comments
- 2026-11-06: claimed. Implementer started.
- 2026-11-06: done. `bpmopt.replay.build_replay` / `write_replay`, tests in `tests/test_replay.py`, regenerate with `uv run python scripts/build_demo_data.py`. File is 426 KB.
  - Window: working days 250 to 625 (1.5 years right after the warm-up), seed 42. The as-is QC queue starts empty and averages 8.0 waiting QC tasks over the window, peak 15; the to-be averages 0.6. 128 / 126 cases on screen, 91 / 98 finish in the window.
  - Cases that arrived during the warm-up are kept (unlike `simulate`'s log), since they are still in flight and hold testers when the window opens.
  - Format for ticket 03. Top level: `seed`, `time_unit` ("working days"), `warm_up`, `cycle_time_ends_at` ("Task_StartOperation"), `window` {`start`, `end`}, `scenarios` [as_is, to_be].
  - Per scenario: `id` ("as_is" / "to_be"), `name`, `changes` ([] / ["C1".."C4"]), `lanes` (lane IDs), `tasks` (task IDs of that model), `cases`, `rows`.
  - `cases`: {`id`, `arrival`, `cycle_time`}. Cases in the system at some point in the window. `cycle_time` is set if the case went live (or ended, if rejected) before the window closes, else null. Finish time is `arrival + cycle_time`; it can fall before `window.start` for a case only seen in its after-go-live tasks (monitoring, evaluation), so count "finished" only when it falls inside the window.
  - `rows`: {`case`, `activity`, `lane`, `ready`, `start`, `end`}, task rows only, any row with `ready < window.end` and `end > window.start`. Waiting from `ready` to `start` (queue badge), working from `start` to `end` (dot on the task). Times may run past the window; clamp them on the page. Times are rounded to 2 decimals.
