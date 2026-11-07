"""graph2vec and node2vec in numpy: they separate what is clearly separate, and a seed fixes the vectors."""

import os
import subprocess
import sys

import numpy as np

from bpmopt.clustering import group
from bpmopt.embedding import graph2vec, node2vec, wl_words


def _cliques() -> list[tuple[int, int, float]]:
    """Two 5-node cliques, nodes 0-4 and 5-9, joined by nothing."""
    edges = []
    for base in (0, 5):
        edges += [(base + a, base + b, 1.0) for a in range(5) for b in range(a + 1, 5)]
    return edges


def _node2vec(seed: int) -> np.ndarray:
    return node2vec(10, _cliques(), dimensions=8, p=1.0, q=0.5, walk_length=10, walks_per_node=20, window=3, epochs=5, seed=seed)


def _chain(labels: list[str]):
    return labels, [(i, i + 1) for i in range(len(labels) - 1)]


# Two path types: a clean pass, and a case that loops back through testing.
CLEAN = _chain(["start", "build", "test", "gate>pass", "deploy", "end"])
LOOP = _chain(["start", "build", "test", "gate>fail", "fix", "test", "gate>pass", "deploy", "end"])


def _graph2vec(seed: int) -> np.ndarray:
    return graph2vec([CLEAN] * 20 + [LOOP] * 20, dimensions=8, iterations=2, epochs=30, seed=seed)


def test_node2vec_puts_two_disconnected_cliques_in_two_groups():
    labels, _ = group(_node2vec(seed=1), seed=1)

    assert len(set(labels[:5])) == 1 and len(set(labels[5:])) == 1
    assert labels[0] != labels[5]


def test_graph2vec_puts_two_kinds_of_paths_in_two_groups():
    labels, _ = group(_graph2vec(seed=1), seed=1)

    assert len(set(labels[:20])) == 1 and len(set(labels[20:])) == 1
    assert labels[0] != labels[20]


def test_the_same_seed_gives_the_same_vectors():
    assert np.array_equal(_graph2vec(seed=3), _graph2vec(seed=3))
    assert np.array_equal(_node2vec(seed=3), _node2vec(seed=3))


def test_weisfeiler_lehman_words_tell_a_step_by_its_neighbours():
    # "test" before a pass and "test" before a fail are the same word in round 0, different words in round 1.
    a = wl_words(*_chain(["build", "test", "gate>pass"]), iterations=1)
    b = wl_words(*_chain(["build", "test", "gate>fail"]), iterations=1)

    assert a[:3] == ["build", "test", "gate>pass"]
    assert a[1] == b[1]
    assert a[3 + 1] != b[3 + 1]


def test_weisfeiler_lehman_words_are_the_same_in_every_python_process():
    # hashlib, not hash(): str hashes change per process with PYTHONHASHSEED, which would change the vectors.
    script = "from bpmopt.embedding import wl_words; print(wl_words(['a', 'b', 'c'], [(0, 1), (1, 2)], 2))"
    runs = [
        subprocess.run([sys.executable, "-c", script], env={**os.environ, "PYTHONHASHSEED": seed}, capture_output=True, text=True, check=True).stdout
        for seed in ("1", "2")
    ]

    assert runs[0] == runs[1]
