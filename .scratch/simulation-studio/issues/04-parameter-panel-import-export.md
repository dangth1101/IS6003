# 04: Parameter panel, import and export

**What to build:** Selecting a task, XOR split or lane opens a side panel to edit its parameters (triangular duration; fixed branch probabilities; capacity). Attribute scaling and logistic branches from an imported file are shown read-only, with "reset to fixed" for logistic branches. A settings panel holds arrival rate, warm-up, cases, replications and seed. Import a `.bpmn` and, optionally, a `.params.toml`; missing entries are filled by `default_parameters` and shown as defaults. A newly drawn task gets a default duration. Export the current BPMN and parameter file.

**Blocked by:** 02, 03

**Status:** ready-for-agent

- [ ] Editing a duration, probability or capacity changes the next run's result in the expected direction
- [ ] Importing a model without a parameter file runs at once, with every default visible
- [ ] Exported BPMN + parameters re-import to the same result under the same seed
- [ ] Exported parameters load in the notebook's `load_parameters`
- [ ] Checked in headless Chrome, no console errors

## Comments
