# 05: Live lint panel

**What to build:** The linter runs on the current diagram after each edit (debounced) and lists violations with rule, severity and message. Clicking a violation selects its element. Errors disable Run and say why; warnings don't.

**Blocked by:** 03

**Status:** claimed

- [ ] The as-is preset shows no violations; the full to-be shows only the G7 warning
- [ ] Drawing an unconnected task shows the reachability error and disables Run
- [ ] Clicking a violation selects the element in the diagram
- [ ] Checked in headless Chrome, no console errors

## Comments
- 2026-11-05: claimed. Implementer started.
