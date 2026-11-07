# 01: graph2vec and node2vec in numpy

**What to build:** `src/bpmopt/embedding.py`: skip-gram with negative sampling, Weisfeiler-Lehman words, graph2vec and node2vec, all seeded.

**Status:** done

- [x] node2vec separates two disconnected cliques
- [x] graph2vec separates two kinds of graphs
- [x] Same seed, same vectors

## Comments

- 2026-11-07: claimed.
- 2026-11-07: done. `src/bpmopt/embedding.py`: one skip-gram trainer with negative sampling, used by both graph2vec (graph -> its Weisfeiler-Lehman words, PV-DBOW) and node2vec (biased walks, p and q). Hashes from hashlib, so the words don't change with PYTHONHASHSEED. Tests in `tests/test_embedding.py`, including a subprocess check with two hash seeds.
