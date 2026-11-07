"""Group the cases (graph2vec) and the activities (node2vec) of an event log.

Cases: each case becomes a chain graph, one node per event in log order,
labeled with its activity. A gateway's label adds the branch it took, so a
loop back and a pass look different. graph2vec embeds the chains, and k-means
groups them. Each group is described by what a reader can check against the
baseline: its cycle time, how often its cases loop back at each rework
gateway, where they end, the attribute values that are over-represented, and
its most common path, as the node labels graph2vec read.

Activities: the directly-follows graph of the log. Two activities share an
edge when one directly follows the other in some case, weighted by how often.
node2vec embeds its nodes, and k-means groups them.

k is picked by silhouette over K_RANGE, on vectors scaled to length 1, so the
distance is cosine. Case groups are numbered by size, largest first. Activity
groups are numbered in process order, by the first activity of each to appear
in the log, so group 1 is the start of the process. The 2D view is PCA of the
same vectors.

clusters_section builds the `clusters` section of the results file.
"""

from collections import Counter
from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

from bpmopt.analysis import cycle_time_stats, cycle_times, outcomes
from bpmopt.bpmn import ProcessModel
from bpmopt.embedding import Graph, graph2vec, node2vec
from bpmopt.features import attribute_names
from bpmopt.flow_analysis import loop_back_flows

K_RANGE = (2, 6)
GRAPH2VEC = {"dimensions": 32, "wl_iterations": 2, "epochs": 20}
NODE2VEC = {"dimensions": 16, "p": 1.0, "q": 0.5, "walk_length": 20, "walks_per_node": 40, "window": 4, "epochs": 5}
# An attribute value goes in a group's profile when the group has it at least
# this many times as often as all cases do, and at least MIN_SHARE of all cases have it.
MIN_LIFT, MIN_SHARE, PROFILE_SIZE = 1.25, 0.05, 3
# Attributes with more distinct values than this (team workload) are left out of the profile.
MAX_PROFILE_VALUES = 10
# The most common paths listed in the results, for the demo's path list.
TOP_PATHS = 12


def clusters_section(log: pd.DataFrame, model: ProcessModel, *, seed: int, ends_at: str | None = None) -> dict:
    """The `clusters` section of the results file: case groups and activity groups."""
    return {"cases": case_clusters(log, model, seed=seed, ends_at=ends_at), "activities": activity_clusters(log, seed=seed)}


def event_label(row) -> str:
    """An event's node label: the activity, and for a gateway the flow it took."""
    return f"{row.activity_id}>{row.flow_id}" if row.element_type == "exclusiveGateway" else row.activity_id


def case_graphs(log: pd.DataFrame) -> dict[int, Graph]:
    """case_id -> chain graph of its events in log order."""
    labels = pd.Series([event_label(r) for r in log.itertuples()], index=log.index)
    graphs = {}
    for case_id, rows in log.groupby("case_id", sort=True).groups.items():
        nodes = list(labels[rows])
        graphs[int(case_id)] = (nodes, [(i, i + 1) for i in range(len(nodes) - 1)])
    return graphs


def follows_graph(log: pd.DataFrame) -> tuple[list[str], list[tuple[int, int, float]]]:
    """Activities in order of first appearance, and the directly-follows edges between them with their counts."""
    activities = list(dict.fromkeys(log.activity_id))
    index = {a: i for i, a in enumerate(activities)}
    follows = pd.DataFrame({"case_id": log.case_id, "a": log.activity_id.map(index)})
    follows["b"] = follows.groupby("case_id").a.shift(-1)
    counts = follows.dropna().astype({"b": int}).groupby(["a", "b"]).size()
    return activities, [(int(a), int(b), float(n)) for (a, b), n in counts.items() if a != b]


def group(vectors: np.ndarray, *, seed: int, by: str = "size") -> tuple[np.ndarray, list[dict]]:
    """K-means groups of the vectors, with k picked by silhouette.

    Groups are numbered by size, largest first (by="size"), or by the first
    vector of each, in input order (by="first"). Returns the group of each
    vector and the silhouette of every k tried.
    """
    x = _unit(vectors)
    tried = []
    for k in range(K_RANGE[0], min(K_RANGE[1], len(x) - 1) + 1):
        labels = KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(x)
        tried.append({"k": k, "silhouette": float(silhouette_score(x, labels)), "labels": labels})
    best = max(tried, key=lambda t: t["silhouette"])
    sizes = np.bincount(best["labels"])
    first = {g: int(np.argmax(best["labels"] == g)) for g in range(len(sizes))}
    key = (lambda g: first[g]) if by == "first" else (lambda g: (-sizes[g], g))
    rank = {old: new for new, old in enumerate(sorted(range(len(sizes)), key=key))}
    return np.array([rank[g] for g in best["labels"]]), [{"k": t["k"], "silhouette": t["silhouette"]} for t in tried]


def plane(vectors: np.ndarray) -> tuple[np.ndarray, list[float]]:
    """2D PCA coordinates of the unit vectors, and the share of variance each axis explains."""
    pca = PCA(n_components=2, svd_solver="full").fit(_unit(vectors))
    return pca.transform(_unit(vectors)), [float(v) for v in pca.explained_variance_ratio_]


