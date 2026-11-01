"""Discrete-event simulation of a process model, producing an event log.

Each case is a SimPy process that walks the model token by token from its
start event to an end event. The log has one row per element execution:
start and end events appear as zero-duration rows so every trace shows where
it began and how it ended.

Lanes with a capacity in the parameter file are resource pools: a task waits
for a free resource of its lane, so ready_time -> start_time is waiting time
and start_time -> end_time is processing time. Lanes without one are unlimited.
"""

from collections.abc import Generator

import numpy as np
import pandas as pd
import simpy

from bpmopt.bpmn import Node, ProcessModel
from bpmopt.parameters import Parameters

LOG_COLUMNS = [
    "case_id",
    "activity_id",
    "activity_label",
    "element_type",
    "lane_id",
    "lane_label",
    "ready_time",
    "start_time",
    "end_time",
]


def simulate(model: ProcessModel, params: Parameters, *, n_cases: int, seed: int) -> pd.DataFrame:
    """Simulate until n_cases cases have arrived after the warm-up and return their event log.

    Cases that arrive during the warm-up still run and hold resources, but are
    left out of the log. Case IDs count from the first case, warm-up included.
    Same seed, same log.
    """
    if n_cases < 1:
        raise ValueError(f"n_cases must be at least 1, got {n_cases}")
    starts = model.nodes_of_type("startEvent")
    if len(starts) != 1:
        raise ValueError(f"expected exactly one start event, found {len(starts)}")

    env = simpy.Environment()
    rows: list[dict] = []
    pools = {lane_id: simpy.Resource(env, capacity) for lane_id, capacity in params.lane_capacities.items()}
    arrivals = env.process(_arrivals(env, model, params, pools, n_cases, seed, starts[0], rows))
    env.run()

    log = pd.DataFrame(rows, columns=LOG_COLUMNS)
    log = log[log.case_id > arrivals.value]
    return log.sort_values(["case_id", "start_time"], kind="stable").reset_index(drop=True)


def _arrivals(
    env: simpy.Environment,
    model: ProcessModel,
    params: Parameters,
    pools: dict[str, simpy.Resource],
    n_cases: int,
    seed: int,
    start: Node,
    rows: list[dict],
) -> Generator[simpy.Event, None, int]:
    """Start one case per arrival: Poisson arrivals, or all at time 0 without a rate.

    Random streams are separate so a design change in one case doesn't shift the
    draws of the others (common random numbers): one generator for interarrival
    times, and one per case for everything drawn inside that case.

    Returns the number of warm-up cases. Arrival times only grow, so those are
    the cases with the lowest IDs.
    """
    arrival_rng = np.random.default_rng([seed, 0])
    case_id = 0
    n_warm_up = 0
    while True:
        case_id += 1
        if env.now < params.warm_up:
            n_warm_up += 1
        case_rng = np.random.default_rng([seed, 1, case_id])
        env.process(_run_case(env, model, params, case_rng, case_id, start, rows, pools))
        if case_id - n_warm_up == n_cases:
            return n_warm_up
        if params.arrival_rate is not None:
            yield env.timeout(arrival_rng.exponential(1 / params.arrival_rate))


def _run_case(
    env: simpy.Environment,
    model: ProcessModel,
    params: Parameters,
    rng: np.random.Generator,
    case_id: int,
    start: Node,
    rows: list[dict],
    pools: dict[str, simpy.Resource],
) -> Generator[simpy.Event, None, None]:
    node = start
    while True:
        if node.element_type in ("startEvent", "endEvent"):
            rows.append(_row(model, case_id, node, env.now, env.now, env.now))
        elif node.element_type == "task":
            ready = env.now
            start_time = yield from _perform_task(env, node, params, rng, pools.get(node.lane))
            rows.append(_row(model, case_id, node, ready, start_time, env.now))
        else:
            raise NotImplementedError(f"{node.id}: element type {node.element_type!r} is not supported by the simulator yet")

        if node.element_type == "endEvent":
            return
        outgoing = model.outgoing(node.id)
        if len(outgoing) != 1:
            raise NotImplementedError(f"{node.id}: {len(outgoing)} outgoing flows, only sequences are supported yet")
        node = model.nodes[outgoing[0].target]


def _perform_task(
    env: simpy.Environment,
    node: Node,
    params: Parameters,
    rng: np.random.Generator,
    pool: simpy.Resource | None,
) -> Generator[simpy.Event, None, float]:
    """Wait for a resource of the task's lane (if the lane is limited), then work. Returns the start time."""
    duration = params.task_durations[node.id].sample(rng)
    if pool is None:
        start_time = env.now
        yield env.timeout(duration)
        return start_time
    with pool.request() as request:
        yield request
        start_time = env.now
        yield env.timeout(duration)
    return start_time


def _row(model: ProcessModel, case_id: int, node: Node, ready: float, start: float, end: float) -> dict:
    return {
        "case_id": case_id,
        "activity_id": node.id,
        "activity_label": node.label,
        "element_type": node.element_type,
        "lane_id": node.lane,
        "lane_label": model.lanes.get(node.lane) if node.lane else None,
        "ready_time": ready,
        "start_time": start,
        "end_time": end,
    }
