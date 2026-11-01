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

Like the book's equations, this only works for block-structured models
(§7.1.7, p.272). Anything else raises ValueError.
"""

from dataclasses import dataclass

from bpmopt.bpmn import Flow, Node, ProcessModel
from bpmopt.parameters import Parameters


def theoretical_cycle_time(model: ProcessModel, params: Parameters) -> float:
    """Mean cycle time of a case, from task mean durations and branching probabilities."""
    starts = model.nodes_of_type("startEvent")
    if len(starts) != 1:
        raise ValueError(f"expected exactly one start event, found {len(starts)}")
    ct, stop = _Reducer(model, params).fragment(_single_outgoing(model, starts[0]))
    if model.nodes[stop.target].element_type != "endEvent":
        raise ValueError(f"{stop.target}: join without a matching split, the model is not block-structured")
    return ct


class _Reducer:
    def __init__(self, model: ProcessModel, params: Parameters):
        self.model = model
        self.params = params
        self.loops = _find_loops(model)  # loop split ID -> loop
        self.loop_joins = {loop.join for loop in self.loops.values()}

    def fragment(self, flow: Flow) -> tuple[float, Flow]:
        """CT of the fragment entered by `flow`, up to the first join or end event.

        Returns the CT and the flow that leaves the fragment (into that join or end event).
        """
        ct = 0.0
        while True:
            node = self.model.nodes[flow.target]
            if node.id in self.loop_joins:
                loop_ct, flow = self.rework(node)
                ct += loop_ct
                continue
            if node.element_type == "endEvent" or _is_join(self.model, node) or node.id in self.loops:
                return ct, flow
            if node.element_type == "task":
                ct += self.params.task_durations[node.id].mean
                flow = _single_outgoing(self.model, node)
            elif _is_split(self.model, node):
                block_ct, flow = self.block(node)
                ct += block_ct
            else:
                raise ValueError(f"{node.id}: element type {node.element_type!r} is not supported by flow analysis")

    def block(self, split: Node) -> tuple[float, Flow]:
        """CT of the block opened by `split`, and the flow that leaves its join."""
        branches = [(flow, *self.fragment(flow)) for flow in self.model.outgoing(split.id)]
        joins = {exit_flow.target for _, _, exit_flow in branches}
        join = self.model.nodes[joins.pop()] if len(joins) == 1 else None
        if join is None or join.element_type != split.element_type or not _is_join(self.model, join):
            raise ValueError(f"{split.id}: branches don't meet at one join of the same type, the model is not block-structured")
        if split.element_type == "exclusiveGateway":
            probabilities = self.params.branch_probabilities[split.id]
            ct = sum(probabilities[flow.id] * branch_ct for flow, branch_ct, _ in branches)
        elif split.element_type == "parallelGateway":
            ct = max(branch_ct for _, branch_ct, _ in branches)
        else:
            raise ValueError(f"{split.id}: gateway type {split.element_type!r} is not supported by flow analysis")
        return ct, _single_outgoing(self.model, join)

    def rework(self, join: Node) -> tuple[float, Flow]:
        """CT of the rework block entered at `join`, and its exit flow."""
        body_ct, into_split = self.fragment(_single_outgoing(self.model, join))
        loop = self.loops.get(into_split.target)
        if loop is None or loop.join != join.id:
            raise ValueError(f"{join.id}: loop body doesn't end at the split that loops back to it")
        exits = [f for f in self.model.outgoing(loop.split) if f.id != loop.back.id]
        if len(exits) != 1:
            raise ValueError(f"{loop.split}: a rework split needs exactly one exit arc, found {len(exits)}")
        r = self.params.branch_probabilities[loop.split][loop.back.id]
        if r >= 1:
            raise ValueError(f"{loop.split}: rework probability {r} never leaves the loop")
        back_ct = sum(self.params.task_durations[task].mean for task in loop.back_tasks)
        return (body_ct + r * back_ct) / (1 - r), exits[0]


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
