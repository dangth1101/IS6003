# 02: Linter for the book's modeling rules

**What to build:** `lint(bpmn file)` returns a list of violations, each with rule ID, element ID and message, covering every checkable rule in the spec: 7PMG G1–G7 (§5.4.4), event labels present and not generic, no yes/no labels on XOR split arcs (p.190), lanes inside a pool, every node reachable from a start and able to reach an end (§5.4.1), and no element types outside the supported subset.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] One fixture per rule that breaks only that rule, and the linter reports exactly that rule
- [ ] One clean fixture that reports no violations
- [ ] Verb-object label check is a heuristic, documented as such, and reported as a warning, not an error
- [ ] Each rule cites its book section in the message
- [ ] The original `current_process.bpmn` is linted in a test that expects the known violations (no pool, generic event labels, Có/Không arcs, missing end event for a rejected proposal)
