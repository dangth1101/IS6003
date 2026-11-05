"""Simulate a design the way the scenario runner does, and compare two runs pair by pair."""

from collections.abc import Callable

import numpy as np

from bpmopt.analysis import baseline_metrics, utilisation
from bpmopt.bpmn import parse_bpmn
from bpmopt.parameters import parse_parameters
from bpmopt.scenarios import estimate, replication_seeds, saving_share
from bpmopt.simulation import simulate
from bpmopt.studio.errors import StudioError

# The run settings two runs must share for compare: only then does replication r of both
# run on the same random numbers (common random numbers).
PAIRED_ON = ("seed", "replications", "n_cases")


def simulate_summary(
    xml: str,
    params: dict,
    n_cases: int,
    seed: int,
    replications: int,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Simulate the model `replications` times and summarise where the time goes.

    Replication r runs with replication_seeds(seed, replications)[r], like the
    scenario runner. Each replication gives the measures of the report's
    baseline section (analysis.baseline_metrics) plus the utilisation per lane;
    every number below is their mean over replications with a 95% t-interval,
    an estimate {value, ci_low, ci_high}:

    - cycle_time: {mean, median, p90}, shaped like a scenario's in the results file
    - processing_time, waiting_time: {mean}
    - cycle_time_efficiency: mean processing time / mean cycle time (§7.1.2)
    - lanes: [{lane_id, label, capacity, utilisation}] per lane with a capacity,
      in model order; empty without an arrival rate (see analysis.utilisation)
    - rework: [{gateway_id, label, rate}] per rework gateway, in model order
    - waiting_by_activity: [{activity_id, label, mean}], longest wait first

    A gateway or task that fewer than 2 replications reach has no CI and is
    left out. replication_means keeps each replication's mean cycle time, so
    two runs can be paired (see compare); n_cases, seed and replications are
    returned for the same reason, and paired_on names them (PAIRED_ON).
    progress, if given, is called with (replications done, replications)
    after each one.
    """
    if replications < 2:
        raise ValueError(f"need at least 2 replications for a confidence interval, got {replications}")
    model = parse_bpmn(xml)
    parameters = parse_parameters(params, model)
    runs, rhos = [], []
    for r, replication_seed in enumerate(replication_seeds(seed, replications)):
        log = simulate(model, parameters, n_cases=n_cases, seed=replication_seed)
        runs.append(baseline_metrics(log, model, ends_at=parameters.cycle_time_end))
        rhos.append(utilisation(log, parameters) if parameters.arrival_rate is not None else {})
        if progress is not None:
            progress(r + 1, replications)

    def over_runs(values: list[float]) -> dict[str, float]:
        return estimate(np.array(values))

    lanes = [lane_id for lane_id in model.lanes if lane_id in parameters.lane_capacities and parameters.arrival_rate is not None]
    rework = _per_element([{row["gateway_id"]: row["rate"] for row in run["rework"]} for run in runs])
    waiting = _per_element([{row["activity_id"]: row["mean"] for row in run["waiting_by_activity"]} for run in runs])
    return {
        "n_cases": n_cases,
        "seed": seed,
        "replications": replications,
        "paired_on": list(PAIRED_ON),
        "cycle_time": {stat: over_runs([run["cycle_time"][stat] for run in runs]) for stat in ("mean", "median", "p90")},
        "processing_time": {"mean": over_runs([run["processing_time"]["mean"] for run in runs])},
        "waiting_time": {"mean": over_runs([run["waiting_time"]["mean"] for run in runs])},
        "cycle_time_efficiency": over_runs([run["cycle_time_efficiency"] for run in runs]),
        "lanes": [
            {
                "lane_id": lane_id,
                "label": model.lanes[lane_id],
                "capacity": parameters.lane_capacities[lane_id],
                "utilisation": over_runs([rho[lane_id] for rho in rhos]),
            }
            for lane_id in lanes
        ],
        "rework": [{"gateway_id": i, "label": model.nodes[i].label, "rate": rate} for i, rate in rework.items()],
        "waiting_by_activity": sorted(
            [{"activity_id": i, "label": model.nodes[i].label, "mean": mean} for i, mean in waiting.items()],
            key=lambda row: row["mean"]["value"],
            reverse=True,
        ),
        "replication_means": [run["cycle_time"]["mean"] for run in runs],
    }


def compare(baseline: dict, variant: dict) -> dict:
    """Compare two simulate_summary runs pair by pair: the variant's saving against the baseline.

    Refuses (StudioError "not_comparable", data settings: [{setting, baseline,
    variant}]) runs that differ in a setting of PAIRED_ON. Returns:

    - saving: baseline mean cycle time minus the variant's, paired by
      replication, with a 95% CI, like a scenario's saving in the results file
    - saving_share: that saving over the baseline mean (scenarios.saving_share)
    - baseline, variant: {cycle_time} of each run, mean / median / P90
    - lanes: [{lane_id, label, capacity_before, capacity_after, before, after}],
      before / after the utilisation estimate of each run
    - activities: [{activity_id, label, before, after}], the mean wait per run

    A lane or task only one run has gets None on the other side. Rows follow the
    baseline's order (activities longest wait first), then the variant's own.
    """
    differ = [{"setting": key, "baseline": baseline[key], "variant": variant[key]} for key in PAIRED_ON if baseline[key] != variant[key]]
    if differ:
        words = ", ".join(f"{d['setting']} {d['baseline']} vs {d['variant']}" for d in differ)
        raise StudioError("not_comparable", f"the runs can't be compared pair by pair, they differ in {words}", settings=differ)
    base_means = np.array(baseline["replication_means"])
    saving = estimate(base_means - np.array(variant["replication_means"]))
    return {
        "saving": saving,
        "saving_share": saving_share(saving, float(base_means.mean())),
        "baseline": {"cycle_time": baseline["cycle_time"]},
        "variant": {"cycle_time": variant["cycle_time"]},
        "lanes": [
            {"lane_id": i, "label": label, "capacity_before": _get(b, "capacity"), "capacity_after": _get(a, "capacity"),
             "before": _get(b, "utilisation"), "after": _get(a, "utilisation")}
            for i, label, b, a in _side_by_side(baseline["lanes"], variant["lanes"], "lane_id")
        ],
        "activities": [
            {"activity_id": i, "label": label, "before": _get(b, "mean"), "after": _get(a, "mean")}
            for i, label, b, a in _side_by_side(baseline["waiting_by_activity"], variant["waiting_by_activity"], "activity_id")
        ],
    }


def _side_by_side(before: list[dict], after: list[dict], key: str) -> list[tuple[str, str, dict | None, dict | None]]:
    """Rows of both runs matched by ID: (id, label, baseline row or None, variant row or None)."""
    b, a = {row[key]: row for row in before}, {row[key]: row for row in after}
    ids = list(dict.fromkeys([*b, *a]))
    return [(i, (b.get(i) or a[i])["label"], b.get(i), a.get(i)) for i in ids]


def _get(row: dict | None, field: str):
    return None if row is None else row[field]


def _per_element(runs: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    """Per element ID, in first-seen order: the estimate over the replications that have it (at least 2)."""
    ids = list(dict.fromkeys(i for run in runs for i in run))
    values = {i: [run[i] for run in runs if i in run] for i in ids}
    return {i: estimate(np.array(v)) for i, v in values.items() if len(v) >= 2}
