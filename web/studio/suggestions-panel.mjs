// The suggestions panel: the four changes of the change catalog (C1-C4), each with its driver,
// Appendix A heuristic, expected effect and Devil's Quadrangle trade-off, and an Apply / Undo
// button. A step loads the catalog's design for the new change set into the diagram and the
// parameter panel, and outlines what it changed in the diagram.
//
// The panel keeps no state of its own about what is applied: it asks bpmopt.studio (in the worker)
//   suggestions      { xml, params }       -> { changes, available, applied, exact }
//   apply_suggestion { xml, change_ids }   -> { xml, params, changes }   the catalog's design
//   diff_designs     { before_xml, before_params, after_xml, after_params } -> what to outline
// after every diagram edit, parameter change and import. So an import of to_be.bpmn shows C1 and
// C2 as applied, and Ctrl+Z after a hand edit makes the suggestions available again.
// Undo of a change is applying the current set without it, which gives back the earlier design
// exactly (the catalog's parameters, whatever they were before).
//
//   const panel = createSuggestionsPanel({ root, modeler, call, t, params, backToPreset, onError });
//   panel.refresh()          once the parameter panel has its first parameters; later refreshes are automatic
//   panel.paramsChanged()    the page calls this when the parameter panel's values change
// params is the parameter panel (load, params). backToPreset() reloads the as-is preset.
// root carries data-available, data-applied (JSON) and data-highlighted (JSON) for the browser check.

const DEBOUNCE_MS = 300;
const MARKER = "studio-changed";

