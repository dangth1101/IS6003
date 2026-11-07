"""Handover of work between lanes and their betweenness (bpmopt.social)."""

import pandas as pd
import pytest

from bpmopt.social import betweenness, centrality, handovers, network, social_section


def _log(cases: dict[int, list[tuple[str, str]]]) -> pd.DataFrame:
    """A log of (element type, lane) rows per case, in order."""
    rows = [{"case_id": c, "element_type": t, "lane_id": lane} for c, steps in cases.items() for t, lane in steps]
    return pd.DataFrame(rows)


def test_a_handover_is_the_next_task_in_another_lane_and_gateways_do_not_count():
    log = _log({
        1: [("task", "A"), ("exclusiveGateway", "C"), ("task", "B"), ("task", "B"), ("task", "C")],
        2: [("task", "A"), ("task", "B")],
    })

    edges = handovers(log)

    assert edges.to_dict("records") == [
        {"source": "A", "target": "B", "count": 2},
        {"source": "B", "target": "C", "count": 1},
    ]


def test_the_middle_of_a_chain_is_on_the_only_path_between_the_ends():
    # A -> B -> C: of the two ordered pairs that don't involve B (A to C, C to A), B is on the one path there is.
    scores = betweenness(network(pd.DataFrame({"source": ["A", "B"], "target": ["B", "C"], "count": [5, 5]})))

    assert scores == pytest.approx({"A": 0.0, "B": 0.5, "C": 0.0})


def test_a_stronger_tie_is_a_shorter_path():
    # A reaches D through B (strong ties) or C (weak ties); only B is on the shortest path.
    edges = pd.DataFrame({"source": ["A", "B", "A", "C"], "target": ["B", "D", "C", "D"], "count": [100, 100, 1, 1]})

    scores = betweenness(network(edges))

    assert scores["B"] > 0
    assert scores["C"] == 0


def test_the_section_ranks_every_lane_by_betweenness():
    log = _log({1: [("task", "A"), ("task", "B"), ("task", "C")], 2: [("task", "A"), ("task", "B"), ("task", "C")]})

    section = social_section(log)

    # B is the broker; A and C broker nothing, and work flows to C, so its PageRank breaks the tie
    assert [row["lane_id"] for row in section["centrality"]] == ["B", "C", "A"]
    assert section["centrality"][0]["betweenness"] == pytest.approx(0.5)


def test_centrality_of_a_chain():
    # A -> B -> C, twice. B works with both others; A reaches B in one hop and C in two; C reaches nobody.
    rows = {r["lane_id"]: r for r in centrality(network(pd.DataFrame({"source": ["A", "B"], "target": ["B", "C"], "count": [2, 2]})))}

    assert {lane: r["degree"] for lane, r in rows.items()} == pytest.approx({"A": 0.5, "B": 1.0, "C": 0.5})
    assert (rows["B"]["in_handovers"], rows["B"]["out_handovers"]) == (2, 2)
    assert (rows["A"]["in_handovers"], rows["C"]["out_handovers"]) == (0, 0)
    assert rows["A"]["closeness"] == pytest.approx(2 / 3)  # (n - 1) / (1 + 2) hops
    assert rows["C"]["closeness"] == 0
    assert sum(r["pagerank"] for r in rows.values()) == pytest.approx(1)
    assert rows["C"]["pagerank"] > rows["A"]["pagerank"]  # work flows to the end of the chain
