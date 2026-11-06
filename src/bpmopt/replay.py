"""Replay data for the flow demo page: one simulation run of the as-is and the full to-be, cut to a time window.

Both scenarios run with the same seed, so they see the same arrivals (common
random numbers). Unlike `simulate`'s log, the replay keeps the cases that
arrived during the warm-up: they are still in flight when the window opens
and hold resources, so the page would show the queues too short without them.
Rows don't depend on later arrivals (resources serve requests first come, first
served), so every row equals the one `simulate` gives for that case and seed.
"""

import json
import math
from dataclasses import replace
from pathlib import Path

import pandas as pd

from bpmopt.analysis import case_ends
from bpmopt.bpmn import ProcessModel
from bpmopt.parameters import Parameters
from bpmopt.scenarios import Catalog
from bpmopt.simulation import simulate

DECIMALS = 2


SCENARIOS = [("as_is", "As-is", False), ("to_be", "To-be", True)]  # id, name, with every change


def build_replay(catalog: Catalog, *, seed: int, start: float, length: float) -> dict:
    """The replay of the as-is (no changes) and the full to-be (every change), for the window [start, start + length).

    Per scenario: its model's lane and task IDs (for the page layout), the cases in
    the system during the window and the task rows that overlap it. Times are in
    working days from the start of the run, rounded to DECIMALS.
    """
    end = start + length
    _, as_is = catalog.resolve([])
    scenarios = []
    for scenario_id, name, every_change in SCENARIOS:
        changes = list(catalog.ids) if every_change else []
        model, params = catalog.resolve(changes)
        log = _full_log(model, params, seed=seed, until=end)
        scenarios.append(
            {
                "id": scenario_id,
                "name": name,
                "changes": changes,
                "lanes": list(model.lanes),
                "tasks": [node.id for node in model.nodes_of_type("task")],
                "cases": _cases(log, params, start, end),
                "rows": _rows(log, start, end),
            }
        )
    return {
        "seed": seed,
        "time_unit": "working days",
        "warm_up": as_is.warm_up,
        "cycle_time_ends_at": as_is.cycle_time_end,
        "window": {"start": start, "end": end},
        "scenarios": scenarios,
    }


def write_replay(replay: dict, path: str | Path) -> Path:
    """Write the replay as compact JSON, creating the folder if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(replay, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return path


def _full_log(model: ProcessModel, params: Parameters, *, seed: int, until: float) -> pd.DataFrame:
    """Every case from time 0, warm-up included, until the first arrival after `until`."""
    if params.arrival_rate is None:
        raise ValueError("a replay needs an arrival rate")
    no_warm_up = replace(params, warm_up=0)
    n_cases = math.ceil(params.arrival_rate * until * 1.2) + 20
    while True:
        log = simulate(model, no_warm_up, n_cases=n_cases, seed=seed)
        if log.groupby("case_id").ready_time.min().max() >= until:
            return log
        n_cases *= 2


def _cases(log: pd.DataFrame, params: Parameters, start: float, end: float) -> list[dict]:
    """Cases in the system during the window: arrived before it closes, last event after it opens.

    The cycle time is filled in only for a case whose cycle time ends inside the
    window (at the parameters' cut-off, else its end event), so the page can count
    it as finished there.
    """
    arrival = log.groupby("case_id").ready_time.min()
    last = log.groupby("case_id").end_time.max()
    ends = case_ends(log, params.cycle_time_end)
    shown = arrival.index[(arrival < end) & (last > start)]
    return [
        {
            "id": int(case_id),
            "arrival": round(arrival[case_id], DECIMALS),
            "cycle_time": round(ends[case_id] - arrival[case_id], DECIMALS) if ends[case_id] < end else None,
        }
        for case_id in shown
    ]


def _rows(log: pd.DataFrame, start: float, end: float) -> list[dict]:
    tasks = log[(log.element_type == "task") & (log.ready_time < end) & (log.end_time > start)]
    return [
        {
            "case": int(r.case_id),
            "activity": r.activity_id,
            "lane": r.lane_id,
            "ready": round(r.ready_time, DECIMALS),
            "start": round(r.start_time, DECIMALS),
            "end": round(r.end_time, DECIMALS),
        }
        for r in tasks.itertuples()
    ]
