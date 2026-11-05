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

Every measure takes an optional cut-off, `ends_at`, the task whose end closes a
case's cycle time (`Parameters.cycle_time_end`, from the parameter file). A
case that reaches it ends there: later tasks, and waiting for them, don't
count. A case that never reaches it ends at its end event. Without a cut-off
a case ends at its end event.
"""

from dataclasses import replace

import pandas as pd

from bpmopt.bpmn import ProcessModel
from bpmopt.flow_analysis import loop_back_flows, theoretical_cycle_time
from bpmopt.parameters import Parameters
from bpmopt.simulation import simulate


def case_ends(log: pd.DataFrame, ends_at: str | None = None) -> pd.Series:
    """When each case's cycle time ends: the first end of task `ends_at`, else the case's last event."""
    ends = log.groupby("case_id").end_time.max()
    if ends_at is not None:
        cut = log[log.activity_id == ends_at].groupby("case_id").end_time.min()
        ends.loc[cut.index] = cut
    return ends


def cycle_times(log: pd.DataFrame, ends_at: str | None = None) -> pd.Series:
    """Cycle time per case: from the moment the case starts until it ends (book §7.1), or until the cut-off."""
    return case_ends(log, ends_at) - log.groupby("case_id").ready_time.min()


def mean_cycle_time(log: pd.DataFrame, ends_at: str | None = None) -> float:
    return float(cycle_times(log, ends_at).mean())


def cycle_time_stats(log: pd.DataFrame, ends_at: str | None = None) -> dict[str, float]:
    """Mean, median and 90th percentile of the cycle time."""
    return _stats(cycle_times(log, ends_at))


def outcomes(log: pd.DataFrame) -> pd.Series:
    """The end event each case ended at, indexed by case_id. Cases that haven't ended are left out."""
    ends = log[log.element_type == "endEvent"]
    return ends.groupby("case_id").activity_id.last()


def task_runs(log: pd.DataFrame, ends_at: str | None = None) -> pd.DataFrame:
    """The task rows that fall inside the cycle time, with end_time clipped to the cut-off.

    A task that only becomes ready at or after the case's cycle time ends (e.g.
    monitoring after go-live) is left out. Without a cut-off every task row is kept.
    """
    tasks = log[log.element_type == "task"]
    if ends_at is None:
        return tasks
    ends = tasks.case_id.map(case_ends(log, ends_at))
    tasks = tasks[tasks.ready_time < ends].copy()
    tasks["end_time"] = tasks.end_time.clip(upper=ends.loc[tasks.index])
    tasks["start_time"] = tasks.start_time.clip(upper=tasks.end_time)
    return tasks


def processing_times(log: pd.DataFrame, ends_at: str | None = None) -> pd.Series:
    """Processing time per case: total length of the time during which some task of the case is in progress."""
    tasks = task_runs(log, ends_at).sort_values(["case_id", "start_time"])
    # Merge overlapping task intervals within each case: a new busy stretch starts
    # where a task starts after every earlier task of the case has ended.
    covered_until = tasks.groupby("case_id").end_time.cummax()
    previous_end = covered_until.groupby(tasks.case_id).shift()
    stretch = (tasks.start_time > previous_end).groupby(tasks.case_id).cumsum()
    stretches = tasks.groupby([tasks.case_id, stretch]).agg(start=("start_time", "min"), end=("end_time", "max"))
    busy = (stretches.end - stretches.start).groupby(level="case_id").sum()
    return busy.reindex(cycle_times(log).index, fill_value=0.0)


def waiting_times(log: pd.DataFrame, ends_at: str | None = None) -> pd.Series:
    """Waiting time per case: cycle time minus processing time."""
    return cycle_times(log, ends_at) - processing_times(log, ends_at)


