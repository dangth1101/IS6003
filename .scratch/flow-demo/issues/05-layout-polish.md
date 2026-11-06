# 05: Layout polish from the visual audit

**What to build:** Fix the layout problems found by the jev-browser audit on 2026-11-06 (screenshots and the probe script in the scratchpad `ui-audit/`). The page must read cleanly on a projector at 1366×768 and 1920×1080, and stay usable at 390 px.

**Blocked by:** 03

**Status:** done

- [x] Dots for projects in progress never cover a task label (own row inside a taller box, or below the box)
- [x] Loop-rate pills and queue badges never overlap a task box, another label or the orange frame
- [x] Lane labels and their "N người" line fit inside their lane; two-line labels have normal line spacing
- [x] Smallest text on the flow is at least 12 px at 1366×768 in compare mode (e.g. drop or shrink the greyed post-go-live tasks, narrow the lane label column, use the height better)
- [x] The control bar never covers the legend, the note or the flows in any view
- [x] At 390 px: no content hidden under the control bar; the flow can be scrolled sideways with a visible cue, or is laid out to fit
- [x] The probe reports no SVG text overlaps and no clipping at all three sizes, in As-is, To-be, compare mid-replay and Kết quả
- [x] Full test suite passes

## Comments

- 2026-11-06: claimed. Implementer started.
- 2026-11-06: done. Layout fix only: palette, wording, data and animation logic unchanged (one new string, `scroll_hint`).
  - `web/demo/layout.js` now derives every size from one type scale (`TYPE`: 15 / 15.5 / 17 units) and one spacing scale (`SPACE`). Box widths fit each label at 15.5; x positions are computed left to right from rules (arrow gap, corner clearance, room for a loop rate), so the flow is 1653 units wide instead of 1790 and draws at about 0.81 px per unit at 1366.
  - Each task box has a status strip under its label: queue count and waiting dots on the left, worked-on dots to the right (normal mode: in the row above the queue). Nothing sits above a box any more, so no dot covers a label and no badge touches a box edge or the orange frame.
  - Loop rates: on a long arrow when there is one; for the two short stacked loops (plan, release) the arrow now leaves the upper box's bottom-left corner and the rate sits just left of the box. Change chips sit beside their box, not on its corner.
  - Lane names wrap greedily in a 108-unit column, line height 1.2, and the lane is checked to hold two lines plus the head count.
  - Page is a three-row grid (header, stage that scrolls, bar). The bar is no longer fixed over the page. Compare at 1366x768 shows both flows whole above the bar; the legend is one scroll below. Queue chart ticks moved to HTML so they keep 12 px.
  - 390 px: the flow keeps 1240 px and scrolls sideways, with a fade on the side that has more and a "Vuốt ngang..." hint under it.
  - Probe (original `audit.jb`, URL changed; screenshots in scratchpad `ui-audit/after/`): no clipping, no SVG text overlaps at 1366, 1920 and 390 in all views. Smallest SVG text 12.2 px at 1366 (all views), 17.2 at 1920, 11.3 at 390 (sideways scroll). A second probe found no tag on a box, label or frame edge and no dot on a label.
  - New Node tests in `tests/demo_state.test.mjs`: boxes in a lane keep an arrow gap and stay in their lane, dots and the count stay in the strip below the label (up to 16 worked on, 12 waiting), worked-on dots never sit on the queue, lanes fit their labels. Full suite: 276 passed.
  - Left as is: the result view's charts at 390 px still draw their labels at about 6 px (not in this ticket's list).
