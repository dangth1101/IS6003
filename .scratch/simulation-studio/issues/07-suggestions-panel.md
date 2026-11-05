# 07: Suggestions panel

**What to build:** A panel listing C1-C4 from the change catalog with title, driver, Appendix A heuristic, expected effect and Devil's Quadrangle trade-off. Each has apply / undo. Applying changes the diagram (structural changes load the matching catalog model) and the parameters (overrides), and highlights what changed. Available only while the model is the as-is preset with suggestions applied; after a hand edit the panel is disabled and says why, with a "back to preset" option.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] Applying any combination of C1-C4 gives the same model and parameters as `catalog.resolve`
- [ ] Undo returns to the previous combination exactly
- [ ] After a hand edit the panel is disabled with the reason shown
- [ ] Checked in headless Chrome, no console errors

## Comments
