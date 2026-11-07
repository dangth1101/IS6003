"""Case groups (graph2vec) and activity groups (node2vec) from an event log, and their place in the results file."""

import json
from pathlib import Path

import jsonschema
import pandas as pd
import pytest

from bpmopt.bpmn import read_bpmn
from bpmopt.clustering import case_graphs, clusters_section, follows_graph
from bpmopt.flow_analysis import loop_back_flows
from bpmopt.parameters import load_parameters
from bpmopt.results import build_results, export_results, validate_results
from bpmopt.simulation import simulate

FIXTURES = Path(__file__).parent / "fixtures"
MODEL = FIXTURES / "proposal_rejected.bpmn"


@pytest.fixture(scope="module")
def model():
    return read_bpmn(MODEL)


@pytest.fixture(scope="module")
def params(model):
    return load_parameters(FIXTURES / "proposal_rejected.ml.params.toml")


@pytest.fixture(scope="module")
def log(model, params):
    return simulate(model, params, n_cases=400, seed=7)


@pytest.fixture(scope="module")
def section(log, model):
    return clusters_section(log, model, seed=7)


def test_each_case_is_a_chain_of_its_events_with_the_branch_taken_at_each_gateway(log):
    graphs = case_graphs(log)
    case_id = log.case_id.iloc[0]
    events = log[log.case_id == case_id]
    labels, edges = graphs[case_id]

    assert len(graphs) == log.case_id.nunique()
    assert len(labels) == len(events)
    assert edges == [(i, i + 1) for i in range(len(labels) - 1)]
    for label, row in zip(labels, events.itertuples(), strict=True):
        expected = f"{row.activity_id}>{row.flow_id}" if row.element_type == "exclusiveGateway" else row.activity_id
        assert label == expected


def test_the_follows_graph_counts_how_often_one_activity_directly_follows_another():
    log = pd.DataFrame({"case_id": [1, 1, 1, 2, 2], "activity_id": ["a", "b", "c", "a", "b"]})

    activities, edges = follows_graph(log)

    assert activities == ["a", "b", "c"]
    assert sorted(edges) == [(0, 1, 2.0), (1, 2, 1.0)]


def test_case_groups_cover_every_case_once(section, log):
    cases = section["cases"]

    assert sum(g["case_count"] for g in cases["groups"]) == log.case_id.nunique()
    assert sorted(p["case_id"] for p in cases["points"]) == sorted(log.case_id.unique())
    assert cases["k"] == len(cases["groups"])


def test_case_groups_are_numbered_by_size_largest_first(section):
    sizes = [g["case_count"] for g in section["cases"]["groups"]]

    assert sizes == sorted(sizes, reverse=True)


def test_activity_groups_are_numbered_in_process_order(section, log):
    first_seen = list(dict.fromkeys(log.activity_id))
    starts = [min(first_seen.index(a) for a in g["activity_ids"]) for g in section["activities"]["groups"]]

    assert starts == sorted(starts)
    assert first_seen[0] in section["activities"]["groups"][0]["activity_ids"]


def test_k_is_the_one_with_the_best_silhouette(section):
    for name in ("cases", "activities"):
        best = max(section[name]["silhouette"], key=lambda row: row["silhouette"])
        assert section[name]["k"] == best["k"]


def test_each_case_group_reports_loops_at_every_rework_gateway(section, model):
    for g in section["cases"]["groups"]:
        assert [loop["gateway_id"] for loop in g["loops"]] == list(loop_back_flows(model))


def test_each_case_group_names_its_most_common_path(section, log):
    graphs = case_graphs(log)
    points = section["cases"]["points"]
    for g in section["cases"]["groups"]:
        members = [p["case_id"] for p in points if p["group"] == g["id"]]
        taking = sum(graphs[c][0] == g["path"]["labels"] for c in members)
        assert taking == round(g["path"]["share"] * len(members))
        assert all(taking >= sum(graphs[c][0] == graphs[o][0] for c in members) for o in members)


def test_the_top_paths_are_the_most_common_ones_with_their_counts(section, log):
    from collections import Counter

    taken = Counter(tuple(nodes) for nodes, _ in case_graphs(log).values())
    paths = section["cases"]["paths"]

    assert section["cases"]["path_count"] == len(taken)
    assert [p["case_count"] for p in paths] == sorted((n for _, n in taken.most_common(len(paths))), reverse=True)
    for p in paths:
        assert taken[tuple(p["labels"])] == p["case_count"]


def test_the_follows_edges_add_up_to_every_step_of_every_case(section, log):
    edges = section["activities"]["edges"]
    steps = len(log) - log.case_id.nunique()  # one step between each pair of events in a case
    repeats = (log.activity_id == log.groupby("case_id").activity_id.shift(-1)).sum()

    assert sum(e["count"] for e in edges) == steps - repeats


def test_activity_groups_cover_every_activity_in_the_log_once(section, log):
    grouped = [a for g in section["activities"]["groups"] for a in g["activity_ids"]]

    assert sorted(grouped) == sorted(log.activity_id.unique())


def test_the_same_seed_gives_the_same_groups(section, log, model):
    assert clusters_section(log, model, seed=7) == section


@pytest.fixture(scope="module")
def exported_text(tmp_path_factory, log, model, params, section):
    out = tmp_path_factory.mktemp("web")
    results = build_results(log=log, model=model, params=params, seed=7, clusters=section)
    return export_results(results, out, models={"as_is": MODEL}).read_text()


@pytest.fixture
def exported(exported_text):
    # A fresh copy per test: the tests below break it on purpose.
    return json.loads(exported_text)


def test_exported_clusters_validate_against_the_schema(exported, section):
    validate_results(exported)
    assert exported["clusters"] == json.loads(json.dumps(section))


def test_a_group_whose_size_disagrees_with_its_points_is_rejected(exported):
    exported["clusters"]["cases"]["groups"][0]["case_count"] += 1

    with pytest.raises(jsonschema.ValidationError, match="points"):
        validate_results(exported)


def test_an_activity_listed_in_the_wrong_group_is_rejected(exported):
    # Swap one activity between two groups, so the group sizes still match the points.
    a, b = (g["activity_ids"] for g in exported["clusters"]["activities"]["groups"][:2])
    a[0], b[0] = b[0], a[0]

    with pytest.raises(jsonschema.ValidationError, match="aren't in that group"):
        validate_results(exported)
