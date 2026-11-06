# 03: Demo page: swimlane flow, switch, animated replay, result

**What to build:** `web/demo/index.html` as in the spec: Vietnamese swimlane flow in SVG for As-is and To-be with the changes highlighted, the switch, "Chạy mô phỏng" animated replay from `replay.json` (dots on tasks, queue badges, loops, clock, play/pause/speed, live counters), compare mode with both in sync, and the result panel from `web/results.json`. Text in a content file. Report page links to the demo.

**Blocked by:** 01, 02

**Status:** done

- [x] Flow is readable on a projector: Vietnamese labels, five lanes, loops with rework rates
- [x] Switch shows As-is and To-be; C1 and C2 are highlighted in the flow, C3 and C4 shown as badges
- [x] Replay plays, pauses, changes speed and finishes; the QC queue visibly builds in As-is and stays shorter in To-be
- [x] Compare mode replays both with the same arrivals
- [x] Result panel numbers equal `web/results.json`; replay counters are labelled as one sample run
- [x] Headless Chrome: no console errors, works at 1366 px and 390 px with no horizontal scroll

## Comments
- 2026-11-06: claimed. Implementer started.
- 2026-11-06: done. `web/demo/index.html` with `app.js` (drawing, animation), `layout.js` (fixed positions by BPMN element ID, normal and compact), `state.js` (per-time state from the rows, no DOM), `figures.js` (result numbers from `results.json`) and the text in `demo.vi.json`. Plain JS and SVG, one Google Font (Be Vietnam Pro), no build step. The report's evaluation section links to `demo/` (new label `demo_link`, `text` resynced in `web/results.json` and the fake results).
  - Views: As-is, To-be, So sánh (both flows stacked, one clock), Kết quả. Keys 1 to 4 switch views, Space plays or pauses. `?view=compare&at=0.6` opens a view at a point in the run.
  - Replay at 1x: 6.25 working days a second, so the 18 months take 60 s (a month in about 3.3 s); 0.5x to 4x. Dots: teal while worked on, orange in the queue tray above a task with a count badge, hollow on the join line while the other parallel checks finish, light teal after go-live.
  - `replay.json` now also carries each scenario's lane capacities (for the C4 badge, 8 → 9) and its rework rates, measured like the baseline (2,000 cases, seed 42). The as-is ones equal `baseline.rework` (a test checks it); the to-be test loop is 30% instead of 37% because of C3. Rows are unchanged.
  - Tests: `tests/test_demo.py` (content covers every task, lane, loop and change of both models; no numbers typed into the content; layout lanes match the BPMN; result numbers equal `results.json`, run through `figures.js` in Node) and `tests/demo_state.test.mjs` (Node, run by pytest).
  - Headless Chrome (1366x768, 1440x810 at scale 2, 390x844): no console errors or failed requests, no horizontal scroll, play, pause, 4x (measured 4.0x) and finish ("Chạy lại", Tháng 18 / 18), compare fits above the transport bar at 1366x768. Mean QC queue over the run: as-is 8.0, to-be 0.6; same arrivals in both. About 60 fps while playing.
  - At 1366 px the task labels render at about 12 px, since 20 tasks sit side by side. Fine on a 1080p projector; on a 1366 one, present full screen (F11).
