# 04: Resources, arrivals and waiting time

**What to build:** Lanes act as resource pools with a capacity from the parameter file. New cases arrive at a configured rate, so cases overlap and queue. The log records when each activity became ready as well as when it started and ended, so waiting time and processing time can be told apart. A warm-up period is configurable and those cases are dropped from the log.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] With unlimited capacity, waiting time is zero for every activity
- [ ] With capacity 1 and an arrival rate close to the service rate, waiting time grows, in line with the book's queueing intuition (§7.2)
- [ ] Ready time ≤ start time ≤ end time for every log row
- [ ] Cases that start during the warm-up are excluded from the log
- [ ] Same seed still gives an identical log
- [ ] Note: this ticket touches the same simulator core as ticket 03. Expect to merge with it.

## Comments

- From review of 01: the simulator draws from one shared RNG in event order. Once arrivals and gateways exist, give each case (or each stream: arrivals, durations, branches) its own generator, e.g. `default_rng([seed, case_id])`. Otherwise a design change shifts every later draw and weakens common random numbers (ticket 13).
