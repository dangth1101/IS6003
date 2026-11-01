"""Discrete-event simulation of a process model, producing an event log.

Each case is a SimPy process that walks the model token by token from its
start event to an end event. An XOR-split sends the token down one branch,
drawn with the branching probabilities from the parameter file. An AND-split
runs one token per branch at the same time and continues once all of them
reach the AND-join. A rework loop is just an XOR-split whose branch leads back
to an earlier XOR-join. The log has one row per element execution:
start and end events appear as zero-duration rows so every trace shows where
it began and how it ended. Each XOR-split decision is a zero-duration row too,
with the outgoing flow taken in flow_id, so rework can be read straight from
the log. XOR-joins, AND gateways and other rows leave flow_id empty.

Lanes with a capacity in the parameter file are resource pools: a task waits
for a free resource of its lane, so ready_time -> start_time is waiting time
and start_time -> end_time is processing time. Lanes without one are unlimited.

Each case draws its attributes (project type, complexity, ...) once when it
arrives. They are repeated on every log row of the case, as extra columns after
LOG_COLUMNS, and XOR-splits with logistic branches read them.
"""

import zlib
from collections.abc import Generator
from dataclasses import dataclass

import numpy as np
import pandas as pd
import simpy

from bpmopt.bpmn import Flow, Node, ProcessModel
from bpmopt.parameters import AttributeValue, Parameters, check_parameters

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
    "flow_id",
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
    check_parameters(params, model)

    env = simpy.Environment()
    rows: list[dict] = []
    pools = {lane_id: simpy.Resource(env, capacity) for lane_id, capacity in params.lane_capacities.items()}
    arrivals = env.process(_arrivals(env, model, params, pools, n_cases, seed, starts[0], rows))
    env.run()

    log = pd.DataFrame(rows, columns=[*LOG_COLUMNS, *params.attributes])
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
    times, one per case and task for durations, one per case and XOR-split
    for branch choices (see _Streams), and one per case and attribute.

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
        case = _Case(
            env,
            model,
            params,
            case_id,
            durations=_Streams(seed, 1, case_id),
            branches=_BranchDraws(seed, case_id),
            attributes=_draw_attributes(params, seed, case_id),
            rows=rows,
            pools=pools,
        )
        env.process(_run_case(case, start))
        if case_id - n_warm_up == n_cases:
            return n_warm_up
        if params.arrival_rate is not None:
            yield env.timeout(arrival_rng.exponential(1 / params.arrival_rate))


@dataclass
class _Case:
    """One case in flight: what its tokens need to move through the model."""

    env: simpy.Environment
    model: ProcessModel
    params: Parameters
    case_id: int
    durations: "_Streams"  # one stream per task
    branches: "_BranchDraws"
    attributes: dict[str, AttributeValue]  # drawn at arrival, repeated on every log row
    rows: list[dict]
    pools: dict[str, simpy.Resource]


def _run_case(case: _Case, start: Node) -> Generator[simpy.Event, None, None]:
    join = yield from _move_token(case, start)
    if join is not None:
        raise ValueError(f"{join.id}: AND-join reached without a matching AND-split")


