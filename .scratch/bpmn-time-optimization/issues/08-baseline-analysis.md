# 08: Baseline analysis (Phase 3)

**What to build:** Event log → baseline metrics: cycle time, processing time and waiting time (mean, median, P90), cycle time efficiency (§7.1.2), rework rate per XOR gateway, and mean waiting time per activity. Also the cross-check between the simulated mean and the flow analysis value. All of it goes into the `baseline` section of the results.

**Blocked by:** 03, 04

**Status:** ready-for-agent

- [ ] Tested on simulator logs with known parameters: configured rework rates and durations are recovered within tolerance
- [ ] Cycle time efficiency is 1.0 with unlimited capacity and no rework, and drops when waiting appears
- [ ] Per-activity waiting time is highest at the lane with the tightest capacity in a fixture
- [ ] Output validates against the `baseline` part of the schema
