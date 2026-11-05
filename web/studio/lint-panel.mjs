// The live lint panel: runs the book's lint rules (bpmopt.studio.lint_xml, in the worker) on the
// diagram after each edit and lists the violations. Clicking one selects its element.
//
//   const panel = createLintPanel({ container, modeler, lint, t, errorText, onChange });
//
// lint(xml) is a promise of lint_xml's result, [{rule, severity, element_id, message}]; it
// rejects when the document can't be read. t(key, vars) is the page's label lookup, errorText(e) the text of an error.
// onChange(state) is called whenever the panel's state changes; state is one of
//   { status: "checking" }                               an edit is waiting for its result
//   { status: "checked", errors, warnings }               counts of the latest result
//   { status: "unreadable", text }                        lint_xml refused; text is errorText of it
// blocksRun(state) says whether Run must stay disabled (anything but a checked model without
// errors), and runBlockedReason(state, t) gives the text shown next to Run.

const DEBOUNCE_MS = 300;

export function createLintPanel({ container, modeler, lint, t, errorText, onChange = () => {} }) {
  const eventBus = modeler.get("eventBus");
  let latest = 0; // the newest lint request; older answers are dropped
  let timer = null;
  let state = { status: "checking" };

  const heading = document.createElement("h2");
  heading.textContent = t("lint_heading");
  const summary = document.createElement("p");
  summary.className = "lint-summary muted small";
  const list = document.createElement("ul");
  list.className = "lint-list";
  container.replaceChildren(heading, summary, list);

  function setState(next, violations = []) {
    state = next;
    container.dataset.status = next.status;
    renderSummary();
    renderList(violations);
    onChange(state);
  }

  function renderSummary() {
    summary.classList.toggle("error", state.status === "unreadable");
    if (state.status === "checking") summary.textContent = t("lint_checking");
    else if (state.status === "unreadable") summary.textContent = t("lint_unreadable", { error: state.text });
    else if (state.errors + state.warnings === 0) summary.textContent = t("lint_ok");
    else summary.textContent = t("lint_count", { errors: state.errors, warnings: state.warnings });
  }

  function renderList(violations) {
    // While checking, keep the last list so it doesn't flicker on every edit.
    if (state.status === "checking") return;
    list.replaceChildren(...violations.map(item));
  }

  function item(violation) {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = `lint-item lint-${violation.severity}`;
    button.dataset.element = violation.element_id;
    button.dataset.rule = violation.rule;
    const badge = document.createElement("span");
    badge.className = "lint-badge";
    badge.textContent = violation.severity === "error" ? t("lint_error") : t("lint_warning");
    const rule = document.createElement("span");
    rule.className = "lint-rule";
    rule.textContent = violation.rule;
    const message = document.createElement("span");
    message.className = "lint-message";
    message.textContent = violation.message;
    const where = document.createElement("span");
    where.className = "lint-element muted small";
    where.textContent = elementName(violation.element_id);
    button.append(badge, rule, message, where);
    const element = shapeFor(violation.element_id);
    if (element) {
      button.title = t("lint_show");
      button.addEventListener("click", () => select(element));
    } else {
      button.disabled = true;
    }
    li.append(button);
    return li;
  }

  /** The diagram element a violation points at. A process-level rule (G7, POOL) names the
   *  process, which bpmn-js draws as its pool, so that one selects the pool. */
  function shapeFor(id) {
    const registry = modeler.get("elementRegistry");
    return registry.get(id) ?? registry.find((e) => e.businessObject?.processRef?.id === id) ?? null;
  }

  function elementName(id) {
    const element = shapeFor(id);
    const name = element?.businessObject?.name?.trim();
    return name ? `${name} (${id})` : id;
  }

  function select(element) {
    modeler.get("selection").select(element);
    modeler.get("canvas").scrollToElement(element);
  }

  async function check() {
    const request = ++latest;
    let violations;
    try {
      const { xml } = await modeler.saveXML();
      violations = await lint(xml);
    } catch (thrown) {
      if (request === latest) setState({ status: "unreadable", text: errorText(thrown) });
      return;
    }
    if (request !== latest) return;
    const errors = violations.filter((v) => v.severity === "error").length;
    setState({ status: "checked", errors, warnings: violations.length - errors }, violations);
  }

  function schedule() {
    clearTimeout(timer);
    latest++; // an answer for the diagram before this edit no longer counts
    if (state.status !== "checking") setState({ status: "checking" });
    timer = setTimeout(check, DEBOUNCE_MS);
  }

  eventBus.on("commandStack.changed", schedule);
  eventBus.on("import.done", schedule);
  setState(state);

  return {
    get state() { return state; },
    /** Lint the diagram now, without waiting for an edit (e.g. once the worker is ready). */
    check: () => { clearTimeout(timer); return check(); },
  };
}

export function blocksRun(state) {
  return !(state.status === "checked" && state.errors === 0);
}

export function runBlockedReason(state, t) {
  if (state.status === "checking") return t("run_blocked_checking");
  if (state.status === "unreadable") return t("run_blocked_unreadable");
  if (state.errors > 0) return t("run_blocked_errors", { errors: state.errors });
  return "";
}
