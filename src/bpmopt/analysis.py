"""Performance measures computed from an event log (book Ch. 7, §11.5).

Per case:

- cycle time: from the moment the case starts until it ends (§7.1).
- processing time: time during which at least one task of the case is being
  worked on. Tasks of an AND-block that run at the same time count once, so
  this is the log's version of the theoretical cycle time (TCT, p.262), which
  also takes the max over AND branches.
- waiting time: the rest of the cycle time, "the portion of the cycle time
  where no work is being done to advance the process" (p.261).

Cycle time efficiency is mean processing time / mean cycle time, the book's
CTE = TCT / CT (7.5) with both terms averaged over cases.
"""

from dataclasses import replace

import pandas as pd

from bpmopt.bpmn import ProcessModel
from bpmopt.flow_analysis import loop_back_flows, theoretical_cycle_time
from bpmopt.parameters import Parameters
from bpmopt.simulation import simulate


def cycle_times(log: pd.DataFrame) -> pd.Series:
    """Cycle time per case: from the moment the case starts until it ends (book §7.1)."""
    by_case = log.groupby("case_id")
    return by_case.end_time.max() - by_case.ready_time.min()


def mean_cycle_time(log: pd.DataFrame) -> float:
    return float(cycle_times(log).mean())


def cycle_time_stats(log: pd.DataFrame) -> dict[str, float]:
    """Mean, median and 90th percentile of the cycle time."""
    return _stats(cycle_times(log))


def processing_times(log: pd.DataFrame) -> pd.Series:
    """Processing time per case: total length of the time during which some task of the case is in progress."""
    tasks = log[log.element_type == "task"].sort_values(["case_id", "start_time"])
    # Merge overlapping task intervals within each case: a new busy stretch starts
    # where a task starts after every earlier task of the case has ended.
    covered_until = tasks.groupby("case_id").end_time.cummax()
    previous_end = covered_until.groupby(tasks.case_id).shift()
    stretch = (tasks.start_time > previous_end).groupby(tasks.case_id).cumsum()
    stretches = tasks.groupby([tasks.case_id, stretch]).agg(start=("start_time", "min"), end=("end_time", "max"))
    busy = (stretches.end - stretches.start).groupby(level="case_id").sum()
    return busy.reindex(cycle_times(log).index, fill_value=0.0)


def waiting_times(log: pd.DataFrame) -> pd.Series:
    """Waiting time per case: cycle time minus processing time."""
    return cycle_times(log) - processing_times(log)


def baseline_metrics(log: pd.DataFrame, model: ProcessModel) -> dict:
    """The `baseline` section of the results, minus time_unit and the flow analysis check."""
    ct, pt = cycle_times(log), processing_times(log)
    return {
        "cycle_time": _stats(ct),
        "processing_time": _stats(pt),
        "waiting_time": _stats(ct - pt),
        "cycle_time_efficiency": float(pt.mean() / ct.mean()) if ct.mean() > 0 else 1.0,
        "rework": rework_rates(log, model),
        "waiting_by_activity": waiting_by_activity(log),
    }


def rework_rates(log: pd.DataFrame, model: ProcessModel) -> list[dict]:
    """Per rework gateway: share of the cases reaching it that loop back at least once.

    Cases that never reach the gateway (e.g. a proposal rejected earlier) are left
    out, so the rate estimates the configured loop-back probability r: a case loops
    back at least once exactly when its first pass does. Read from the XOR decision
    rows of the log.
    """
    decisions = log[log.element_type == "exclusiveGateway"]
    rates = []
    for gateway_id, back_flow in loop_back_flows(model).items():
        at_gateway = decisions[decisions.activity_id == gateway_id]
        looped = (at_gateway.flow_id == back_flow).groupby(at_gateway.case_id).any()
        if len(looped):
            rates.append({"gateway_id": gateway_id, "rate": float(looped.mean())})
    return rates


def waiting_by_activity(log: pd.DataFrame) -> list[dict]:
    """Mean waiting time (ready to start) per task execution, longest first.

    A task that runs several times in a case (rework) counts once per run.
    """
    tasks = log[log.element_type == "task"]
    means = (tasks.start_time - tasks.ready_time).groupby(tasks.activity_id).mean()
    means = means.sort_values(ascending=False, kind="stable")
    return [{"activity_id": activity_id, "mean": float(mean)} for activity_id, mean in means.items()]


def flow_analysis_check(model: ProcessModel, params: Parameters, *, n_cases: int, seed: int) -> dict[str, float]:
    """Book flow analysis (§7.1.1) next to the simulated mean cycle time, both with unlimited capacity.

    Flow analysis ignores resource contention (§7.1.7, p.273), so the model is
    simulated again with every lane unlimited. The two should agree within
    sampling error.
    """
    unlimited = replace(params, lane_capacities={})
    log = simulate(model, unlimited, n_cases=n_cases, seed=seed)
    return {"theoretical": theoretical_cycle_time(model, params), "simulated": mean_cycle_time(log)}


def _stats(values: pd.Series) -> dict[str, float]:
    return {"mean": float(values.mean()), "median": float(values.median()), "p90": float(values.quantile(0.9))}
