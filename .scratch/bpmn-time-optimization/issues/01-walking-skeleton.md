# 01: Walking skeleton

**What to build:** A thin end-to-end path. A pure-sequence BPMN file (pool, one lane, start event, three tasks, end event) is read, simulated with fixed task durations from a parameter file, and turned into an event log. Mean cycle time is computed from the log and written to a results file. A static page loads the results file and the BPMN file, renders the model with bpmn-js and shows the number. A notebook stub runs the whole path. This sets up the Python package, the test runner and the folder layout every later ticket builds on.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Python package with a test runner, installable in a fresh virtual environment, with dependencies pinned
- [ ] Simulating the same model with the same seed gives an identical event log
- [ ] Every simulated case has one start and reaches the end event
- [ ] Event log has case ID, activity ID, activity label, lane, ready time, start time, end time
- [ ] Mean simulated cycle time equals the book's sequence formula (§7.1.1) within tolerance
- [ ] Results file has a `meta` section and a `baseline` section with mean cycle time, and validates against a first version of the JSON schema
- [ ] Page served from a local static server renders the BPMN diagram and the mean cycle time
- [ ] Notebook runs top to bottom and produces the results file
