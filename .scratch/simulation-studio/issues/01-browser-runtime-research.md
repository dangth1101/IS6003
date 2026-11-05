# 01: Browser runtime research

**Type:** research

**What to find out:** Which Pyodide release to pin, and whether `bpmopt`'s simulation path runs on it. Specifically: the NumPy, pandas and SciPy versions it ships versus our pins (NumPy 2.5.4, pandas 3.1.0, SciPy 1.18.1) and whether our code uses anything the shipped versions lack; whether SimPy 4.1.2 and jsonschema install with micropip; how to load a local pure-Python wheel; running Pyodide in a Web Worker; whether NumPy's `SeedSequence` / PCG64 streams give the same numbers as native (so the studio matches the notebook); rough speed of one 1,000-case as-is simulation in Pyodide versus native. Also the bpmn-js Modeler version to pin (same major as the viewer's 18.28.0) and how to read selection and change events from it.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Research note saved in `docs/research/` with a source link for each claim
- [x] Pinned Pyodide and bpmn-js Modeler versions chosen, with the reason
- [x] A throwaway proof (outside the repo or in the scratchpad) that the as-is preset simulates in Pyodide, with timing
- [x] Any version gap with our pins is listed with a proposed way to handle it

## Comments
- 2026-11-05: claimed. Research agent started.
- 2026-11-05: done. Note in `docs/research/studio-browser-runtime.md`.
  - Pin Pyodide 314.0.7 (Python 3.14.2) and bpmn-js Modeler 18.31.1.
  - Pyodide ships NumPy 2.4.6, pandas 3.0.2, SciPy 1.18.0 and jsonschema 4.26.0. SimPy 4.1.2 installs from PyPI with micropip. Our wheel loads with `deps=False`.
  - As-is preset, 1,000 cases, seed 42: per-case cycle times and 10 replication means are bit-identical to native, in Node and in a Chrome Web Worker. 146 simulation-path tests pass under Pyodide.
  - Speed is about 2.3x native: 0.9 s per replication vs 0.38 s on an M4. First load is about 36 MB.
  - Version gap: keep the native pins and add a parity fixture that pytest and the browser check both compare against.
