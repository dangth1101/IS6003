"""Flow analysis: theoretical cycle time from the process model (book §7.1.1).

The model is reduced block by block with the book's formulas:

- sequence: CT = sum of the CTs (7.1)
- XOR-block: CT = sum of p_i x CT_i (7.2)
- AND-block: CT = max of the CT_i (7.3)
- rework block: CT = T / (1 - r) (7.4), where T is the CT of the loop body

A rework block (Fig. 7.8, p.260) is an XOR-join, a body, and an XOR-split with
an exit arc and a loop-back arc to the join. In the book the loop-back arc is
always empty. We also allow tasks on it. That case is our own derivation, not
the book's: from the same geometric series (p.259) the body runs 1/(1 - r)
times and the loop-back tasks r/(1 - r) times, so CT = (T + r x R) / (1 - r),
with R the summed CT of the loop-back tasks. R = 0 gives the book's formula.

Early end events are also our own derivation. In the book every block ends in
a join, but a model with one end event per outcome (7PMG G3) has XOR branches
that end the case, such as "Proposal rejected". The CT stays the mean over all
cases, the book's definition (p.256), so a case that ends early counts with
the time it took up to its end. A case that has ended spends no more time, so
every fragment after a possible early end is weighted by the probability that
the case is still running, the same weighting as the XOR formula (7.2). A
model with several end events on exclusive paths has the same CT as the model
with those paths merged by an XOR-join in front of one end event, so this
stays within (7.1)-(7.4). In a rework split with an extra branch to an end
event, leaving the loop is an XOR-split of its own over the arcs that don't
loop back, with probabilities divided by 1 - r.

Branch probabilities that depend on case attributes (logistic branches) are
our extension too. The book's probabilities are fixed. Once a case's
attributes are known its probabilities are fixed, so the formulas hold per
attribute vector, and the process CT is their mean over the attribute
distributions in the parameter file. That mean is estimated from a fixed
number of attribute draws with a fixed seed, so it is reproducible. Putting
the mean probability into the formulas instead would be wrong: 1 / (1 - r) is
convex, so it would underestimate rework (Jensen's inequality). A duration
that scales with the attributes goes in with its mean for the drawn case,
since a case with long test rounds may also fail more often. With only fixed
splits nothing is drawn, scaled durations go in with their mean over the
attribute distributions (exact, since the scale is linear), and the result is
the plain formula.

Like the book's equations, this only works for block-structured models
(§7.1.7, p.272). Anything else raises ValueError.
"""

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from bpmopt.bpmn import Flow, Node, ProcessModel
from bpmopt.parameters import AttributeValue, Parameters, ScaledDuration


def theoretical_cycle_time(model: ProcessModel, params: Parameters, *, n_draws: int = 5_000, seed: int = 0) -> float:
    """Mean cycle time of a case, from task mean durations and branching probabilities.

    With logistic branches, the mean over n_draws attribute vectors drawn with
    `seed` (see the module docstring). With fixed branches both are ignored.
    """
    starts = model.nodes_of_type("startEvent")
    if len(starts) != 1:
        raise ValueError(f"expected exactly one start event, found {len(starts)}")
    reducer = _Reducer(model, params)
    first = _single_outgoing(model, starts[0])
    if not any(branches.depends_on_attributes for branches in params.branch_probabilities.values()):
        return reducer.cycle_time(first, {})
    rng = np.random.default_rng(seed)
    draws = [{name: d.sample(rng) for name, d in params.attributes.items()} for _ in range(n_draws)]
    return float(np.mean([reducer.cycle_time(first, attributes) for attributes in draws]))


