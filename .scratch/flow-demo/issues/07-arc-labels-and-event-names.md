# 07: Arc labels next to their gateway, visible event names

**What to build:** Two gaps left after ticket 06. (1) Some condition labels sit far from the arc they belong to ("được duyệt" next to "Đăng ký yêu cầu", "cần sửa (19%)" and "bị từ chối (8%)" at the top), so they are hard to match. Place every XOR-split condition label on its own arc, right next to the gateway it leaves, as in the book's figures. (2) Start and end events show their names only as tooltips. The book's labeling rule (§5.4.3, our linter's event-label check) needs a visible label on every event. Show short natural Vietnamese names under each event, taken from the BPMN names, e.g. "Có yêu cầu mới", "Đề xuất bị từ chối", "Dự án kết thúc".

**Blocked by:** 06

**Status:** done

- [x] Every condition label touches or sits within a few pixels of its own arc, next to the gateway it leaves; a test checks label-to-arc distance
- [x] Every start and end event has a visible label in natural Vietnamese
- [x] The layout probe still reports no overlaps or clipping at 1366, 1920 and 390, smallest flow text at least 12 px at 1366 in compare mode
- [x] Full test suite passes

## Comments

- 2026-11-07: claimed. Implementer started.
- 2026-11-07: done. Every condition now sits beside the first stretch of its own arc, at the gateway; the three events show their names.
  - `web/demo/layout.js`: a leg up has its label up and right of it, a leg down down and right, an arc to the right has it underneath. Each flow label and event label carries its width and line count, so the tests can check them. Width and height are both at the limit for 12 px text, so routing moved instead of text shrinking: the build and deploy boxes sit further left under their gateways, the loop back from "Sửa đề xuất" enters the join's left corner, the to-be test split sits at box height right of the retest box, and "có lỗi (30%)" takes two lines there. Flow width 1752 units (12.03 px at 1366).
  - Two labels sit across a lane line, since the boxes fill those lanes: the proposal's "cần sửa (20%)" is just inside the development lane, beside its leg down; "Dự án kết thúc" sits above its event in the QC lane.
  - Event names in `demo.vi.json`: "Đã nhận / yêu cầu" (request received, object plus past participle as in §5.4.3; "Có yêu cầu mới" did not fit left of the request box), "Đề xuất / bị từ chối", "Dự án kết thúc".
  - Tests (`tests/demo_state.test.mjs`): each condition is at most 6 units from the first segment of its own arc, every other arc at least 4 units further, and within 40 units of its gateway; each event has its name within 18 units; no label touches an element (diamond and circle shapes, not boxes), another label, an arc, or the pool edge. Full suite: 281 passed.
  - Probe (ticket 06's audit, screenshots in scratchpad `ui-audit/after-07/`, the 1920 shots at device scale 2): no clipping, no text overlaps, no text on shapes or lines, no token on text at 1366, 1920 and 390, during play too. Smallest flow text 12.03 px at 1366 (all views), 16.8 at 1920. Compare at 1366x768 still shows both flows above the bar.
