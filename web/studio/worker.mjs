// The studio's Python runtime: Pyodide in a module Web Worker, so the page stays
// responsive while it simulates. Decisions: docs/research/studio-browser-runtime.md.
//
// Messages from the page, { id, call, args }: call is a bpmopt.studio function, args its
// keyword arguments, JSON in and JSON out (signatures and return shapes in the studio module):
//   lint_xml            { xml }
//   default_parameters  { xml, params? }
//   simulate_summary    { xml, params, n_cases, seed, replications }   sends progress
//   compare             { baseline, variant }                         two simulate_summary results
//   suggestions         { xml, params? }   the catalog, and which changes the design carries
//   apply_suggestion    { xml, change_ids }
//   diff_designs        { before_xml, before_params, after_xml, after_params }   what a step changed
//   set_parameter       { xml, params, entry, fields }   one entry from the parameter panel
//   fixed_branches      { params, gateway_id }           "reset to fixed" for logistic branches
//   params_to_toml      { params }                       the parameter file's text, for export
//   params_from_toml    { text }                         a parameter file's text to the dict the studio takes
// The worker adds two arguments itself: progress (a function that posts progress messages)
// and preset (the PRESET_FILES below, file name -> text) to the functions that take them.
// Messages to the page:
//   { type: "loading", stage, step, steps }   while starting; stage is a label key of the studio text
//   { type: "ready" }
//   { type: "progress", id, done, total }      after each replication of simulate_summary
//   { type: "result", id, value }
//   { type: "error", id, code, data, detail }  id is null when starting failed. code and data are a
//       StudioError's (Python) or the worker's own (errors.mjs); the page shows the code's text from
//       the studio content file. An unexpected failure is code "internal", its detail for the console.
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";
import { asStudioError, studioError } from "./errors.mjs";

const WHEEL = "bpmopt-0.1.0-py3-none-any.whl"; // keep in step with the committed wheel (a test checks it)
const STEPS = ["load_python", "load_packages", "load_simpy", "load_bpmopt"];
// The as-is preset and the change catalog with its models, from presets/ (scripts/build_studio.py copies them).
const PRESET_FILES = ["as_is.bpmn", "as_is.params.toml", "to_be.catalog.toml", "to_be_c1.bpmn", "to_be_c2.bpmn", "to_be.bpmn"];

// call returns {"value": ...} or, for a StudioError, {"error": {code, data, detail}}. Any other
// exception is a bug and comes out as a PythonError (see the message handler).
const GLUE = `
import inspect, json
from bpmopt import studio

def call(name, args_json, progress, preset_json):
    args = json.loads(args_json)
    function = getattr(studio, name)
    accepts = inspect.signature(function).parameters
    if "progress" in accepts:
        args["progress"] = progress
    if "preset" in accepts:
        args["preset"] = json.loads(preset_json)
    try:
        return json.dumps({"value": function(**args)})
    except studio.StudioError as e:
        return json.dumps({"error": {"code": e.code, "data": e.data, "detail": str(e)}})
`;

function loading(stage) {
  self.postMessage({ type: "loading", stage, step: STEPS.indexOf(stage) + 1, steps: STEPS.length });
}

async function fetchPreset() {
  const texts = await Promise.all(
    PRESET_FILES.map(async (name) => {
      const file = `presets/${name}`;
      const response = await fetch(new URL(`./${file}`, import.meta.url));
      if (!response.ok) throw studioError("fetch_failed", { file, status: response.status });
      return [name, await response.text()];
    }),
  );
  return JSON.stringify(Object.fromEntries(texts));
}

async function start() {
  const preset = fetchPreset();
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
  return { call: pyodide.globals.get("call"), preset: await preset };
}

const ready = start();
ready.then(
  () => self.postMessage({ type: "ready" }),
  (thrown) => postError(null, thrown),
);

self.onmessage = async ({ data: { id, call, args } }) => {
  try {
    const py = await ready;
    const progress = (done, total) => self.postMessage({ type: "progress", id, done, total });
    const out = JSON.parse(py.call(call, JSON.stringify(args), progress, py.preset));
    if (out.error) self.postMessage({ type: "error", id, ...out.error });
    else self.postMessage({ type: "result", id, value: out.value });
  } catch (thrown) {
    postError(id, thrown); // a PythonError (a bug in the studio) or a failed start
  }
};

function postError(id, thrown) {
  const { code, data, detail } = asStudioError(thrown);
  self.postMessage({ type: "error", id, code, data, detail });
}