class _Reducer:
    """Each step returns (CT, exit flow, probability of reaching the exit flow).

    The CT counts cases that end early only up to their end event. The exit flow
    is None when every case ends inside the fragment.
    """

    def __init__(self, model: ProcessModel, params: Parameters):
        self.model = model
        self.params = params
        self.loops = _find_loops(model)  # loop split ID -> loop
        self.loop_joins = {loop.join for loop in self.loops.values()}
        self.attributes: Mapping[str, AttributeValue] = {}

    def cycle_time(self, first: Flow, attributes: Mapping[str, AttributeValue]) -> float:
        """CT of a case with these attributes, from the start event's outgoing flow."""
        self.attributes = attributes
        ct, stop, _ = self.fragment(first)
        if stop is not None and not _is_end(self.model, stop):
            raise ValueError(f"{stop.target}: join without a matching split, the model is not block-structured")
        return ct

    def probabilities(self, split_id: str) -> dict[str, float]:
        return self.params.branch_probabilities[split_id].probabilities(self.attributes)

    def task_mean(self, task_id: str) -> float:
        """Mean duration of the task, for this case's attributes when it scales with them."""
        duration = self.params.task_durations[task_id]
        if isinstance(duration, ScaledDuration) and self.attributes:
            return duration.mean_given(self.attributes)
        return duration.mean

    def fragment(self, flow: Flow) -> tuple[float, Flow | None, float]:
        """The fragment entered by `flow`, up to the first join or end event."""
        ct, p = 0.0, 1.0
        while True:
            node = self.model.nodes[flow.target]
            if node.id in self.loop_joins:
                part_ct, flow, part_p = self.rework(node)
            elif node.element_type == "endEvent" or _is_join(self.model, node) or node.id in self.loops:
                return ct, flow, p
            elif node.element_type == "task":
                part_ct, flow, part_p = self.task_mean(node.id), _single_outgoing(self.model, node), 1.0
            elif _is_split(self.model, node):
                probabilities = self.probabilities(node.id) if node.element_type == "exclusiveGateway" else None
                part_ct, flow, part_p = self.block(node, self.model.outgoing(node.id), probabilities)
            else:
                raise ValueError(f"{node.id}: element type {node.element_type!r} is not supported by flow analysis")
            ct += p * part_ct
            p *= part_p
            if flow is None:
                return ct, None, 0.0

    def block(self, split: Node, flows: list[Flow], probabilities: dict[str, float] | None) -> tuple[float, Flow | None, float]:
        """The block opened by `split` over `flows`, up to and including its join."""
        branches = [(flow, *self.fragment(flow)) for flow in flows]
        going_on = [b for b in branches if b[2] is not None and not _is_end(self.model, b[2])]
        if split.element_type == "parallelGateway":
            if len(going_on) < len(branches) or any(p < 1 for *_, p in branches):
                raise ValueError(f"{split.id}: a branch of an AND-block can't end the case on its own")
            join = self._join(split, going_on)
            return max(ct for _, ct, _, _ in branches), _single_outgoing(self.model, join), 1.0
        if split.element_type != "exclusiveGateway":
            raise ValueError(f"{split.id}: gateway type {split.element_type!r} is not supported by flow analysis")

        ct = sum(probabilities[flow.id] * branch_ct for flow, branch_ct, _, _ in branches)
        p = sum(probabilities[flow.id] * branch_p for flow, _, _, branch_p in going_on)
        if not going_on:
            return ct, None, 0.0
        if len(going_on) == 1:
            # The other branches all end the case, so this split has no join of its own.
            # Its one remaining branch runs on into a join of an enclosing block.
            return ct, going_on[0][2], p
        return ct, _single_outgoing(self.model, self._join(split, going_on)), p

    def _join(self, split: Node, going_on: list[tuple]) -> Node:
        """The join where the branches of `split` that don't end the case meet. They must be all its inputs."""
        joins = {exit_flow.target for _, _, exit_flow, _ in going_on}
        join = self.model.nodes[joins.pop()] if len(joins) == 1 else None
        if (
            join is None
            or join.element_type != split.element_type
            or len(self.model.incoming(join.id)) != len(going_on)
        ):
            raise ValueError(f"{split.id}: branches don't meet at one join of the same type, the model is not block-structured")
        return join

    def rework(self, join: Node) -> tuple[float, Flow | None, float]:
        """The rework block entered at `join`, up to its exit."""
        body_ct, into_split, body_p = self.fragment(_single_outgoing(self.model, join))
        loop = self.loops.get(into_split.target) if into_split is not None else None
        if loop is None or loop.join != join.id:
            raise ValueError(f"{join.id}: loop body doesn't end at the split that loops back to it")
        probabilities = self.probabilities(loop.split)
        r = probabilities[loop.back.id]
        if r >= 1:
            raise ValueError(f"{loop.split}: rework probability {r} never leaves the loop")
        exits = [f for f in self.model.outgoing(loop.split) if f.id != loop.back.id]
        if not exits:
            raise ValueError(f"{loop.split}: a rework split needs an exit arc")
        # With body_p = 1 this is (T + r x R) / (1 - r), see the module docstring.
        loops_back = body_p * r
        back_ct = sum(self.task_mean(task) for task in loop.back_tasks)
        ct = (body_ct + loops_back * back_ct) / (1 - loops_back)
        leaves = body_p * (1 - r) / (1 - loops_back)
        if len(exits) == 1:
            return ct, exits[0], leaves
        exit_ct, exit_flow, exit_p = self.block(
            self.model.nodes[loop.split], exits, {f.id: probabilities[f.id] / (1 - r) for f in exits}
        )
        return ct + leaves * exit_ct, exit_flow, leaves * exit_p


