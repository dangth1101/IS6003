# 03: Gateways, rework and flow analysis

**What to build:** The simulator handles XOR splits and joins, AND splits and joins, and rework loops, with fixed branch probabilities from the parameter file. A flow analysis function computes the theoretical cycle time from the process graph and mean parameters, using the book's sequence, XOR, AND and rework block formulas (§7.1.1).

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Fixture models for an XOR block, an AND block and a rework loop
- [ ] Flow analysis reproduces the book's worked examples (Figs. 7.1–7.8) exactly
- [ ] With unlimited capacity, mean simulated cycle time matches flow analysis within tolerance for each fixture
- [ ] A configured branch probability shows up in the log within tolerance
- [ ] AND branches run concurrently, so the AND block takes as long as its longest branch
- [ ] Rework loops terminate and the number of iterations follows the configured probability
