// The studio's results panel: what one run gives (cycle time with CIs, processing vs waiting,
// cycle time efficiency, utilisation per lane, rework per XOR split, waiting per activity), a
// pinned baseline, and the comparison of a later run with it (bpmopt.studio.compare).
//
// The page owns the worker and the Run button; this module only renders and calls compare:
//   const results = createResultsPanel({ container, t, errorText, lang, compare });
//   const timer = results.startRun(run)   run = { n_cases, replications, seed }; at the start of a run
//   timer.status(done, total)             the status text after `done` replications, with a rough time left
//   await results.show(summary, seconds)  a finished simulate_summary result; compares it with the baseline
//   results.runChanged(run)               the run settings changed (params panel onRunChange)
// compare(baseline, variant) is a promise of compare's result; it rejects when the runs can't be
// paired (code not_comparable, data.settings the settings that differ), shown as the reason.
// Which settings must match comes from Python too: a summary's paired_on.
// The container carries data-summary (the shown run) and data-compare (the comparison, absent when
// there is none) as full-precision JSON for the browser checks.

import { el, formatters } from "./dom.mjs";

// Before a run has finished, the time estimate uses the as-is preset's speed in headless Chrome:
// 8.6 s for 1,000 cases x 10 replications (ticket 03). After a run, that run's own speed.
const PRIOR_SECONDS_PER_CASE = 8.6 / 10_000;

