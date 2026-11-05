# 01: Browser runtime research

**Type:** research

**What to find out:** Which Pyodide release to pin, and whether `bpmopt`'s simulation path runs on it. Specifically: the NumPy, pandas and SciPy versions it ships versus our pins (NumPy 2.5.4, pandas 3.1.0, SciPy 1.18.1) and whether our code uses anything the shipped versions lack; whether SimPy 4.1.2 and jsonschema install with micropip; how to load a local pure-Python wheel; running Pyodide in a Web Worker; whether NumPy's `SeedSequence` / PCG64 streams give the same numbers as native (so the studio matches the notebook); rough speed of one 1,000-case as-is simulation in Pyodide versus native. Also the bpmn-js Modeler version to pin (same major as the viewer's 18.28.0) and how to read selection and change events from it.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Research note saved in `docs/research/` with a source link for each claim
- [ ] Pinned Pyodide and bpmn-js Modeler versions chosen, with the reason
- [ ] A throwaway proof (outside the repo or in the scratchpad) that the as-is preset simulates in Pyodide, with timing
- [ ] Any version gap with our pins is listed with a proposed way to handle it

## Comments
