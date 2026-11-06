# 05: Layout polish from the visual audit

**What to build:** Fix the layout problems found by the jev-browser audit on 2026-11-06 (screenshots and the probe script in the scratchpad `ui-audit/`). The page must read cleanly on a projector at 1366×768 and 1920×1080, and stay usable at 390 px.

**Blocked by:** 03

**Status:** claimed

- [ ] Dots for projects in progress never cover a task label (own row inside a taller box, or below the box)
- [ ] Loop-rate pills and queue badges never overlap a task box, another label or the orange frame
- [ ] Lane labels and their "N người" line fit inside their lane; two-line labels have normal line spacing
- [ ] Smallest text on the flow is at least 12 px at 1366×768 in compare mode (e.g. drop or shrink the greyed post-go-live tasks, narrow the lane label column, use the height better)
- [ ] The control bar never covers the legend, the note or the flows in any view
- [ ] At 390 px: no content hidden under the control bar; the flow can be scrolled sideways with a visible cue, or is laid out to fit
- [ ] The probe reports no SVG text overlaps and no clipping at all three sizes, in As-is, To-be, compare mid-replay and Kết quả
- [ ] Full test suite passes

## Comments

- 2026-11-06: claimed. Implementer started.
