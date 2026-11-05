// The studio's parameter panel: edit the selected task, XOR split or lane, the run settings,
// import a .bpmn and / or .params.toml, export both, and see which entries are studio defaults.
//
// The page owns the Modeler and the worker; this module only reads the diagram and calls
// bpmopt.studio through call(name, args):
//   default_parameters  after an import and after every diagram edit (a new task gets a default)
//   set_parameter       when the user applies a value (the entry gets the rationale "Set in the studio.")
//   fixed_branches      "reset to fixed" for a logistic branch
//   params_from_toml, params_to_toml   import and export of the parameter file
// Parameter updates run one after another (a queue), each on the latest parameters, so a diagram
// edit and a value edit never overwrite each other.
//
// For the page (and tickets 06 / 07):
//   const panel = createParamsPanel({ root, modeler, call, t, errorText, lang, run, onRunChange, onError, onParamsChange });
//   onParamsChange(params) after every update of the parameters (edit, diagram edit, load)
//   await panel.load({ params, name })          after the worker is ready: fill and show these parameters
//   await panel.load({ xml, params, name })     also import xml into the Modeler first (e.g. a suggestion)
//   await panel.params()                        the current parameters, after pending updates
//   panel.run()                                 the run settings { n_cases, replications, seed }
//   panel.name()                                the file name (no extension) the export uses: the loaded
//                                               name, plus EDITED once the diagram or a value was edited by hand
// The root element carries data-params and data-defaults (JSON) for the browser check.

import { el, entryKey, formatters, splitEntry } from "./dom.mjs";

const DEBOUNCE_MS = 300;
const EDITED = "_edited"; // e.g. as_is_C1_C2_edited.bpmn: no longer the catalog's design

