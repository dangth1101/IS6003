# 03: Gateways, rework and flow analysis

**What to build:** The simulator handles XOR splits and joins, AND splits and joins, and rework loops, with fixed branch probabilities from the parameter file. A flow analysis function computes the theoretical cycle time from the process graph and mean parameters, using the book's sequence, XOR, AND and rework block formulas (§7.1.1).

**Blocked by:** 01

**Status:** done

- [x] Fixture models for an XOR block, an AND block and a rework loop
- [x] Flow analysis reproduces the book's worked examples (Figs. 7.1–7.8) exactly
- [x] With unlimited capacity, mean simulated cycle time matches flow analysis within tolerance for each fixture
- [x] A configured branch probability shows up in the log within tolerance
- [x] AND branches run concurrently, so the AND block takes as long as its longest branch
- [x] Rework loops terminate and the number of iterations follows the configured probability

## Comments

- Done. Flow analysis in `src/bpmopt/flow_analysis.py`: `theoretical_cycle_time(model, params)`. Tests in `tests/test_flow_analysis.py` (book examples) and `tests/test_gateways.py` (simulator seam).
- Fixtures are the book's own models: Figs. 7.1, 7.2, 7.4, 7.6, 7.7, 7.9, 7.10 and 3.13, plus `rework_with_activity` (not from the book). They're process-only BPMN with no diagram section, so bpmn-js won't draw them. Fine for tests.
- Flow analysis hits every book value exactly: 30, 25, 29, 30, 35, 34, 8.4, 8.65, 20, and 8.9 h TCT for Ex. 7.3. Figs. 7.3, 7.5 and 7.8 are patterns with no numbers.
- Rework with a task on the loop-back arc isn't in the book. We use CT = (T + r x R)/(1 - r), derived from the same geometric series. Marked as our derivation in the code and the test.
- Flow analysis only takes block-structured models (§7.1.7) and raises `ValueError` otherwise. A rework split must have exactly two arcs: exit and loop-back.
- Parameter file, branch probabilities keyed by XOR-split ID, then by outgoing flow ID:
  `[gateways.Gateway_X]` with `branches = { Flow_Ok = 0.8, Flow_Rework = 0.2 }` and `rationale = "..."`. The loader checks each is in [0, 1] and they sum to 1. The simulator checks the keys match the split's outgoing flows when the split is first reached.
- RNG: each case gets one stream per XOR-split, `default_rng([seed, 2, case_id, crc32(gateway_id)])`, separate from the duration stream. One uniform draw per choice against the cumulative probabilities. So adding a task or gateway doesn't change any other gateway's choices for the same case (tested: Fig. 7.6 vs 7.10 give every case the same credit decision).
- AND-blocks must be structured: all branches of an AND-split end at one AND-join, else `ValueError`.
- For 07: logistic probabilities can replace a number in `branches` with a table. `_BranchDraws.choose` is the one place that reads them, and needs the case attributes passed in. Triangular durations need a `mean` property ((min + mode + max)/3), since flow analysis uses `Duration.mean`. Checking IDs against the model on load also belongs to 07.
- For 08: the log has no gateway rows, only start/end events and tasks. Rework rate per gateway has to come from repeated task executions, or 08 adds gateway decision rows. TCT is `theoretical_cycle_time` run on processing times, like Ex. 7.3.
- For 08 and 06: an XOR branch that ends at its own end event (e.g. "Proposal rejected") isn't a book block, so flow analysis rejects it today. If the corrected as-is model has that shape, 08 has to extend flow analysis, e.g. weight the rest of the process by the chance of not having ended, and mark that as our derivation too.
