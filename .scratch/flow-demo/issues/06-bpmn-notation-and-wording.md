# 06: BPMN notation, no duplicate badges, natural wording

**What to build:** Student feedback on 2026-11-06. (1) The demo flow must use the book's BPMN symbols and shapes (Dumas et al., 2nd ed., §3.1-3.4): thin-circle start event, thick-circle end event, rounded-rectangle activities, XOR gateways as a diamond with an X, AND gateways as a diamond with a +, solid sequence-flow arrows, a pool with one lane per department. Every decision and every loop goes through the gateways that `models/as_is.bpmn` and `models/to_be.bpmn` have, with the condition on the outgoing arcs (book p.190: a condition label, not yes/no), and the rework share added in brackets, e.g. "cần sửa (20%)". C1 is drawn as the AND-split and AND-join around the four checks, C2 as the retest task and its XOR-join, as in `to_be.bpmn`. The visual style (colors, fonts, the orange highlight) can stay. Dashed lines are not allowed for sequence flows (in BPMN they mean message flows). (2) Remove the numbered queue badges; the orange dots alone show who is waiting, wrapping onto more rows when needed. (3) Rewrite all on-screen text in natural Vietnamese and drop AI-looking symbols.

**Blocked by:** 05

**Status:** done

- [x] Every element of `as_is.bpmn` and `to_be.bpmn` that the replay visits is drawn with the book's shape, gateways included; no element is drawn that the model doesn't have, except highlight frames and the C3/C4 notes
- [x] All sequence flows are solid arrows; XOR split arcs carry condition labels with the rework share in brackets
- [x] Tokens move through gateways along the arcs the way the book describes token flow (§3.1, Fig. 3.2); the legend says each dot is a token, one project
- [x] No numbered queue badges; waiting is shown only by orange dots
- [x] No text uses →, ×, —, –, •, ·, …, emoji or ASCII stand-ins like "---"; all labels read as natural Vietnamese; speed shows as e.g. "Tốc độ x2" or plain words
- [x] The layout probe still reports no overlaps or clipping at 1366, 1920 and 390, smallest flow text at least 12 px at 1366 in compare mode
- [x] A test checks the drawn elements against the BPMN files, so the demo can't drift from the model
- [x] Full test suite passes

## Comments

- 2026-11-06: claimed. Implementer started.
- 2026-11-06: done. The flow is now drawn in the book's notation from the BPMN IDs; replay data, colours and fonts unchanged.
  - `web/demo/layout.js` lists every node of both models (type and lane) and every sequence flow by its BPMN ID, with orthogonal waypoints. `route()` gives the path a token takes from one task to the next through gateways only (and on to an end event). The page draws thin and thick event circles, rounded tasks, XOR (X) and AND (+) diamonds, solid arrows, and a pool ("Ngân hàng") with one lane per department.
  - Condition labels sit beside the arcs of every XOR split, the loops with the rework share in brackets ("cần sửa (20%)", "có lỗi (37%)"). C1 is the AND-split and AND-join around the four checks; C2 is the retest task and its XOR-join, as in `to_be.bpmn`. Checks that finish first wait as hollow tokens on their arc just before the AND-join and merge into it.
  - Tokens are created at the start event, move along the arcs (around the outside of a box, never over its label) and end at an end event. Queue badges are gone; orange dots wrap onto a second (compact) or third (normal) row.
  - Wording: conditions, legend and controls rewritten; speed buttons read "x0,5" to "x4", the clock "Tháng 10 trên 18", the C4 lane "9 người" with "C4 thêm 1". The legend draws each symbol as a small SVG and says each dot is a token, one project.
  - Tests: `tests/test_demo.py` compares the drawn nodes and flows with both BPMN files (both sizes), checks that every XOR-split arc has a condition and that only loops carry `{rate}`, and scans the content and page code for stand-in symbols. `tests/demo_state.test.mjs` checks the token routes (also for every step in the real replay), that arcs run from edge to edge without crossing an element, element placement, dots in the strip and clear of chips, the park spots, and the width budget for 12 px text. Full suite: 281 passed.
  - Probe (ticket 05's `probe.js` plus a second probe for text on shapes or lines and dots on text, screenshots in scratchpad `ui-audit/after-06/`): no clipping, no text overlaps, nothing on shapes or lines at 1366, 1920 and 390, during play too. Smallest flow text 12.0 px at 1366 (all views; the side gutter is 2 px up to 1500 px wide), 16.7 at 1920, 12.0 at 390 (sideways scroll). Compare at 1366x768 still shows both flows above the bar.
  - Not like the book, on purpose: lane names are horizontal (vertical names don't fit a 67-unit compact lane); events have their names as tooltips only, since there is no room for visible labels at 12 px. The result view's charts at 390 px are still small (unchanged, as in ticket 05).
