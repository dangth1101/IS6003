# Studio browser runtime

Research for the simulation studio (`.scratch/simulation-studio/issues/01-browser-runtime-research.md`). Checked 2026-11-05.

Short answer: Pyodide 314.0.7 runs the simulation path unchanged. The as-is preset with 1,000 cases and seed 42 gives bit-identical per-case cycle times and per-replication means to native `bpmopt`, at about 2.3x the native time.

## Pyodide release

- Latest stable on npm is 314.0.7 (2026-09-14). Pyodide now numbers releases after the Python version: 314.x ships Python 3.14.2. The old 0.29.x and 0.27.x lines still get patch releases, and 315.0.0 is in alpha. Sources: [npm registry](https://registry.npmjs.org/pyodide), [changelog](https://pyodide.org/en/stable/project/changelog.html).
- The 314.0.x line moved SciPy from 1.17.1 to 1.18.0 in 314.0.2 ([changelog](https://pyodide.org/en/stable/project/changelog.html)).
- Python 3.14 is fine for us: `pyproject.toml` asks for `>=3.12`.
- Picked 314.0.7 over 0.29.5 because 0.29.5 ships Python 3.13, NumPy 2.2.5, pandas 2.3.3 and SciPy 1.14.1 ([0.29.5 lock file](https://cdn.jsdelivr.net/pyodide/v0.29.5/full/pyodide-lock.json)). That is a whole pandas major behind our pin. Skipped 315 because it's alpha.

## Shipped versions vs our pins

From the [314.0.7 lock file](https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide-lock.json):

| Package | Our pin | Pyodide 314.0.7 | Gap |
| --- | --- | --- | --- |
| NumPy | 2.5.4 | 2.4.6 | one minor behind |
| pandas | 3.1.0 | 3.0.2 | one minor behind |
| SciPy | 1.18.1 | 1.18.0 | patch only |
| jsonschema | 4.26.0 | 4.26.0 | none |
| SimPy | 4.1.2 | not shipped | from PyPI via micropip |
| rfc3339-validator | 0.1.4 | not shipped | not needed in the studio (see below) |

- NumPy 2.5.0's only `numpy.random` change is a fix to the binomial sampler, which changes `Generator.binomial` and `Generator.multinomial` streams ([2.5.0 notes](https://numpy.org/doc/stable/release/2.5.0-notes.html)). `bpmopt` uses neither (no `binomial`/`multinomial` in `src/`). We use `default_rng`, `SeedSequence.generate_state`, `random`, `exponential`, `triangular`, `poisson` and `choice(p=...)`.
- pandas 3.1.0 came out 2026-10-22 ([whatsnew](https://pandas.pydata.org/docs/whatsnew/v3.1.0.html)). Its visible changes are deprecations (setitem-with-expansion dtype changes, non-bool `numeric_only`, ragged list-of-sequences constructors). None of them are features our code depends on, and the test run below confirms it.
- SciPy we only use for `scipy.stats.t` in `scenarios.py`. 1.18.0 vs 1.18.1 is a bugfix gap.
- rfc3339-validator is only there so jsonschema can check `format: date-time`. The only such field in `results.schema.json` is `generated_at`, which isn't in the `changes` section the catalog loader validates. Without the package jsonschema skips that format check, so the studio path doesn't need it. It has a pure wheel on [PyPI](https://pypi.org/project/rfc3339-validator/0.1.4/#files) if we ever do.

## Do the numbers match native?

- NumPy only promises the same stream "on the same build of numpy, in the same environment, on the same machine", and allows `Generator` stream changes in X.Y releases ([compatibility policy](https://numpy.org/doc/stable/reference/random/compatibility.html)). PCG64 itself guarantees "a fixed seed will always produce the same random integer stream" ([PCG64 docs](https://numpy.org/doc/stable/reference/random/bit_generators/pcg64.html)), and the seed goes through `SeedSequence` (same page). So the raw bits are safe; the float transforms (exponential, triangular) are what could drift across builds.
- In practice they didn't. Native (CPython 3.13.13, NumPy 2.5.4, Apple M4) and Pyodide (wasm32, NumPy 2.4.6) gave:
  - the same 1,000 case IDs and bit-identical cycle times (max difference 0.0), mean 131.5696274415606 days;
  - the same 10 replication seeds from `replication_seeds(42, 10)` and bit-identical replication means;
  - the same values from a probe of each `Generator` method we use.
- Because the policy doesn't promise this, it needs a check, not trust (see decisions).

## Test suite under Pyodide

- Ran 13 simulation-path test files (`test_simulation`, `test_analysis`, `test_lint`, `test_scenarios`, `test_gateways`, `test_resources`, `test_parameters`, `test_flow_analysis`, `test_baseline`, `test_case_attributes`, `test_to_be_model`, `test_as_is_model`, `test_event_log`) in Pyodide under Node, with the repo mounted through NODEFS and pytest 9.0.2 from the Pyodide lock.
- 146 passed in 34 s. The same files pass natively in 16 s.
- Left out: the ML tests and the ones that build the results file, since they need scikit-learn/SHAP and aren't on the studio path.

## Loading packages

- `pyodide.loadPackage([...])` loads packages listed in the Pyodide lock file. In the proof they came from `https://cdn.jsdelivr.net/pyodide/v314.0.7/full/`, the folder `pyodide.mjs` was loaded from (seen in the load log). Our list: `numpy`, `pandas`, `scipy`, `jsonschema`, `micropip`. Their own deps (python-dateutil, pytz, six, attrs, referencing, rpds-py, ...) come along.
- `micropip.install("simpy==4.1.2")` pulls SimPy from PyPI. It works because SimPy 4.1.2 has a `py3-none-any` wheel ([PyPI](https://pypi.org/project/simpy/4.1.2/#files)) and micropip installs pure-Python wheels from PyPI ([micropip API](https://micropip.pyodide.org/en/stable/project/api.html)).
- Our own wheel: `micropip.install(url, deps=False)`. The URL's last segment has to be a valid wheel file name; `http(s):` URLs and `emfs:` paths both work ([micropip API](https://micropip.pyodide.org/en/stable/project/api.html)).
- `deps=False` is required. The wheel's METADATA pins `numpy==2.5.4`, `scikit-learn` and `shap`. With deps on, micropip would try to resolve those and fail, or replace Pyodide's NumPy.
- `micropip.freeze()` can write a lock file that `loadPyodide({ lockFileURL })` reads later ([micropip API](https://micropip.pyodide.org/en/stable/project/api.html)). Not worth it for one extra package.

## Web Worker

- Pyodide 314 needs a module worker: `new Worker("./worker.mjs", { type: "module" })` and `import { loadPyodide } from ".../pyodide.mjs"` in the worker. Classic workers with `importScripts()` no longer work ([Web Worker docs](https://pyodide.org/en/stable/usage/webworker.html), [changelog 314.0.0](https://pyodide.org/en/stable/project/changelog.html)).
- Progress works: Python called a JS function after each replication, the function did `self.postMessage(...)`, and the messages reached the page about 1 s apart during the run, not all at the end.
- The page stays responsive: a 100 ms `setInterval` on the main thread kept ticking through the whole run.
- Cancelling a running simulation in place needs a `SharedArrayBuffer` and `pyodide.setInterruptBuffer()`, which needs the page to be cross-origin isolated ([interrupts docs](https://pyodide.org/en/stable/usage/keyboard-interrupts.html), [MDN on the security requirements](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/SharedArrayBuffer#security_requirements)). That takes COOP/COEP response headers on our pages, and our static setup sets none. Simpler: cancel with `worker.terminate()` ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/Worker/terminate)) and start a fresh worker (about 3 s to boot and load packages again).

## Speed and download size

Apple M4. One run is a single 1,000-case simulation of the as-is preset plus `cycle_times`. Times are from `time.perf_counter()` inside Python.

| Runtime | 1 run | 10 replications | vs native |
| --- | --- | --- | --- |
| Native CPython 3.13.13 | 0.38 s | 3.77 s | 1x |
| Pyodide in Node 24.15 | 0.89 s | 8.37 s | 2.2-2.3x |
| Pyodide in headless Chrome 156, Web Worker | 0.88-0.90 s | 8.1-9.0 s | 2.2-2.4x |

- Startup in Chrome: about 1.1 s to boot Pyodide and about 2 s to load the packages and our wheel, on a fast connection with the CDN warm.
- Download on first visit is about 36 MB: Pyodide core about 13.4 MB (`pyodide.asm.wasm` 9.6 MB, stdlib 2.5 MB, `pyodide.asm.mjs` 1.3 MB) and packages about 22.4 MB. SciPy alone is 14 MB, just for `scipy.stats.t`. The browser caches all of it after the first visit.
- Expect a slower laptop to be 2-3x slower than these numbers.

## bpmn-js Modeler

- bpmn-js latest is 18.31.1 (2026-10-21), same major as the report page's 18.28.0 ([npm registry](https://registry.npmjs.org/bpmn-js)).
- 18.29 to 18.31 have no breaking changes. They add a theme-token colour source (18.30.0), fixes for text layout overflowing and looping (18.30.1), and label fixes (18.31.0, 18.31.1) ([CHANGELOG](https://github.com/bpmn-io/bpmn-js/blob/develop/CHANGELOG.md)).
- The modeler bundle and CSS are on jsDelivr for both versions: `dist/bpmn-modeler.production.min.js`, `dist/assets/diagram-js.css`, `dist/assets/bpmn-js.css`, `dist/assets/bpmn-font/css/bpmn.css` (the font is for the palette icons). Checked with HTTP 200 on [jsDelivr](https://cdn.jsdelivr.net/npm/bpmn-js@18.31.1/dist/).
- Selection: diagram-js fires `selection.changed` with `{ oldSelection, newSelection }` ([Selection.js](https://github.com/bpmn-io/diagram-js/blob/v15.28.0/lib/features/selection/Selection.js)). Listen with `modeler.on("selection.changed", ({ newSelection }) => ...)`; an element's BPMN data is on `element.businessObject`.
- Edits: every modelling command ends with `commandStack.changed` ([CommandStack.js](https://github.com/bpmn-io/diagram-js/blob/v15.28.0/lib/command/CommandStack.js)), including undo and redo. That's the event to debounce, then `saveXML()` and re-lint. `element.changed` fires per element ([ChangeSupport.js](https://github.com/bpmn-io/diagram-js/blob/v15.28.0/lib/features/change-support/ChangeSupport.js)) and is too fine-grained for re-linting.
- Load and export: `await modeler.importXML(xml)` and `const { xml } = await modeler.saveXML({ format: true })` ([BaseViewer.js](https://github.com/bpmn-io/bpmn-js/blob/v18.31.1/lib/BaseViewer.js), which the Modeler extends).

## Proof

Throwaway, kept in the session scratchpad, not in the repo:

- `proof.py` reads `models/as_is.bpmn` and `models/as_is.params.toml`, runs one 1,000-case simulation with seed 42 and then 10 replications from `replication_seeds(42, 10)`, and returns the per-case cycle times, the replication means, timings and an RNG probe.
- The native run used the repo's venv (`uv run python proof.py`).
- `node-proof.mjs` ran it in Pyodide via the `pyodide@314.0.7` npm package.
- `site/` + `chrome-proof.mjs` ran it in a module Web Worker in headless Chrome against `python -m http.server`, loading Pyodide from jsDelivr and our wheel from the local server. The only console error was a 404 for `favicon.ico`.
- `node-pytest.mjs` ran the test files listed above under Pyodide.

## Decisions for ticket 02

- **Pyodide 314.0.7**, from `https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs`, imported in a module worker.
- **bpmn-js Modeler 18.31.1** for the studio. It's the editor, so the text-layout and label fixes since 18.28.0 matter. Leave the report page on 18.28.0, as the spec says it stays unchanged apart from the link. Load `bpmn-font/css/bpmn.css` too.
- **Loading, in the worker:**
  1. `const pyodide = await loadPyodide()`
  2. `await pyodide.loadPackage(["numpy", "pandas", "scipy", "jsonschema", "micropip"])`
  3. `await micropip.install("simpy==4.1.2")`
  4. `await micropip.install.callKwargs(new URL("./bpmopt-0.1.0-py3-none-any.whl", location.href).href, { deps: false })`
  - Keep the committed wheel's real file name; micropip parses it.
- **Version gap:** keep the native pins as they are. Don't pin the notebook down to Pyodide's versions, and don't write version-tolerant code; nothing on the path needs it. Guard it with a parity fixture instead: commit the expected per-replication means for the as-is preset (seed 42, 1,000 cases, 10 replications). The pytest suite and the headless-Chrome acceptance check both compare against it, so a NumPy or Pyodide bump that changes a stream fails loudly. Bump Pyodide only on purpose and rerun that check.
- **Not in the browser:** rfc3339-validator, scikit-learn, SHAP. `bpmopt.studio` must not import `ml`, `features`, `results` or `planted`.
- **SciPy:** keep it for now. It's 14 MB of the first load just for the t quantile, but it means the studio's CI code is the scenario runner's. If first load turns out too slow, swap `student_t.ppf` for a small table of t quantiles; that's a contained change in `scenarios._estimate`.
- **Catalog files:** `load_catalog` reads the catalog TOML and its model files by path. Write them into the Pyodide FS (or read them from strings) when the worker starts.
- **Cancel:** `worker.terminate()` and start a new worker. No interrupt buffer.
- **Expected speed:** about 0.9 s per 1,000-case replication on an M4, so about 9 s for the default run. Budget 20-25 s on a slower laptop. First visit adds about 3 s plus the 36 MB download.
- **Default run size:** keep the spec's 1,000 cases and 10 replications, with progress per replication. Use the measured time per replication for the time estimate, and warn above about 50,000 case-runs (cases x replications).