def _unit(vectors: np.ndarray) -> np.ndarray:
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def case_clusters(log: pd.DataFrame, model: ProcessModel, *, seed: int, ends_at: str | None = None) -> dict:
    """graph2vec on the cases: method, silhouettes, one entry per group and one point per case."""
    graphs = case_graphs(log)
    case_ids = list(graphs)
    vectors = graph2vec(list(graphs.values()), dimensions=GRAPH2VEC["dimensions"], iterations=GRAPH2VEC["wl_iterations"],
                        epochs=GRAPH2VEC["epochs"], seed=seed)
    labels, silhouettes = group(vectors, seed=seed)
    xy, variance = plane(vectors)
    membership = pd.Series(labels, index=case_ids)
    return {
        "method": {"embedding": "graph2vec", **GRAPH2VEC, "k_range": list(K_RANGE)},
        "silhouette": silhouettes,
        "k": int(labels.max()) + 1,
        "explained_variance": variance,
        "groups": [_case_group(log, model, membership, graphs, g, ends_at) for g in range(int(labels.max()) + 1)],
        "path_count": len({tuple(nodes) for nodes, _ in graphs.values()}),
        "paths": _top_paths(log, graphs, membership, ends_at),
        "points": [
            {"case_id": c, "x": round(float(x), 4), "y": round(float(y), 4), "group": int(g)}
            for c, (x, y), g in zip(case_ids, xy, labels, strict=True)
        ],
    }


def _case_group(log: pd.DataFrame, model: ProcessModel, membership: pd.Series, graphs: dict[int, Graph], g: int, ends_at: str | None) -> dict:
    members = membership.index[membership == g]
    paths = Counter(tuple(graphs[c][0]) for c in members)
    path, count = max(paths.items(), key=lambda item: (item[1], item[0]))
    events = log[log.case_id.isin(members)]
    decisions = events[events.element_type == "exclusiveGateway"]
    loops = [
        {"gateway_id": gateway, "mean": float((decisions.activity_id.eq(gateway) & decisions.flow_id.eq(back)).sum() / len(members))}
        for gateway, back in loop_back_flows(model).items()
    ]
    ends = outcomes(events).value_counts(normalize=True)
    return {
        "id": g,
        "case_count": len(members),
        "cycle_time": cycle_time_stats(events, ends_at),
        "loops": loops,
        "outcomes": [{"end_event_id": e, "share": float(s)} for e, s in ends.items()],
        "profile": _profile(log, members),
        "path": {"labels": list(path), "share": count / len(members)},
    }


def _top_paths(log: pd.DataFrame, graphs: dict[int, Graph], membership: pd.Series, ends_at: str | None) -> list[dict]:
    """The TOP_PATHS most common paths: their labels, how many cases took each, their mean cycle time and their group.

    Cases on the same path have the same words but their own vectors, so a path's group is the one most of its cases are in.
    """
    by_path: dict[tuple[str, ...], list[int]] = {}
    for case_id, (nodes, _) in graphs.items():
        by_path.setdefault(tuple(nodes), []).append(case_id)
    ranked = sorted(by_path.items(), key=lambda item: (-len(item[1]), item[0]))[:TOP_PATHS]
    times = cycle_times(log, ends_at)
    return [
        {"labels": list(path), "case_count": len(cases), "cycle_time": float(times[cases].mean()), "group": int(membership[cases].mode().min())}
        for path, cases in ranked
    ]


def _profile(log: pd.DataFrame, members: Sequence[int]) -> list[dict]:
    """Attribute values over-represented in the group, by lift (share in the group / share in all cases)."""
    cases = log.groupby("case_id")[attribute_names(log)].first()
    inside = cases.loc[cases.index.isin(members)]
    rows = []
    for attribute in cases.columns:
        if cases[attribute].nunique() > MAX_PROFILE_VALUES:
            continue
        overall = cases[attribute].value_counts(normalize=True)
        share = inside[attribute].value_counts(normalize=True).reindex(overall.index, fill_value=0.0)
        for value in overall.index:
            if overall[value] >= MIN_SHARE and share[value] >= MIN_LIFT * overall[value]:
                rows.append({"feature": attribute, "value": _plain(value), "share": float(share[value]), "overall_share": float(overall[value])})
    rows.sort(key=lambda r: (-r["share"] / r["overall_share"], r["feature"], str(r["value"])))
    return rows[:PROFILE_SIZE]


def _plain(value):
    return value.item() if hasattr(value, "item") else value


def activity_clusters(log: pd.DataFrame, *, seed: int) -> dict:
    """node2vec on the directly-follows graph: method, silhouettes, the groups and one point per activity."""
    activities, edges = follows_graph(log)
    vectors = node2vec(len(activities), edges, dimensions=NODE2VEC["dimensions"], p=NODE2VEC["p"], q=NODE2VEC["q"],
                       walk_length=NODE2VEC["walk_length"], walks_per_node=NODE2VEC["walks_per_node"],
                       window=NODE2VEC["window"], epochs=NODE2VEC["epochs"], seed=seed)
    labels, silhouettes = group(vectors, seed=seed, by="first")
    xy, variance = plane(vectors)
    k = int(labels.max()) + 1
    return {
        "method": {"embedding": "node2vec", **NODE2VEC, "k_range": list(K_RANGE)},
        "silhouette": silhouettes,
        "k": k,
        "explained_variance": variance,
        "groups": [{"id": g, "activity_ids": [a for a, lab in zip(activities, labels, strict=True) if lab == g]} for g in range(k)],
        "edges": [{"source": activities[a], "target": activities[b], "count": int(n)} for a, b, n in edges],
        "points": [
            {"activity_id": a, "x": round(float(x), 4), "y": round(float(y), 4), "group": int(g)}
            for a, (x, y), g in zip(activities, xy, labels, strict=True)
        ],
    }
