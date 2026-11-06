# 06: BPMN notation, no duplicate badges, natural wording

**What to build:** Student feedback on 2026-11-06. (1) The demo flow must use the book's BPMN symbols and shapes (Dumas et al., 2nd ed., §3.1-3.4): thin-circle start event, thick-circle end event, rounded-rectangle activities, XOR gateways as a diamond with an X, AND gateways as a diamond with a +, solid sequence-flow arrows, a pool with one lane per department. Every decision and every loop goes through the gateways that `models/as_is.bpmn` and `models/to_be.bpmn` have, with the condition on the outgoing arcs (book p.190: a condition label, not yes/no), and the rework share added in brackets, e.g. "cần sửa (20%)". C1 is drawn as the AND-split and AND-join around the four checks, C2 as the retest task and its XOR-join, as in `to_be.bpmn`. The visual style (colors, fonts, the orange highlight) can stay. Dashed lines are not allowed for sequence flows (in BPMN they mean message flows). (2) Remove the numbered queue badges; the orange dots alone show who is waiting, wrapping onto more rows when needed. (3) Rewrite all on-screen text in natural Vietnamese and drop AI-looking symbols.

**Blocked by:** 05

**Status:** claimed

- [ ] Every element of `as_is.bpmn` and `to_be.bpmn` that the replay visits is drawn with the book's shape, gateways included; no element is drawn that the model doesn't have, except highlight frames and the C3/C4 notes
- [ ] All sequence flows are solid arrows; XOR split arcs carry condition labels with the rework share in brackets
- [ ] Tokens move through gateways along the arcs the way the book describes token flow (§3.1, Fig. 3.2); the legend says each dot is a token, one project
- [ ] No numbered queue badges; waiting is shown only by orange dots
- [ ] No text uses →, ×, —, –, •, ·, …, emoji or ASCII stand-ins like "---"; all labels read as natural Vietnamese; speed shows as e.g. "Tốc độ x2" or plain words
- [ ] The layout probe still reports no overlaps or clipping at 1366, 1920 and 390, smallest flow text at least 12 px at 1366 in compare mode
- [ ] A test checks the drawn elements against the BPMN files, so the demo can't drift from the model
- [ ] Full test suite passes

## Comments

- 2026-11-06: claimed. Implementer started.