export function createResultsPanel({ container, t, errorText, lang, compare }) {
  const { fixed: fmt, percent: pct, whole } = formatters(lang);
  const days = (e) => `${fmt(e.value)} ${t("days")}`;
  const range = (e, f = fmt) => t("ci", { low: f(e.ci_low), high: f(e.ci_high) });
  const name = (label, id) => label || id; // XOR splits often have no label in the diagram

  let secondsPerCase = PRIOR_SECONDS_PER_CASE;
  let current = null; // the shown simulate_summary result
  let baseline = null; // the pinned one
  let comparison = null; // { result } or { refused: reason text } of current against baseline
  let settings = null; // the run settings now in the panel

  container.classList.add("results-panel"); // styles in results-panel.css

  // ---------- progress ----------

  function startRun(run) {
    settings = { ...run };
    const started = performance.now();
    const cases = (done) => run.n_cases * done;
    return {
      status(done, total) {
        const elapsed = (performance.now() - started) / 1000;
        const rate = done > 0 ? elapsed / cases(done) : secondsPerCase;
        const left = rate * run.n_cases * (total - done);
        const running = t("running", { done: Math.min(done + 1, total), total });
        if (done >= total) return running;
        if (left < 1) return `${running} ${t("time_left_soon")}`;
        if (left < 90) return `${running} ${t("time_left_seconds", { seconds: Math.ceil(left) })}`;
        return `${running} ${t("time_left_minutes", { minutes: Math.ceil(left / 60) })}`;
      },
      finish(seconds) {
        secondsPerCase = seconds / cases(run.replications);
      },
    };
  }

  // ---------- state ----------

  async function show(summary, seconds) {
    current = summary;
    current.seconds = seconds;
    comparison = null;
    if (baseline && baseline !== current) {
      try {
        comparison = { result: await compare(strip(baseline), strip(current)) };
      } catch (thrown) {
        comparison = { refused: thrown?.code === "not_comparable" ? differsText(thrown.data.settings) : errorText(thrown) };
      }
    }
    render();
  }

  function runChanged(run) {
    settings = { ...run };
    renderMismatch();
  }

  function pin() {
    baseline = current;
    comparison = null;
    render();
  }

  function unpin() {
    baseline = null;
    comparison = null;
    render();
  }

  const strip = ({ seconds, ...summary }) => summary; // compare gets simulate_summary's result as it was

  /** The settings in which `run` differs from the baseline, as text, or "". paired_on comes from simulate_summary. */
  function mismatch(run) {
    if (!baseline || !run) return "";
    return differsText(baseline.paired_on
      .filter((key) => baseline[key] !== run[key])
      .map((setting) => ({ setting, baseline: baseline[setting], variant: run[setting] })));
  }

  /** "Seed 42 in the baseline, 43 now; ..." for compare's not_comparable data.settings. */
  function differsText(settings) {
    const label = { seed: t("setting_seed"), replications: t("setting_replications"), n_cases: t("setting_cases") };
    return settings
      .map(({ setting, baseline: before, variant: now }) => t("differs", { setting: label[setting] ?? setting, baseline: whole(before), run: whole(now) }))
      .join("; ");
  }

  // ---------- rendering ----------

  const mismatchNote = el("p", { id: "baseline-mismatch", className: "notice small", hidden: true });

  function renderMismatch() {
    const differs = mismatch(settings);
    mismatchNote.textContent = differs ? t("baseline_mismatch", { differs }) : "";
    mismatchNote.hidden = !differs;
  }

  function render() {
    if (!current) return;
    container.dataset.summary = JSON.stringify(strip(current));
    if (comparison?.result) container.dataset.compare = JSON.stringify(comparison.result);
    else delete container.dataset.compare;
    const blocks = [
      el("h2", {}, t("results_title")),
      baselineBlock(),
      mismatchNote,
      comparisonBlock(),
      el("h3", {}, t("this_run")),
      runTiles(current),
      el("p", { className: "muted small" }, t("run_time", { seconds: fmt(current.seconds) }),
        " ", t("run_settings", { cases: whole(current.n_cases), replications: current.replications, seed: current.seed })),
      lanesBlock(),
      reworkBlock(),
      waitingBlock(),
    ];
    container.replaceChildren(...blocks.flat(Infinity).filter(Boolean));
    renderMismatch();
    container.hidden = false;
  }

  function baselineBlock() {
    if (!baseline) {
      return el("div", { className: "baseline-bar" },
        el("button", { id: "pin-baseline", type: "button", onclick: pin }, t("pin_baseline")),
        el("span", { className: "muted small" }, t("pin_hint")));
    }
    const isCurrent = baseline === current;
    return el("div", { className: "baseline-bar" },
      el("div", { id: "baseline-box", className: "baseline-box small" },
        el("span", { className: "swatch baseline" }),
        el("span", {}, t("baseline_summary", {
          mean: fmt(baseline.cycle_time.mean.value), cases: whole(baseline.n_cases),
          replications: baseline.replications, seed: baseline.seed,
        })),
        isCurrent ? el("span", { className: "muted" }, t("baseline_is_this_run")) : null),
      isCurrent ? null : el("button", { id: "pin-baseline", type: "button", onclick: pin }, t("pin_again")),
      el("button", { id: "unpin-baseline", type: "button", className: "secondary", onclick: unpin }, t("unpin_baseline")));
  }

  function tile(id, label, estimate, format = (e) => [fmt(e.value), " ", el("span", {}, t("days"))], rangeFormat = fmt) {
    return el("div", { className: "tile", id },
      el("dt", {}, label),
      el("dd", {}, format(estimate), el("span", { className: "sub" }, range(estimate, rangeFormat))));
  }

  function runTiles(s) {
    return el("dl", { className: "tiles" },
      tile("result-ct-mean", t("mean_cycle_time"), s.cycle_time.mean),
      tile("result-ct-median", t("median_cycle_time"), s.cycle_time.median),
      tile("result-ct-p90", t("p90_cycle_time"), s.cycle_time.p90),
      tile("result-processing", t("processing_time"), s.processing_time.mean),
      tile("result-waiting", t("waiting_time"), s.waiting_time.mean),
      tile("result-cte", t("cycle_time_efficiency"), s.cycle_time_efficiency, (e) => pct(e.value), (v) => pct(v)));
  }

  function comparisonBlock() {
    if (!comparison) return null;
    if (comparison.refused) {
      return el("section", { id: "comparison" },
        el("h3", {}, t("compare_title")),
        el("p", { id: "not-comparable", className: "notice" }, t("not_comparable", { reason: comparison.refused })));
    }
    const c = comparison.result;
    const share = (e) => pct(e.value, 1);
    const stats = [["mean", t("mean_cycle_time")], ["median", t("median_cycle_time")], ["p90", t("p90_cycle_time")]];
    return el("section", { id: "comparison" },
      el("h3", {}, t("compare_title")),
      el("p", { className: "muted small" }, t("compare_hint")),
      el("dl", { className: "tiles" },
        tile("compare-saving", t("saving"), c.saving),
        tile("compare-saving-share", t("saving_share"), c.saving_share, share, (v) => pct(v, 1))),
      ciPlot(c),
      table("compare-cycle-time", [t("measure"), t("baseline"), t("this_run")],
        stats.map(([key, label]) => [label, ciCell(c.baseline.cycle_time[key]), ciCell(c.variant.cycle_time[key])]), [1, 2]));
  }

  /** Mean cycle time of both runs on one axis: a dot at the mean and a line over its 95% CI. */
  function ciPlot(c) {
    const runs = [[t("baseline"), c.baseline.cycle_time.mean, "baseline"], [t("this_run"), c.variant.cycle_time.mean, "variant"]];
    const lo = Math.min(...runs.map(([, e]) => e.ci_low)) * 0.95;
    const hi = Math.max(...runs.map(([, e]) => e.ci_high)) * 1.02;
    const pos = (v) => `${((v - lo) / (hi - lo)) * 100}%`;
    return el("div", { className: "ci-plot", "aria-hidden": "true" },
      runs.map(([label, e, cls]) => [
        el("div", {}, label),
        el("div", { className: `ci-track ${cls}`, title: `${label}: ${days(e)}, ${range(e)}` },
          el("div", { className: "ci-range", style: `left:${pos(e.ci_low)}; width:calc(${pos(e.ci_high)} - ${pos(e.ci_low)})` }),
          el("div", { className: "ci-dot", style: `left:${pos(e.value)}` })),
      ]));
  }

  function ciCell(e, f = fmt) {
    if (!e) return "–";
    return [f(e.value), el("div", { className: "ci-sub" }, `${f(e.ci_low)} – ${f(e.ci_high)}`)];
  }

  function table(id, headers, rows, numeric = []) {
    const cls = (i) => (numeric.includes(i) ? "num" : undefined);
    return el("div", { className: "table-scroll" },
      el("table", { id },
        el("thead", {}, el("tr", {}, headers.map((h, i) => el("th", { className: cls(i), scope: "col" }, h)))),
        el("tbody", {}, rows.map((row) => el("tr", {}, row.map((cell, i) => el("td", { className: cls(i) }, cell)))))));
  }

  function legend() {
    return el("ul", { className: "legend" },
      el("li", {}, el("span", { className: "swatch baseline" }), t("baseline")),
      el("li", {}, el("span", { className: "swatch variant" }), t("this_run")));
  }

  /**
   * Horizontal bars, value at the end of each. rows: [label, after, before?]; before is drawn as a
   * second, grey bar above when a comparison is shown. max is the scale's end.
   */
  function bars(id, rows, format, max, paired) {
    const length = (v) => `max(0px, calc(${(v / max) * 100}% - 56px))`;
    const bar = (v, cls, label) => v === null || v === undefined
      ? el("div", { className: "bar-track" }, el("span", { className: "bar-value", style: "left: 0" }, "–"))
      : el("div", { className: "bar-track", title: `${label}: ${format(v)}` },
          el("div", { className: `bar ${cls}`, style: `width: ${length(v.value ?? v)}` }),
          el("span", { className: "bar-value", style: `left: ${length(v.value ?? v)}` }, format(v)));
    return el("div", { id, className: `bars${paired ? " paired" : ""}`, role: "group" },
      rows.map(([label, after, before]) => [
        el("div", { className: "bar-label" }, label),
        el("div", { className: "bar-pair" },
          paired ? bar(before, "baseline", `${label}, ${t("baseline")}`) : null,
          bar(after, "variant", paired ? `${label}, ${t("this_run")}` : label)),
      ]));
  }

  const scaleOf = (values) => Math.max(0, ...values.filter((v) => v !== null && v !== undefined).map((v) => v.value ?? v)) || 1;

  function lanesBlock() {
    const c = comparison?.result;
    const out = [el("h3", {}, t("utilisation_title"))];
    if (!current.lanes.length && !c?.lanes.length) return [...out, el("p", { className: "muted small" }, t("utilisation_none"))];
    out.push(el("p", { className: "muted small" }, t("utilisation_hint")));
    const share = (e) => pct(e.value);
    if (c) {
      const rows = c.lanes.map((l) => [name(l.label, l.lane_id), l.after, l.before]);
      out.push(legend(), bars("result-lanes", rows, share, Math.max(1, scaleOf(rows.flatMap(([, a, b]) => [a, b]))), true));
      const capacity = (v) => (v === null ? "–" : whole(v));
      out.push(details(table("compare-lanes",
        [t("lane"), t("capacity_baseline"), t("capacity_this_run"), t("baseline"), t("this_run")],
        c.lanes.map((l) => [name(l.label, l.lane_id), capacity(l.capacity_before), capacity(l.capacity_after), ciCell(l.before, (v) => pct(v)), ciCell(l.after, (v) => pct(v))]),
        [1, 2, 3, 4])));
    } else {
      const rows = current.lanes.map((l) => [name(l.label, l.lane_id), l.utilisation]);
      out.push(bars("result-lanes", rows, share, Math.max(1, scaleOf(rows.map(([, v]) => v))), false));
      out.push(details(table("run-lanes", [t("lane"), t("capacity"), t("utilisation")],
        current.lanes.map((l) => [name(l.label, l.lane_id), whole(l.capacity), ciCell(l.utilisation, (v) => pct(v))]), [1, 2])));
    }
    return out;
  }

  function reworkBlock() {
    const out = [el("h3", {}, t("rework_title"))];
    if (!current.rework.length) return [...out, el("p", { className: "muted small" }, t("rework_none"))];
    const before = new Map((comparison?.result ? baseline.rework : []).map((r) => [r.gateway_id, r.rate]));
    const headers = comparison?.result ? [t("gateway"), t("baseline"), t("this_run")] : [t("gateway"), t("rework_rate")];
    const rows = current.rework.map((r) => comparison?.result
      ? [name(r.label, r.gateway_id), ciCell(before.get(r.gateway_id), (v) => pct(v)), ciCell(r.rate, (v) => pct(v))]
      : [name(r.label, r.gateway_id), ciCell(r.rate, (v) => pct(v))]);
    return [...out, table("result-rework", headers, rows, comparison?.result ? [1, 2] : [1])];
  }

  function waitingBlock() {
    const c = comparison?.result;
    const out = [el("h3", {}, t("waiting_title")), el("p", { className: "muted small" }, t("waiting_hint"))];
    const daysOf = (e) => fmt(e.value);
    if (c) {
      const rows = c.activities.map((a) => [name(a.label, a.activity_id), a.after, a.before]);
      out.push(legend(), bars("result-waiting", rows, daysOf, scaleOf(rows.flatMap(([, a, b]) => [a, b])), true));
      out.push(details(table("compare-activities", [t("activity"), t("baseline"), t("this_run")],
        c.activities.map((a) => [name(a.label, a.activity_id), ciCell(a.before), ciCell(a.after)]), [1, 2])));
    } else {
      const rows = current.waiting_by_activity.map((a) => [name(a.label, a.activity_id), a.mean]);
      out.push(bars("result-waiting", rows, daysOf, scaleOf(rows.map(([, v]) => v)), false));
      out.push(details(table("run-activities", [t("activity"), t("mean_wait")],
        current.waiting_by_activity.map((a) => [name(a.label, a.activity_id), ciCell(a.mean)]), [1])));
    }
    return out;
  }

  function details(content) {
    return el("details", { className: "table-view" }, el("summary", {}, t("show_table")), content);
  }

  return { startRun, show, runChanged };
}
