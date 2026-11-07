# Spec: Grouping cases and activities with graph embeddings

**Status:** ready-for-agent

## Problem Statement

The ML section predicts from the attributes known at case start. It doesn't look at the path a case took. The student asked (2026-11-07) for graph2vec and node2vec to group the cases and the activities, drawn in the notebook and on the page.

## Solution

1. **graph2vec on cases.** Each case of the as-is log becomes a small graph: one node per event, labeled with its activity (a gateway with the branch it took), and an edge from each event to the next. Graph2vec (Narayanan et al., 2017) turns each graph into a vector: Weisfeiler-Lehman subtree labels are the words of the graph, and a PV-DBOW model (doc2vec) learns one vector per graph. K-means groups the vectors; k is picked by silhouette from 2 to 6. Per group: case count, mean cycle time, loops back per case, the most common path, and the attribute values that are over-represented.
2. **node2vec on activities.** The directly-follows graph of the log (an edge between two activities when one directly follows the other in a case, weighted by how often) is embedded with node2vec (Grover and Leskovec, 2016): biased random walks with return parameter p and in-out parameter q, then skip-gram. K-means groups the activities, k by silhouette from 2 to 6.
3. **Page section** after "What machine learning found": a scatter of the case vectors in 2D (PCA), colored by group, a table of the groups, and the as-is diagram colored by activity group.

## Implementation Decisions

- No gensim or karateclub. karateclub pins numpy 1.22 and pandas 1.3. gensim 4.4.0 reports an ignored exception in its C dot product on this machine (`our_dot_float`), so its vectors can't be trusted. Skip-gram with negative sampling is written in numpy (`bpmopt.embedding`), seeded, so a rerun gives the same vectors.
- Weisfeiler-Lehman relabeling uses hashlib, not Python's `hash`, which changes per process.
- The 2D view is PCA, not t-SNE, so it is deterministic and the distances keep their meaning.
- Results contract version 5 adds an optional `clusters` section with `cases` and `activities`.
- Cycle time per group ends at the parameters' cut-off, like the baseline.

## Testing Decisions

- Embedding: two disconnected cliques land in two node2vec groups; two kinds of graphs land in two graph2vec groups; the same seed gives the same vectors.
- Clusters: case graphs from a fixture log, the section validates against the schema, group sizes add up to the case count.
- Page: the fake results fill the new section; the label test still passes.

## Out of Scope

- Clustering the to-be scenarios.
- Using the groups as ML features.