export function createParamsPanel({ root, modeler, call, t, errorText, lang, run: runDefaults, onRunChange = () => {}, onError = () => {}, onParamsChange = () => {} }) {
  const registry = modeler.get("elementRegistry");
  const canvas = modeler.get("canvas");
  const selection = modeler.get("selection");
  const commandStack = modeler.get("commandStack");
  const { upTo: number, percentUpTo: percent } = formatters(lang);

  let state = null; // { params, defaults, dropped } from bpmopt.studio
  let name = "model"; // of the last load
  let valueEdited = false; // a value set in this panel since the last load
  let selected = null; // element ID
  let editError = null; // { key, message } of the last refused edit
  let marked = [];
  let queue = Promise.resolve();
  let timer = null;
  const settings = { ...runDefaults };

  root.classList.add("params-panel"); // styles in params-panel.css

  /** Run fn(current params) after the pending updates; it returns the new {params, defaults, dropped}.
   *  With a key (an edit), a refusal is shown at that entry; without, the returned promise rejects. */
  function update(fn, key = null) {
    const next = queue.then(async () => {
      try {
        state = await fn(state?.params);
        if (key) {
          editError = null;
          valueEdited = true;
        }
        onParamsChange(state.params);
      } catch (thrown) {
        if (!key) throw thrown;
        editError = { key, message: errorText(thrown) };
      }
      render();
    });
    queue = next.catch(() => {});
    return next;
  }

  async function currentXml() {
    return (await modeler.saveXML()).xml;
  }

  // ---------- diagram edits ----------

  function refill() {
    timer = null;
    if (!state) return;
    // An unreadable diagram (mid-edit) can't be filled; the lint panel shows why and blocks Run.
    update(async (params) => call("default_parameters", { xml: await currentXml(), params })).catch(() => {});
  }

  modeler.on("commandStack.changed", () => {
    clearTimeout(timer);
    timer = setTimeout(refill, DEBOUNCE_MS);
  });
  modeler.on("selection.changed", ({ newSelection }) => {
    selected = newSelection.length === 1 ? newSelection[0].id : null;
    editError = null;
    render();
  });

  // ---------- rendering ----------

  const labelOf = (id) => {
    const bo = registry.get(id)?.businessObject;
    return bo?.name || bo?.targetRef?.name || id;
  };

  function input(labelText, props) {
    return el("label", {}, labelText, el("input", { type: "number", step: "any", required: true, ...props }));
  }

  function errorFor(key) {
    return editError?.key === key ? el("p", { className: "error", role: "alert" }, t("param_invalid", { error: editError.message })) : null;
  }

  function header(kind, id, entryKey, entry) {
    const isDefault = state.defaults.includes(entryKey);
    return [
      el("h3", {}, labelOf(id), " ", isDefault ? el("span", { className: "badge" }, t("param_default")) : null),
      el("p", { className: "note" }, `${kind} · ${id}`),
      entry?.rationale ? el("p", { className: "note" }, entry.rationale) : null,
    ];
  }

  function terms(coefficients) {
    return Object.entries(coefficients)
      .flatMap(([attr, c]) =>
        typeof c === "object" ? Object.entries(c).map(([label, v]) => `${attr} = ${label} × ${number(v)}`) : [`${attr} × ${number(c)}`],
      )
      .join(", ");
  }

  function taskForm(id) {
    const key = entryKey("tasks", id);
    const entry = state.params.tasks[id];
    const { scale, ...base } = entry.duration;
    const fixed = "fixed" in base;
    const values = fixed ? [base.fixed] : base.triangular;
    const names = fixed ? ["fixed"] : ["min", "mode", "max"];
    const labels = fixed ? [t("param_fixed")] : [t("param_min"), t("param_mode"), t("param_max")];
    const form = el(
      "form",
      { dataset: { entry: key } },
      el("p", { className: "note" }, t("param_duration")),
      el("div", { className: "row" }, names.map((n, i) => input(labels[i], { name: n, min: 0, value: values[i] }))),
      scale ? el("p", { className: "note" }, t("param_scale", { terms: terms(scale) })) : null,
      el("div", {}, el("button", { type: "submit" }, t("param_apply"))),
      errorFor(key),
    );
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const v = names.map((n) => Number(form.elements[n].value));
      const duration = fixed ? { fixed: v[0] } : { triangular: v };
      if (scale) duration.scale = scale;
      setEntry(key, { duration });
    });
    return [...header(t("kind_task"), id, key, entry), form];
  }

  function gatewayForm(id) {
    const key = entryKey("gateways", id);
    const entry = state.params.gateways[id];
    const branches = entry.branches;
    const flows = Object.keys(branches);
    const logistic = flows.some((f) => typeof branches[f] === "object");
    if (logistic) {
      return [
        ...header(t("kind_gateway"), id, key, entry),
        el("p", { className: "note" }, t("param_branches")),
        el(
          "ul",
          {},
          flows.map((f) => {
            const p = branches[f];
            const value = p === "rest" ? t("param_rest") : typeof p === "object" ? logisticText(p.logistic) : percent(p);
            return el("li", {}, `${labelOf(f)}: ${value}`);
          }),
        ),
        el("div", {}, el("button", { type: "button", className: "secondary", dataset: { action: "reset-fixed" }, onclick: () => resetFixed(id) }, t("param_reset_fixed"))),
        errorFor(key),
      ];
    }
    const others = flows.filter((f) => branches[f] !== "rest").reduce((sum, f) => sum + branches[f], 0);
    const value = (f) => (branches[f] === "rest" ? Number((1 - others).toPrecision(12)) : branches[f]);
    const form = el(
      "form",
      { dataset: { entry: key } },
      el("p", { className: "note" }, t("param_branches")),
      flows.map((f) => input(labelOf(f), { name: f, min: 0, max: 1, value: value(f), dataset: { flow: f } })),
      el("div", {}, el("button", { type: "submit" }, t("param_apply"))),
      errorFor(key),
    );
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      setEntry(key, { branches: Object.fromEntries(flows.map((f) => [f, Number(form.elements[f].value)])) });
    });
    return [...header(t("kind_gateway"), id, key, entry), form];
  }

  function logisticText({ intercept = 0, ...coefficients }) {
    const rest = terms(coefficients);
    return t("param_logistic", { formula: rest ? `${t("param_intercept", { value: number(intercept) })}, ${rest}` : t("param_intercept", { value: number(intercept) }) });
  }

  function laneForm(id) {
    const key = entryKey("lanes", id);
    const entry = state.params.lanes[id];
    const form = el(
      "form",
      { dataset: { entry: key } },
      input(t("param_capacity"), { name: "capacity", min: 1, step: 1, value: entry.capacity }),
      el("div", {}, el("button", { type: "submit" }, t("param_apply"))),
      errorFor(key),
    );
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      setEntry(key, { capacity: Number(form.elements.capacity.value) });
    });
    return [...header(t("kind_lane"), id, key, entry), form];
  }

  function elementSection() {
    const p = state.params;
    if (selected && p.tasks?.[selected]) return taskForm(selected);
    if (selected && p.gateways?.[selected]) return gatewayForm(selected);
    if (selected && p.lanes?.[selected]) return laneForm(selected);
    return [el("p", { className: "note" }, t("params_hint"))];
  }

  function settingsSection() {
    const p = state.params;
    const badge = (key) => (state.defaults.includes(key) ? el("span", { className: "badge" }, t("param_default")) : null);
    const form = el(
      "form",
      { className: "settings", id: "run-settings-form" },
      el("label", {}, el("span", {}, t("setting_rate"), " ", badge("arrivals")),
        el("input", { type: "number", step: "any", min: 0, name: "rate", value: p.arrivals?.rate ?? "", onchange: (e) => setEntry("arrivals", { rate: Number(e.target.value) }) })),
      el("label", {}, el("span", {}, t("setting_warm_up"), " ", badge("warm_up")),
        el("input", { type: "number", step: "any", min: 0, name: "warm_up", value: p.warm_up?.length ?? 0, onchange: (e) => setEntry("warm_up", { length: Number(e.target.value) }) })),
      cycleEndInput(),
      runInput(t("setting_cases"), "n_cases", 1),
      runInput(t("setting_replications"), "replications", 2),
      runInput(t("setting_seed"), "seed", 0),
    );
    form.addEventListener("submit", (e) => e.preventDefault());
    return [el("h2", {}, t("settings_title")), form, errorFor("arrivals"), errorFor("warm_up"), errorFor("cycle_time"), errorFor("run")];
  }

  /** Where a case's cycle time ends: a task of the model, or (empty value) its end events. */
  function cycleEndInput() {
    const select = el("select", {
      name: "cycle_time", id: "cycle-time-end",
      onchange: (e) => setEntry("cycle_time", { ends_at: e.target.value || null }),
    },
      el("option", { value: "" }, t("setting_cycle_end_default")),
      Object.keys(state.params.tasks ?? {}).map((id) => el("option", { value: id }, labelOf(id))));
    select.value = state.params.cycle_time?.ends_at ?? "";
    return el("label", { className: "wide" }, t("setting_cycle_end"), select);
  }

  function runInput(labelText, key, min) {
    return el("label", {}, labelText, el("input", {
      type: "number", step: 1, min, name: key, value: settings[key],
      onchange: (e) => {
        const value = Number(e.target.value);
        if (!Number.isInteger(value) || value < min) {
          editError = { key: "run", message: t("setting_whole_number", { setting: labelText, min }) };
        } else {
          settings[key] = value;
          editError = null;
          onRunChange(run());
        }
        render();
      },
    }));
  }

  function describe(key) {
    const [section, id] = splitEntry(key);
    const p = state.params;
    if (section === "arrivals") return [t("entry_arrivals"), t("value_rate", { rate: number(p.arrivals.rate) })];
    if (section === "warm_up") return [t("entry_warm_up"), t("value_days", { days: number(p.warm_up.length) })];
    const entry = p[section]?.[id];
    if (section === "tasks") {
      const d = entry.duration;
      const value = "fixed" in d ? t("value_days", { days: number(d.fixed) }) : t("value_triangular", { min: number(d.triangular[0]), mode: number(d.triangular[1]), max: number(d.triangular[2]) });
      return [labelOf(id), value];
    }
    if (section === "lanes") return [labelOf(id), t("value_capacity", { capacity: entry.capacity })];
    if (section === "gateways") {
      return [labelOf(id), Object.entries(entry.branches).map(([f, v]) => `${labelOf(f)} ${typeof v === "number" ? percent(v) : t("param_rest")}`).join(", ")];
    }
    return [key, ""];
  }

  function defaultsSection() {
    const items = state.defaults.map((key) => {
      const [what, value] = describe(key);
      const [, id] = splitEntry(key);
      const target = id && registry.get(id);
      return el("li", { dataset: { entry: key } },
        target ? el("button", { type: "button", onclick: () => selection.select(target) }, what) : what, `: ${value}`);
    });
    return [
      el("h2", {}, t("defaults_title", { count: state.defaults.length })),
      items.length ? el("ul", { id: "defaults-list" }, items) : el("p", { className: "note" }, t("defaults_none")),
      state.dropped.length ? el("p", { className: "note" }, t("dropped", { entries: state.dropped.join(", ") })) : null,
    ];
  }

  function ioSection() {
    const file = el("input", { type: "file", multiple: true, accept: ".bpmn,.xml,.toml", hidden: true, id: "import-file", onchange: (e) => importFiles([...e.target.files]).finally(() => { e.target.value = ""; }) });
    return [el("div", { className: "io" },
      el("button", { type: "button", className: "secondary", id: "import", onclick: () => file.click() }, t("import")),
      el("button", { type: "button", className: "secondary", id: "export-bpmn", onclick: exportBpmn }, t("export_bpmn")),
      el("button", { type: "button", className: "secondary", id: "export-params", onclick: exportParams }, t("export_params")),
      file,
    ), el("p", { className: "note" }, t("import_hint"))];
  }

  function markDefaults() {
    for (const id of marked) if (registry.get(id)) canvas.removeMarker(id, "studio-default");
    marked = state.defaults.map((key) => splitEntry(key)[1]).filter((id) => id && registry.get(id));
    for (const id of marked) canvas.addMarker(id, "studio-default");
  }

  function render() {
    if (!state) return;
    root.dataset.params = JSON.stringify(state.params);
    root.dataset.defaults = JSON.stringify(state.defaults);
    markDefaults();
    root.replaceChildren(
      el("section", {}, ioSection()),
      el("section", { id: "element-params" }, el("h2", {}, t("params_title")), elementSection()),
      el("section", {}, settingsSection()),
      el("section", {}, defaultsSection()),
    );
  }

  // ---------- actions ----------

  async function setEntry(key, fields) {
    clearTimeout(timer);
    if (timer) refill();
    return update(async (params) => call("set_parameter", { xml: await currentXml(), params, entry: key, fields }), key);
  }

  async function resetFixed(id) {
    const key = entryKey("gateways", id);
    return update(async (params) => {
      const fields = await call("fixed_branches", { params, gateway_id: id }); // { branches, rationale }
      return call("set_parameter", { xml: await currentXml(), params, entry: key, fields });
    }, key);
  }

  async function load({ xml, params, name: newName }) {
    clearTimeout(timer);
    timer = null;
    if (newName) name = newName;
    valueEdited = false;
    selected = null;
    editError = null;
    return update(async () => {
      if (xml !== undefined) {
        await modeler.importXML(xml); // the page fits the diagram to the view on import.done
        await call("lint_xml", { xml: await currentXml() }); // refuses (unreadable_*) a broken file
      }
      return call("default_parameters", params ? { xml: await currentXml(), params } : { xml: await currentXml() });
    });
  }

  async function importFiles(files) {
    const model = files.find((f) => /\.(bpmn|xml)$/i.test(f.name));
    const paramFile = files.find((f) => /\.toml$/i.test(f.name));
    let params;
    try {
      if (paramFile) params = await call("params_from_toml", { text: await paramFile.text() });
    } catch (thrown) {
      return onError(t("import_failed", { file: paramFile.name, error: errorText(thrown) }));
    }
    if (model) {
      try {
        // A new model without a parameter file starts from studio defaults only.
        await load({ xml: await model.text(), params, name: model.name.replace(/\.(bpmn|xml)$/i, "") });
      } catch (thrown) {
        onError(t("import_failed", { file: model.name, error: errorText(thrown) }));
      }
    } else if (paramFile) {
      await load({ params, name: paramFile.name.replace(/(\.params)?\.toml$/i, "") });
    }
  }

  function download(fileName, text, type) {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const a = el("a", { href: url, download: fileName });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function exportBpmn() {
    const { xml } = await modeler.saveXML({ format: true });
    download(`${exportName()}.bpmn`, xml, "application/xml");
  }

  async function exportParams() {
    const params = await currentParams();
    download(`${exportName()}.params.toml`, await call("params_to_toml", { params }), "application/toml");
  }

  /** The loaded name, marked EDITED once the diagram (anything to undo) or a value was edited by hand. */
  function exportName() {
    const edited = valueEdited || commandStack.canUndo();
    return edited && !name.endsWith(EDITED) ? `${name}${EDITED}` : name;
  }

  async function currentParams() {
    if (timer) {
      clearTimeout(timer);
      refill();
    }
    await queue;
    return state.params;
  }

  function run() {
    return { ...settings };
  }

  return { load, params: currentParams, run, name: exportName };
}
