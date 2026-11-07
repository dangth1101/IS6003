"""Handover of work between departments, and how central each department is in it.

This is the social network of process mining (van der Aalst, handover of work):
the nodes are the resources, here the lanes, since a lane is a pool of people.
Work passes from lane A to lane B when, in some case, a task of B is the next
task after a task of A. Each pair counts how often that happens. Gateways and
events are left out: they are no work.

Centrality, one row per lane, all from networkx:

- degree: the share of the other lanes it hands work to or gets work from.
- in and out handovers: how often it gets work and hands it on (weighted degree).
- closeness: (n - 1) / the number of handovers it takes to reach each other
  lane, counted in hops, so 1 means it reaches every lane directly.
- betweenness (Freeman, 1977): the share of shortest paths between two other
  lanes that run through it, so a high value marks a broker. A stronger tie is
  a shorter one, so each edge has length 1 / handovers (Opsahl et al., 2010).
  Brandes' algorithm, directed, normalised by (n - 1)(n - 2), so 0 to 1.
- pagerank: where work flows to, counting a handover from a lane that gets
  much work as more; weighted by handovers, damping 0.85, sums to 1.

social_section builds the `social` section of the results file.
"""

import networkx as nx
import pandas as pd


def handovers(log: pd.DataFrame) -> pd.DataFrame:
    """One row per (source lane, target lane) pair with how often work passed between them, most first."""
    tasks = log[log.element_type == "task"]
    following = tasks.groupby("case_id").lane_id.shift(-1)
    pairs = pd.DataFrame({"source": tasks.lane_id, "target": following}).dropna()
    pairs = pairs[pairs.source != pairs.target]
    counts = pairs.value_counts().rename("count").reset_index()
    return counts.sort_values(["count", "source", "target"], ascending=[False, True, True], ignore_index=True)


def network(edges: pd.DataFrame) -> nx.DiGraph:
    """The handover network, each edge with its count and its distance 1 / count."""
    graph = nx.DiGraph()
    for row in edges.itertuples():
        graph.add_edge(row.source, row.target, count=int(row.count), distance=1 / row.count)
    return graph


def betweenness(graph: nx.DiGraph) -> dict[str, float]:
    """Normalised, weighted betweenness of every lane, with distance 1 / handovers."""
    return nx.betweenness_centrality(graph, weight="distance", normalized=True)


def centrality(graph: nx.DiGraph) -> list[dict]:
    """Every centrality measure of every lane, highest betweenness first (see the module docstring)."""
    degree = nx.degree_centrality(graph.to_undirected())
    closeness = nx.closeness_centrality(graph.reverse())  # networkx counts distances in; reversed, they count out
    between = betweenness(graph)
    rank = nx.pagerank(graph, weight="count", alpha=0.85)
    rows = [
        {
            "lane_id": lane,
            "degree": float(degree[lane]),
            "in_handovers": int(graph.in_degree(lane, weight="count")),
            "out_handovers": int(graph.out_degree(lane, weight="count")),
            "closeness": float(closeness[lane]),
            "betweenness": float(between[lane]),
            "pagerank": float(rank[lane]),
        }
        for lane in graph
    ]
    return sorted(rows, key=lambda r: (-r["betweenness"], -r["pagerank"], r["lane_id"]))


def social_section(log: pd.DataFrame) -> dict:
    """The `social` section of the results file: the handovers and each lane's centrality, highest betweenness first."""
    edges = handovers(log)
    return {
        "method": {"network": "handover of work between lanes", "distance": "1 / handovers", "normalized": True},
        "handovers": [{"source": r.source, "target": r.target, "count": int(r.count)} for r in edges.itertuples()],
        "centrality": centrality(network(edges)),
    }
