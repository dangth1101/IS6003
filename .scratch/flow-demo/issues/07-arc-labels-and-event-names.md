# 07: Arc labels next to their gateway, visible event names

**What to build:** Two gaps left after ticket 06. (1) Some condition labels sit far from the arc they belong to ("được duyệt" next to "Đăng ký yêu cầu", "cần sửa (19%)" and "bị từ chối (8%)" at the top), so they are hard to match. Place every XOR-split condition label on its own arc, right next to the gateway it leaves, as in the book's figures. (2) Start and end events show their names only as tooltips. The book's labeling rule (§5.4.3, our linter's event-label check) needs a visible label on every event. Show short natural Vietnamese names under each event, taken from the BPMN names, e.g. "Có yêu cầu mới", "Đề xuất bị từ chối", "Dự án kết thúc".

**Blocked by:** 06

**Status:** claimed

- [ ] Every condition label touches or sits within a few pixels of its own arc, next to the gateway it leaves; a test checks label-to-arc distance
- [ ] Every start and end event has a visible label in natural Vietnamese
- [ ] The layout probe still reports no overlaps or clipping at 1366, 1920 and 390, smallest flow text at least 12 px at 1366 in compare mode
- [ ] Full test suite passes

## Comments

- 2026-11-07: claimed. Implementer started.