def loop_back_flows(model: ProcessModel) -> dict[str, str]:
    """Rework XOR-splits of the model: split ID -> ID of its outgoing flow that loops back."""
    return {split: loop.back.id for split, loop in _find_loops(model).items()}


@dataclass(frozen=True)
class _Loop:
    split: str  # XOR-split that decides on rework
    back: Flow  # its outgoing flow that starts the loop-back arc
    back_tasks: tuple[str, ...]  # tasks on the loop-back arc (empty in every book example)
    join: str  # XOR-join the loop-back arc returns to


def _find_loops(model: ProcessModel) -> dict[str, _Loop]:
    """Rework blocks, found from the back edges of a depth-first search from the start event."""
    back_edges: list[Flow] = []
    on_path: set[str] = set()
    done: set[str] = set()

    def visit(node_id: str) -> None:
        on_path.add(node_id)
        for flow in model.outgoing(node_id):
            if flow.target in on_path:
                back_edges.append(flow)
            elif flow.target not in done:
                visit(flow.target)
        on_path.remove(node_id)
        done.add(node_id)

    for start in model.nodes_of_type("startEvent"):
        visit(start.id)

    loops = {}
    for edge in back_edges:
        # Walk the loop-back arc backwards, over its tasks, to the split that starts it.
        flow, back_tasks = edge, []
        while model.nodes[flow.source].element_type == "task":
            back_tasks.insert(0, flow.source)
            (flow,) = model.incoming(flow.source)
        split = model.nodes[flow.source]
        if split.element_type != "exclusiveGateway" or model.nodes[edge.target].element_type != "exclusiveGateway":
            raise ValueError(f"{edge.id}: a cycle must be a rework block between an XOR-join and an XOR-split")
        loops[split.id] = _Loop(split.id, flow, tuple(back_tasks), edge.target)
    return loops


def _is_split(model: ProcessModel, node: Node) -> bool:
    return node.element_type.endswith("Gateway") and len(model.outgoing(node.id)) > 1


def _is_join(model: ProcessModel, node: Node) -> bool:
    return node.element_type.endswith("Gateway") and len(model.incoming(node.id)) > 1


def _single_outgoing(model: ProcessModel, node: Node) -> Flow:
    outgoing = model.outgoing(node.id)
    if len(outgoing) != 1:
        raise ValueError(f"{node.id}: expected one outgoing flow, found {len(outgoing)}")
    return outgoing[0]


def _is_end(model: ProcessModel, flow: Flow) -> bool:
    return model.nodes[flow.target].element_type == "endEvent"
