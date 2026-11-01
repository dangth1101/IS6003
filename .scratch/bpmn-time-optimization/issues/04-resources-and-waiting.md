# 04: Resources, arrivals and waiting time

**What to build:** Lanes act as resource pools with a capacity from the parameter file. New cases arrive at a configured rate, so cases overlap and queue. The log records when each activity became ready as well as when it started and ended, so waiting time and processing time can be told apart. A warm-up period is configurable and those cases are dropped from the log.

**Blocked by:** 01

**Status:** done

- [x] With unlimited capacity, waiting time is zero for every activity
- [x] With capacity 1 and an arrival rate close to the service rate, waiting time grows, in line with the book's queueing intuition (§7.2)
- [x] Ready time ≤ start time ≤ end time for every log row
- [x] Cases that start during the warm-up are excluded from the log
- [x] Same seed still gives an identical log
- [x] Note: this ticket touches the same simulator core as ticket 03. Expect to merge with it.

## Comments

- From review of 01: the simulator draws from one shared RNG in event order. Once arrivals and gateways exist, give each case (or each stream: arrivals, durations, branches) its own generator, e.g. `default_rng([seed, case_id])`. Otherwise a design change shifts every later draw and weakens common random numbers (ticket 13).
- Done. Tests in `tests/test_resources.py`, through the simulator seam only.
- Parameter file: `[arrivals] rate` (cases per working day, Poisson), `[lanes.<id>] capacity` (whole number), `[warm_up] length` (working days). All optional. No arrivals means every case arrives at time 0, as before. A lane not listed is unlimited.
- A warm-up without an arrival rate is rejected on load, since every case would arrive at time 0.
- `n_cases` now counts cases kept after the warm-up. Warm-up cases still run and hold resources. Case IDs count from the first case, so a log with a warm-up doesn't start at case 1.
- RNG: one generator for interarrival times (`[seed, 0]`) and one per case (`[seed, 1, case_id]`). Ticket 03: draw branch choices from the `rng` passed to `_run_case`, which is already the per-case one. Durations and branches share that stream, so removing a task in one case still shifts that case's later draws, but no other case's.
- Task execution is in `_perform_task` (waits for the lane's resource, then works). Gateways in 03 shouldn't need to touch it.
- Queueing check uses an M/D/1 fixture against the Pollaczek-Khinchine formula, because durations are fixed until 07. Once 07 adds triangular durations, an M/M/1 or M/G/1 check would line up better with §7.2.
- Unknown lane IDs in `[lanes]` are ignored for now. Validation belongs to 07.
- Meta in the results file doesn't carry the warm-up or arrival rate yet. Ticket 05 should add them.
