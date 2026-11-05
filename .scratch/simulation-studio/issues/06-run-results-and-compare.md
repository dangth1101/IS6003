# 06: Run results and baseline comparison

**What to build:** The results view for a run (cycle time mean / median / P90 with CI, processing vs waiting, cycle time efficiency, utilisation per lane, rework per gateway, waiting per activity), with progress per replication and a rough time estimate while it runs. "Pin as baseline" keeps a run; later runs show the saving with its paired CI and before/after per lane and per activity. A run with different seed or replications than the baseline is not compared, and the page says why.

**Blocked by:** 03, 04

**Status:** ready-for-agent

- [ ] Progress updates during a run and the page stays responsive
- [ ] The comparison numbers match `compare` for the same two runs
- [ ] Changing the seed after pinning shows the "not comparable" message instead of a saving
- [ ] Checked in headless Chrome, no console errors

## Comments
