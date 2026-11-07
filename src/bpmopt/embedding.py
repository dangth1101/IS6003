"""Graph embeddings in numpy: graph2vec for whole graphs, node2vec for the nodes of one graph.

Both end in the same model, skip-gram with negative sampling (Mikolov et al.,
2013): two tables of vectors, one for the inputs and one for what appears next
to them. Training pulls an input towards its real neighbours and pushes it
away from a few random ones. Inputs that share neighbours end up close.

- graph2vec (Narayanan et al., 2017): the input is a graph, its "neighbours"
  are its Weisfeiler-Lehman subtree labels (wl_words). Two graphs that contain
  the same small subgraphs get similar vectors. This is doc2vec's PV-DBOW with
  a graph as the document.
- node2vec (Grover and Leskovec, 2016): the input is a node, its neighbours are
  the nodes near it on biased random walks. p sets how likely a walk steps back
  to the node it came from, q how likely it moves away. Nodes that the walks
  visit together get similar vectors.

No gensim: see the spec (.scratch/graph-clustering/spec.md). Everything is
seeded, so the same inputs and seed give the same vectors.
"""

import hashlib
from collections.abc import Sequence

import numpy as np

# One graph for graph2vec: node labels, and directed edges as (from, to) node indices.
Graph = tuple[Sequence[str], Sequence[tuple[int, int]]]


def skipgram(
    pairs: np.ndarray,
    n_inputs: int,
    n_outputs: int,
    *,
    dimensions: int,
    epochs: int,
    seed: int,
    negatives: int = 5,
    learning_rate: float = 0.025,
    batch_size: int = 256,
) -> np.ndarray:
    """Input vectors, one row per input, trained on (input, output) index pairs.

    Negative outputs are drawn from the output frequencies to the power 0.75,
    as in word2vec. The learning rate falls linearly to near zero over the run.
    """
    rng = np.random.default_rng(seed)
    w_in = (rng.random((n_inputs, dimensions)) - 0.5) / dimensions
    w_out = np.zeros((n_outputs, dimensions))
    noise = np.bincount(pairs[:, 1], minlength=n_outputs) ** 0.75
    noise_cdf = np.cumsum(noise / noise.sum())

    batches = -(-len(pairs) // batch_size)
    total, step = epochs * batches, 0
    labels = np.zeros((batch_size, negatives + 1))
    labels[:, 0] = 1.0
    for _ in range(epochs):
        order = rng.permutation(len(pairs))
        for start in range(0, len(pairs), batch_size):
            batch = pairs[order[start : start + batch_size]]
            rate = learning_rate * max(1.0 - step / total, 1e-4)
            step += 1
            sampled = np.searchsorted(noise_cdf, rng.random((len(batch), negatives)), side="right")
            outputs = np.concatenate([batch[:, 1:2], np.minimum(sampled, n_outputs - 1)], axis=1)
            v, u = w_in[batch[:, 0]], w_out[outputs]
            score = 1.0 / (1.0 + np.exp(-np.einsum("bd,bkd->bk", v, u)))
            gradient = (labels[: len(batch)] - score) * rate
            np.add.at(w_in, batch[:, 0], np.einsum("bk,bkd->bd", gradient, u))
            np.add.at(w_out, outputs, gradient[:, :, None] * v[:, None, :])
    return w_in


def wl_words(labels: Sequence[str], edges: Sequence[tuple[int, int]], iterations: int) -> list[str]:
    """The Weisfeiler-Lehman subtree labels of a directed graph: its "words" for graph2vec.

    Round 0 is each node's own label. Each next round relabels a node with a
    hash of its label and the sorted labels of its successors and predecessors,
    so after h rounds a label stands for everything within h steps. Hashes come
    from hashlib, so they are the same in every Python process.
    """
    succ: list[list[int]] = [[] for _ in labels]
    pred: list[list[int]] = [[] for _ in labels]
    for a, b in edges:
        succ[a].append(b)
        pred[b].append(a)
    current = list(labels)
    words = list(current)
    for _ in range(iterations):
        current = [
            _hash(f"{current[n]}|{','.join(sorted(current[s] for s in succ[n]))}|{','.join(sorted(current[p] for p in pred[n]))}")
            for n in range(len(current))
        ]
        words += current
    return words


def _hash(text: str) -> str:
    return hashlib.blake2b(text.encode(), digest_size=8).hexdigest()


def graph2vec(graphs: Sequence[Graph], *, dimensions: int, iterations: int, epochs: int, seed: int) -> np.ndarray:
    """One vector per graph, in input order (Narayanan et al., 2017)."""
    documents = [wl_words(labels, edges, iterations) for labels, edges in graphs]
    vocabulary = {word: i for i, word in enumerate(sorted({w for doc in documents for w in doc}))}
    pairs = np.array([(g, vocabulary[w]) for g, doc in enumerate(documents) for w in doc], dtype=np.int64)
    return skipgram(pairs, len(graphs), len(vocabulary), dimensions=dimensions, epochs=epochs, seed=seed)


def node2vec(
    n_nodes: int,
    edges: Sequence[tuple[int, int, float]],
    *,
    dimensions: int,
    p: float,
    q: float,
    walk_length: int,
    walks_per_node: int,
    window: int,
    epochs: int,
    seed: int,
) -> np.ndarray:
    """One vector per node of an undirected weighted graph (Grover and Leskovec, 2016).

    edges are (a, b, weight). From node v, having come from t, a walk steps to
    a neighbour x with weight w(v, x) times 1/p if x is t, 1 if x is a
    neighbour of t, and 1/q otherwise. Every pair of nodes at most `window`
    steps apart on a walk is a training pair, both ways.
    """
    rng = np.random.default_rng(seed)
    neighbours: list[dict[int, float]] = [{} for _ in range(n_nodes)]
    for a, b, weight in edges:
        neighbours[a][b] = neighbours[a].get(b, 0.0) + weight
        neighbours[b][a] = neighbours[b].get(a, 0.0) + weight

    def step(previous: int | None, current: int) -> int | None:
        options = sorted(neighbours[current])
        if not options:
            return None
        weights = np.array([neighbours[current][x] for x in options])
        if previous is not None:
            bias = [1 / p if x == previous else 1.0 if x in neighbours[previous] else 1 / q for x in options]
            weights = weights * np.array(bias)
        return options[rng.choice(len(options), p=weights / weights.sum())]

    pairs = []
    for _ in range(walks_per_node):
        for start in rng.permutation(n_nodes):
            walk, previous = [int(start)], None
            while len(walk) < walk_length:
                nxt = step(previous, walk[-1])
                if nxt is None:
                    break
                previous = walk[-1]
                walk.append(nxt)
            for i, node in enumerate(walk):
                for other in walk[max(0, i - window) : i] + walk[i + 1 : i + 1 + window]:
                    pairs.append((node, other))
    return skipgram(np.array(pairs, dtype=np.int64), n_nodes, n_nodes, dimensions=dimensions, epochs=epochs, seed=seed)
