# 03: Demo page: swimlane flow, switch, animated replay, result

**What to build:** `web/demo/index.html` as in the spec: Vietnamese swimlane flow in SVG for As-is and To-be with the changes highlighted, the switch, "Chạy mô phỏng" animated replay from `replay.json` (dots on tasks, queue badges, loops, clock, play/pause/speed, live counters), compare mode with both in sync, and the result panel from `web/results.json`. Text in a content file. Report page links to the demo.

**Blocked by:** 01, 02

**Status:** claimed

- [ ] Flow is readable on a projector: Vietnamese labels, five lanes, loops with rework rates
- [ ] Switch shows As-is and To-be; C1 and C2 are highlighted in the flow, C3 and C4 shown as badges
- [ ] Replay plays, pauses, changes speed and finishes; the QC queue visibly builds in As-is and stays shorter in To-be
- [ ] Compare mode replays both with the same arrivals
- [ ] Result panel numbers equal `web/results.json`; replay counters are labelled as one sample run
- [ ] Headless Chrome: no console errors, works at 1366 px and 390 px with no horizontal scroll

## Comments
- 2026-11-06: claimed. Implementer started.
