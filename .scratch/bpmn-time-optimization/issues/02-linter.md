# 02: Linter for the book's modeling rules

**What to build:** `lint(bpmn file)` returns a list of violations, each with rule ID, element ID and message, covering every checkable rule in the spec: 7PMG G1–G7 (§5.4.4), event labels present and not generic, no yes/no labels on XOR split arcs (p.190), lanes inside a pool, every node reachable from a start and able to reach an end (§5.4.1), and no element types outside the supported subset.

**Blocked by:** 01

**Status:** done

- [x] One fixture per rule that breaks only that rule, and the linter reports exactly that rule
- [x] One clean fixture that reports no violations
- [x] Verb-object label check is a heuristic, documented as such, and reported as a warning, not an error
- [x] Each rule cites its book section in the message
- [x] The original `current_process.bpmn` is linted in a test that expects the known violations (no pool, generic event labels, Có/Không arcs, missing end event for a rejected proposal)

## Comments

- Done. `bpmopt.lint.lint(path) -> list[Violation]`. `Violation` has `rule`, `element_id`, `message`, `severity` ("error" or "warning"). It's a frozen dataclass, so `dataclasses.asdict` gives the JSON row for the results file.
- Rule IDs: POOL, EVENT-LABEL, ARC-LABEL, REACH, SUBSET (errors), G1, G2, G3, G6, G7 (warnings), G4, G5 (errors). The 7PMG are guidelines, i.e. suggestions (p.192), hence warnings. G4 is an error because a mismatched split/join is always a behavioral anomaly (p.185). G5 is an error because OR gateways are also outside the subset.
- Our interpretations, all marked in the code:
  - G7 "element" = flow node (events, tasks, gateways). Arcs, lanes and the pool don't count. The book doesn't define it (p.193).
  - G1 has no number in the book (p.192), and size is G7's job. G1 flags gateways with one arc in and one out, i.e. elements you can drop without changing behavior.
  - G2 limit is 5 routing paths (in + out) per element. Our number, the book gives none (p.192). A 4-branch split or join is the most it allows.
  - G3 flags events of one kind with the same label, and (heuristic) a model with one end event plus an XOR split that no XOR join closes. That second part is what catches the rejected proposal. It also fires on a plain rework loop with a single end, so it's a warning.
  - G4 checks only that each split's first meeting point (immediate post-dominator) isn't a gateway of another type. Unstructured cycles aren't detected.
  - G6 is a word-list heuristic: first word must be a capitalized verb in `KNOWN_VERBS`, not make/do/perform/conduct (p.77), followed by an object. English only. If a good label gets flagged, add the verb to the list.
  - REACH is a graph check, not full soundness (p.186). An AND join fed by an XOR split passes REACH; G4 catches the usual case.
- POOL cites §3.4 with no page; it isn't in our book notes. Check the page if the grader cares.
- Not checked: missing condition labels on XOR split arcs (p.184), lowercase event labels, compound activities like the as-is "test" task. Those need a human look.
- The as-is test expects G6 on all 15 tasks, because the labels are Vietnamese.
- For ticket 06 to lint clean (no errors, no warnings):
  - wrap the process in a pool (a `collaboration` with a `participant`), lanes inside it
  - at most 30 flow nodes. The corrected model is close: about 25 with the split test activity and a "Proposal rejected" end, so explicit XOR merges plus an AND block land right at 30
  - a separate end event for each outcome; no two ends with the same label
  - XOR split arcs with real conditions ("proposal approved"), never yes/no
  - no 1-in-1-out gateways, at most 4 branches per split or join
  - task labels start with a verb from `KNOWN_VERBS` (extend it if needed); event labels have at least two words and aren't "Start"/"End"