def baseline_metrics(log: pd.DataFrame, model: ProcessModel, *, ends_at: str | None = None) -> dict:
    """The `baseline` section of the results, minus time_unit and the flow analysis check.

    ends_at is the cycle time cut-off (Parameters.cycle_time_end). The headline
    counts every case. by_outcome splits the cycle time by the end event each
    case ended at, most common first, so e.g. approved projects can be read
    apart from rejected proposals.
    """
    ct, pt = cycle_times(log, ends_at), processing_times(log, ends_at)
    ended_at = outcomes(log)
    by_outcome = [
        {
            "end_event_id": end_id,
            "case_count": int(len(cases)),
            "cycle_time": _stats(ct[cases]),
            "cycle_time_efficiency": _efficiency(ct[cases], pt[cases]),
        }
        for end_id in ended_at.value_counts(sort=True).index
        if len(cases := ended_at[ended_at == end_id].index)
    ]
    return {
        "cycle_time": _stats(ct),
        "processing_time": _stats(pt),
        "waiting_time": _stats(ct - pt),
        "cycle_time_efficiency": _efficiency(ct, pt),
        "by_outcome": by_outcome,
        "rework": rework_rates(log, model),
        "waiting_by_activity": waiting_by_activity(log, ends_at),
    }


def _efficiency(ct: pd.Series, pt: pd.Series) -> float:
    return float(pt.mean() / ct.mean()) if ct.mean() > 0 else 1.0


def rework_rates(log: pd.DataFrame, model: ProcessModel) -> list[dict]:
    """Per rework gateway: share of the cases reaching it that loop back at least once.

    Cases that never reach the gateway (e.g. a proposal rejected earlier) are left
    out, so the rate estimates the configured loop-back probability r: a case loops
    back at least once exactly when its first pass does.
    """
    return [
        {"gateway_id": gateway_id, "rate": float(looped.mean())}
        for gateway_id, looped in rework_flags(log, model).items()
        if len(looped)
    ]


def rework_flags(log: pd.DataFrame, model: ProcessModel) -> dict[str, pd.Series]:
    """Per rework gateway, in model order: True for each case that reached it and looped back at least once.

    Indexed by case_id, with only the cases that have a decision row at the
    gateway. Read from the XOR decision rows of the log.
    """
    decisions = log[log.element_type == "exclusiveGateway"]
    flags = {}
    for gateway_id, back_flow in loop_back_flows(model).items():
        at_gateway = decisions[decisions.activity_id == gateway_id]
        flags[gateway_id] = (at_gateway.flow_id == back_flow).groupby(at_gateway.case_id).any()
    return flags


def waiting_by_activity(log: pd.DataFrame, ends_at: str | None = None) -> list[dict]:
    """Mean waiting time (ready to start) per task execution, longest first.

    A task that runs several times in a case (rework) counts once per run.
    Tasks after the cut-off are left out, since their waiting isn't part of the
    cycle time.
    """
    tasks = task_runs(log, ends_at)
    means = (tasks.start_time - tasks.ready_time).groupby(tasks.activity_id).mean()
    means = means.sort_values(ascending=False, kind="stable")
    return [{"activity_id": activity_id, "mean": float(mean)} for activity_id, mean in means.items()]


def utilisation(log: pd.DataFrame, params: Parameters) -> dict[str, float]:
    """Per lane with a capacity: rho = arrival rate x work per case / capacity (Eq. 7.8 p.270, p.276).

    Work per case is the lane's processing time over every task row of the log,
    after the cycle time cut-off too, since those tasks also keep the lane busy.
    Needs an arrival rate: with every case arriving at time 0 there is no rate.
    """
    if params.arrival_rate is None:
        raise ValueError("utilisation needs an arrival rate: without [arrivals] every case arrives at time 0")
    tasks = log[log.element_type == "task"]
    work_per_case = (tasks.end_time - tasks.start_time).groupby(tasks.lane_id).sum() / log.case_id.nunique()
    return {lane_id: params.arrival_rate * float(work_per_case.get(lane_id, 0.0)) / c for lane_id, c in params.lane_capacities.items()}


def flow_analysis_check(model: ProcessModel, params: Parameters, *, n_cases: int, seed: int) -> dict[str, float]:
    """Book flow analysis (§7.1.1) next to the simulated mean cycle time, both with unlimited capacity.

    Flow analysis ignores resource contention (§7.1.7, p.273), so the model is
    simulated again with every lane unlimited. The two should agree within
    sampling error. Both stop at the parameters' cycle time cut-off.
    """
    unlimited = replace(params, lane_capacities={})
    log = simulate(model, unlimited, n_cases=n_cases, seed=seed)
    return {"theoretical": theoretical_cycle_time(model, params), "simulated": mean_cycle_time(log, params.cycle_time_end)}


def _stats(values: pd.Series) -> dict[str, float]:
    return {"mean": float(values.mean()), "median": float(values.median()), "p90": float(values.quantile(0.9))}
