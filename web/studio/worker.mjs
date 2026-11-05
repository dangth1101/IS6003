// The studio's Python runtime: Pyodide in a module Web Worker, so the page stays
// responsive while it simulates. Decisions: docs/research/studio-browser-runtime.md.
//
// Messages from the page:
//   { id, call: "<bpmopt.studio function>", args: {...} }   JSON in, JSON out
//   { id, call: "params_from_toml", args: { text } }         a parameter file to the dict the studio takes
// Messages to the page:
//   { type: "loading", stage, step, steps }   while starting; stage is a label key of the studio text
//   { type: "ready" }
//   { type: "progress", id, done, total }      after each replication of simulate_summary
//   { type: "result", id, value }
//   { type: "error", id, message }             id is null when starting failed
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

const WHEEL = "bpmopt-0.1.0-py3-none-any.whl"; // keep in step with the committed wheel (a test checks it)
const STEPS = ["load_python", "load_packages", "load_simpy", "load_bpmopt"];

const GLUE = `
import json, tomllib
from bpmopt import studio

def call(name, args_json, progress):
    args = json.loads(args_json)
    if name == "params_from_toml":
        return json.dumps(tomllib.loads(args["text"]))
    if name == "simulate_summary":
        args["progress"] = progress
    return json.dumps(getattr(studio, name)(**args))
`;

function loading(stage) {
  self.postMessage({ type: "loading", stage, step: STEPS.indexOf(stage) + 1, steps: STEPS.length });
}

async function start() {
  loading("load_python");
  const pyodide = await loadPyodide();
  loading("load_packages");
  await pyodide.loadPackage(["numpy", "pandas", "scipy", "jsonschema", "micropip"]);
  const micropip = pyodide.pyimport("micropip");
  loading("load_simpy");
  await micropip.install("simpy==4.1.2");
  loading("load_bpmopt");
  // deps=False: the wheel's metadata pins the notebook's versions and the ML packages.
  await micropip.install.callKwargs(new URL(`./${WHEEL}`, import.meta.url).href, { deps: false });
  pyodide.runPython(GLUE);
  return pyodide.globals.get("call");
}

const ready = start();
ready.then(
  () => self.postMessage({ type: "ready" }),
  (e) => self.postMessage({ type: "error", id: null, message: String(e?.message ?? e) }),
);

self.onmessage = async ({ data: { id, call, args } }) => {
  try {
    const py = await ready;
    const progress = (done, total) => self.postMessage({ type: "progress", id, done, total });
    const value = JSON.parse(py(call, JSON.stringify(args), progress));
    self.postMessage({ type: "result", id, value });
  } catch (e) {
    self.postMessage({ type: "error", id, message: pythonError(e) });
  }
};

/** The last line of a Python traceback ("ValueError: ...") is what a user can act on. */
function pythonError(e) {
  const lines = String(e?.message ?? e).trim().split("\n");
  return lines[lines.length - 1];
}