export function createSuggestionsPanel({ root, modeler, call, t, params: paramsPanel, backToPreset, onError = () => {} }) {
  const canvas = modeler.get("canvas");
  const registry = modeler.get("elementRegistry");
  let state = null; // suggestions() for the current design
  let started = false;
  let busy = false;
  let stepping = false; // our own import: keep the last step's summary
  let lastStep = null; // diff_designs of the last step
  let latest = 0;
  let timer = null;

  root.classList.add("suggestions-panel"); // styles in suggestions-panel.css

  const trade = { better: t("trade_better"), worse: t("trade_worse"), neutral: t("trade_neutral") };
  const dimensions = [["time", t("trade_time")], ["cost", t("trade_cost")], ["quality", t("trade_quality")], ["flexibility", t("trade_flexibility")]];

  function el(tag, props = {}, ...children) {
    const node = Object.assign(document.createElement(tag), props);
    node.append(...children.filter((c) => c !== null && c !== undefined));
    return node;
  }

  // ---------- what the current design is ----------

  async function currentDesign() {
    const params = await paramsPanel.params();
    const { xml } = await modeler.saveXML();
    return { xml, params };
  }

  async function refresh() {
    started = true;
    clearTimeout(timer);
    timer = null;
    const request = ++latest;
    try {
      const { xml, params } = await currentDesign();
      const next = await call("suggestions", { xml, params });
      if (request !== latest) return;
      state = next;
    } catch (e) {
      // An unreadable diagram (mid-edit) is no preset design; the lint panel says why.
      if (request !== latest) return;
      state = { ...(state ?? { changes: [] }), available: false, applied: null, exact: null };
    }
    render();
  }

  function later() {
    if (!started || stepping) return;
    clearTimeout(timer);
    timer = setTimeout(refresh, DEBOUNCE_MS);
  }

  modeler.on("commandStack.changed", later);
  modeler.on("import.done", () => {
    if (stepping) return;
    lastStep = null; // a new model from elsewhere (import, back to preset)
    later();
  });

  // ---------- steps ----------

  async function step(changeIds) {
    if (busy || !state?.available) return;
    busy = true;
    stepping = true;
    render();
    try {
      const before = await currentDesign();
      const design = await call("apply_suggestion", { xml: before.xml, change_ids: changeIds });
      const name = design.changes.length ? `as_is_${design.changes.join("_")}` : "as_is";
      await paramsPanel.load({ xml: design.xml, params: design.params, name });
      const after = await currentDesign();
      lastStep = await call("diff_designs", {
        before_xml: before.xml, before_params: before.params, after_xml: after.xml, after_params: after.params,
      });
      highlight();
    } catch (e) {
      onError(t("suggestion_failed", { error: e.message }));
    } finally {
      busy = false;
      stepping = false;
      await refresh();
    }
  }

  function toggle(id) {
    const applied = state.applied ?? [];
    return step(applied.includes(id) ? applied.filter((i) => i !== id) : [...applied, id]);
  }

  async function goBack() {
    busy = true;
    render();
    try {
      await backToPreset();
    } catch (e) {
      onError(t("suggestion_failed", { error: e.message }));
    } finally {
      busy = false;
      await refresh();
    }
  }

  /** The IDs to outline: added and reconnected elements, and elements with new parameters. */
  function highlighted() {
    if (!lastStep) return [];
    const ids = [
      ...lastStep.added.map((r) => r.id),
      ...lastStep.rerouted.map((r) => r.id),
      ...lastStep.parameters.map((key) => key.split(/\.(.*)/s)[1]).filter(Boolean),
    ];
    return [...new Set(ids)].filter((id) => registry.get(id));
  }

  function highlight() {
    // The step's import made a fresh canvas, so there are no old markers to remove.
    for (const id of highlighted()) canvas.addMarker(id, MARKER);
  }

  // ---------- rendering ----------

  function card(change) {
    const applied = state.applied?.includes(change.id) ?? false;
    const disabled = busy || !state.available;
    const button = el("button", {
      type: "button", className: applied ? "secondary" : "", disabled, onclick: () => toggle(change.id),
    }, applied ? t("suggestion_undo") : t("suggestion_apply"));
    button.dataset.change = change.id;
    const chips = el("ul", { className: "trade" }, ...dimensions.map(([key, label]) =>
      el("li", { className: `trade-${change.trade_off[key]}` }, `${label}: ${trade[change.trade_off[key]] ?? change.trade_off[key]}`)));
    const article = el("article", { className: applied ? "suggestion applied" : "suggestion" },
      el("header", {},
        el("h3", {}, el("span", { className: "id" }, change.id), " ", change.title),
        applied ? el("span", { className: "badge" }, t("suggestion_applied")) : null),
      el("p", { className: "heuristic" }, t("suggestion_heuristic", { name: change.heuristic.name, ref: change.heuristic.ref })),
      el("dl", {},
        el("dt", {}, t("suggestion_driver")), el("dd", {}, change.driver),
        el("dt", {}, t("suggestion_effect")), el("dd", {}, change.expected_effect),
        el("dt", {}, t("suggestion_trade_off")), el("dd", {}, chips, el("span", { className: "note" }, change.trade_off.note))),
      el("div", { className: "actions" }, button));
    article.dataset.change = change.id;
    return article;
  }

  function notice() {
    if (!state.available) {
      return el("div", { className: "unavailable", role: "status" },
        el("p", {}, t("suggestions_unavailable")),
        el("button", { type: "button", id: "back-to-preset", disabled: busy, onclick: goBack }, t("suggestions_back")));
    }
    if (busy) return el("p", { className: "muted" }, t("suggestions_applying"));
    if (state.exact === false) return el("p", { className: "hand-params" }, t("suggestions_hand_params"));
    return null;
  }

  function stepSummary() {
    if (!lastStep || !state.available) return null;
    return el("p", { className: "step muted" }, t("suggestion_diff", {
      added: lastStep.added.length, rerouted: lastStep.rerouted.length,
      removed: lastStep.removed.length, parameters: lastStep.parameters.length,
    }));
  }

  function render() {
    root.dataset.available = String(state?.available ?? false);
    root.dataset.applied = JSON.stringify(state?.applied ?? null);
    root.dataset.highlighted = JSON.stringify(highlighted());
    root.classList.toggle("disabled", !!state && !state.available);
    root.replaceChildren(...[
      el("h2", {}, t("suggestions_heading")),
      el("p", { className: "muted small" }, t("suggestions_intro")),
      state ? notice() : el("p", { className: "muted" }, t("suggestions_checking")),
      state ? stepSummary() : null,
      state ? el("div", { className: "suggestion-list" }, ...state.changes.map(card)) : null,
    ].filter(Boolean));
  }

  render();
  return { refresh, paramsChanged: later };
}