def _move_token(case: _Case, node: Node) -> Generator[simpy.Event, object, Node | None]:
    """Move one token from node until it reaches an end event or an AND-join.

    Returns None at an end event, or the AND-join, where the AND-split that
    created this token picks it up. XOR-joins just pass the token on, which is
    all a rework loop needs. AND-blocks must be structured: the branches of one
    AND-split all end at the same AND-join (7PMG G4).
    """
    env, model = case.env, case.model
    while True:
        incoming, outgoing = model.incoming(node.id), model.outgoing(node.id)
        if node.element_type in ("startEvent", "endEvent"):
            case.rows.append(_row(case, node, env.now, env.now, env.now))
            if node.element_type == "endEvent":
                return None
        elif node.element_type == "task":
            ready = env.now
            start_time = yield from _perform_task(env, node, case.params, case.durations[node.id], case.pools.get(node.lane))
            case.rows.append(_row(case, node, ready, start_time, env.now))
        elif node.element_type == "exclusiveGateway" and len(outgoing) > 1:
            flow = case.branches.choose(node.id, outgoing, case.params, case.attributes)
            case.rows.append(_row(case, node, env.now, env.now, env.now, flow_id=flow.id))
            node = model.nodes[flow.target]
            continue
        elif node.element_type == "parallelGateway" and len(incoming) > 1 and len(outgoing) == 1:
            return node
        elif node.element_type == "parallelGateway" and len(outgoing) > 1 and len(incoming) == 1:
            branches = [env.process(_move_token(case, model.nodes[flow.target])) for flow in outgoing]
            yield env.all_of(branches)
            joins = {branch.value for branch in branches}
            if len(joins) != 1 or None in joins:
                raise ValueError(f"{node.id}: branches of an AND-split must all end at one AND-join")
            node = joins.pop()
            outgoing = model.outgoing(node.id)
        elif node.element_type not in ("exclusiveGateway", "parallelGateway"):
            raise NotImplementedError(f"{node.id}: element type {node.element_type!r} is not supported by the simulator")

        if len(outgoing) != 1:
            raise ValueError(f"{node.id}: expected one outgoing flow, found {len(outgoing)}")
        node = model.nodes[outgoing[0].target]


class _Streams:
    """Random streams of one case, one per element (task or XOR-split), made on first use.

    Keyed by element ID, not by draw order, so adding or removing a task or a
    gateway elsewhere doesn't change what this case draws for the others. That
    keeps common random numbers between designs (ticket 13). A task that runs
    again in a rework loop takes the next draw from its own stream.
    """

    def __init__(self, seed: int, kind: int, case_id: int):
        self._key = [seed, kind, case_id]
        self._rngs: dict[str, np.random.Generator] = {}

    def __getitem__(self, element_id: str) -> np.random.Generator:
        if element_id not in self._rngs:
            self._rngs[element_id] = np.random.default_rng([*self._key, zlib.crc32(element_id.encode())])
        return self._rngs[element_id]


class _BranchDraws:
    """Branch choices of one case, with one random stream per XOR-split.

    Each choice uses one uniform draw against the cumulative probabilities, so a
    small change in a probability only flips the cases near the boundary.
    """

    def __init__(self, seed: int, case_id: int):
        self._streams = _Streams(seed, 2, case_id)

    def choose(self, gateway_id: str, outgoing: list[Flow], params: Parameters, attributes: dict[str, AttributeValue]) -> Flow:
        """Pick an outgoing flow of the XOR-split.

        Probabilities can depend on the case attributes (logistic branches).
        """
        probabilities = params.branch_probabilities[gateway_id].probabilities(attributes)
        u = self._streams[gateway_id].random()
        cumulative = 0.0
        for flow in outgoing:
            cumulative += probabilities[flow.id]
            if u < cumulative:
                return flow
        return outgoing[-1]  # u fell in the rounding gap just below 1


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


def _draw_attributes(params: Parameters, seed: int, case_id: int) -> dict[str, AttributeValue]:
    """One stream per case and attribute, keyed by name, so adding an attribute doesn't change the others."""
    return {
        name: distribution.sample(np.random.default_rng([seed, 3, case_id, zlib.crc32(name.encode())]))
        for name, distribution in params.attributes.items()
    }


def _row(case: _Case, node: Node, ready: float, start: float, end: float, flow_id: str | None = None) -> dict:
    model = case.model
    return {
        "case_id": case.case_id,
        "activity_id": node.id,
        "activity_label": node.label,
        "element_type": node.element_type,
        "lane_id": node.lane,
        "lane_label": model.lanes.get(node.lane) if node.lane else None,
        "ready_time": ready,
        "start_time": start,
        "end_time": end,
        "flow_id": flow_id,
        **case.attributes,
    }
