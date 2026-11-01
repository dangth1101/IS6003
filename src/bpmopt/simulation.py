"""Discrete-event simulation of a process model, producing an event log.

Each case is a SimPy process that walks the model token by token from its
start event to an end event. The log has one row per element execution:
start and end events appear as zero-duration rows so every trace shows where
it began and how it ended.
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
    """Simulate n_cases cases and return the event log. Same seed, same log."""
    starts = model.nodes_of_type("startEvent")
    if len(starts) != 1:
        raise ValueError(f"expected exactly one start event, found {len(starts)}")

    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    rows: list[dict] = []
    # No arrival process yet: every case starts at time 0.
    for case_id in range(1, n_cases + 1):
        env.process(_run_case(env, model, params, rng, case_id, starts[0], rows))
    env.run()

    log = pd.DataFrame(rows, columns=LOG_COLUMNS)
    return log.sort_values(["case_id", "start_time"], kind="stable").reset_index(drop=True)


def _run_case(
    env: simpy.Environment,
    model: ProcessModel,
    params: Parameters,
    rng: np.random.Generator,
    case_id: int,
    start: Node,
    rows: list[dict],
) -> Generator[simpy.Event, None, None]:
    node = start
    while True:
        if node.element_type in ("startEvent", "endEvent"):
            rows.append(_row(model, case_id, node, env.now, env.now, env.now))
        elif node.element_type == "task":
            ready = env.now
            yield env.timeout(params.task_durations[node.id].sample(rng))
            rows.append(_row(model, case_id, node, ready, ready, env.now))
        else:
            raise NotImplementedError(f"{node.id}: element type {node.element_type!r} is not supported by the simulator yet")

        if node.element_type == "endEvent":
            return
        outgoing = model.outgoing(node.id)
        if len(outgoing) != 1:
            raise NotImplementedError(f"{node.id}: {len(outgoing)} outgoing flows, only sequences are supported yet")
        node = model.nodes[outgoing[0].target]


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
