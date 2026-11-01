# 05: Results contract and full page on fake data

**What to build:** The full JSON schema for the results file as described in the spec (`meta`, `assumptions`, `models` with lint results, `value_added`, `baseline` with the flow analysis cross-check, `ml`, `changes`, `scenarios`, `threats`). A realistic fake results file that passes the schema. The complete static page built against it, with sections in DSRM order: problem and method, as-is model and baseline, ML findings, redesign (to-be model and change catalog), evaluation (one toggle per change showing cycle time with CI, plus the ablation), assumptions and threats.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Schema covers every section listed in the spec
- [ ] Fake results file validates against the schema in a test
- [ ] Page renders both BPMN models with bpmn-js, using pinned CDN versions
- [ ] Toggling any combination of changes shows that scenario's cycle time mean, median and P90 with CI
- [ ] All visible text comes from the results file or the BPMN labels, so translation is a content change
- [ ] Page works on GitHub Pages and on a local static server, with no backend
- [ ] Page is readable at phone width
