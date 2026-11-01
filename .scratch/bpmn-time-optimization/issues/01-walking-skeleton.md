# 01: Walking skeleton

**What to build:** A thin end-to-end path. A pure-sequence BPMN file (pool, one lane, start event, three tasks, end event) is read, simulated with fixed task durations from a parameter file, and turned into an event log. Mean cycle time is computed from the log and written to a results file. A static page loads the results file and the BPMN file, renders the model with bpmn-js and shows the number. A notebook stub runs the whole path. This sets up the Python package, the test runner and the folder layout every later ticket builds on.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Python package with a test runner, installable in a fresh virtual environment, with dependencies pinned
- [x] Simulating the same model with the same seed gives an identical event log
- [x] Every simulated case has one start and reaches the end event
- [x] Event log has case ID, activity ID, activity label, lane, ready time, start time, end time
- [x] Mean simulated cycle time equals the book's sequence formula (§7.1.1) within tolerance
- [x] Results file has a `meta` section and a `baseline` section with mean cycle time, and validates against a first version of the JSON schema
- [x] Page served from a local static server renders the BPMN diagram and the mean cycle time
- [x] Notebook runs top to bottom and produces the results file

## Comments

- Done. Package `bpmopt` in `src/`, tests in `tests/`, notebook in `notebooks/`, page in `web/`.
- Log columns: case_id, activity_id, activity_label, element_type, lane_id, lane_label, ready_time, start_time, end_time. Start and end events are zero-duration rows, so each trace shows where it began and which end event it reached. Filter on `element_type == "task"` for activity-level measures.
- Parameter file is TOML. Durations are `{ fixed = x }` only for now.
- Python 3.12+, not 3.11+: the pinned NumPy 2.5.4 needs it. Spec updated.
- The same-seed test can't fail yet, because fixed durations draw no random numbers. It starts to matter with ticket 07.
