# To-be model: change log

What the redesign changes in `models/as_is.bpmn`, why, and what it costs. Book: Dumas et al., *Fundamentals of BPM*, 2nd ed., printed page numbers. The change catalog with every number is `models/to_be.catalog.toml`.

The student delegated the design to Claude and approved keeping all four changes on 2026-11-03. Every effect size below is a proposed default, an assumption, not a measurement.

## Files

| File | What it is |
| --- | --- |
| `to_be.bpmn` | The full to-be model: C1 and C2 together. C3 and C4 only change parameters, so they need no model of their own |
| `to_be_c1.bpmn` | As-is plus C1 only |
| `to_be_c2.bpmn` | As-is plus C2 only |
| `to_be.catalog.toml` | The four changes, their parameter overrides, and which model each combination runs on |

The scenario runner simulates all 16 combinations of the four changes. A combination without C1 and C2 runs on the as-is model.

## What the changes aim at

From the baseline and the ML (ticket 14), seed 42:

- The four QC checks are the main queue. Each waits about 2 days for a tester, a test round takes about 26 days, and QC is the busiest lane (0.87).
- 37% of cases that reach testing go back for fixes at least once, the highest rework rate, and every fix sends the case through all four checks again.
- The ML ranks complexity and security level first for both cycle time and test rework.

## C1: Run the four checks in parallel

- Heuristic: Parallelism (Appendix A.3). Nothing in the process says code review must come before functional tests, or security tests before acceptance tests. They all check the same build.
- Model: an AND-split `Gateway_ChecksSplit` after the build sends the case to all four checks at once, and an AND-join `Gateway_ChecksJoin` waits for all four before the rework decision `Gateway_TestSplit`.
- New flows `Flow_CodeReviewStarted`, `Flow_FunctionalTestsStarted`, `Flow_SecurityTestsStarted`, `Flow_AcceptanceTestsStarted` (split to checks) and `Flow_ChecksCompleted` (join to the decision).
- Rerouted: `Flow_TestsStarted` now ends at the AND-split. `Flow_CodeReviewed`, `Flow_FunctionsTested`, `Flow_SecurityTested` and `Flow_AcceptanceTested` now end at the AND-join instead of the next check.
- Expected effect: a round takes as long as its longest check plus waiting, not the sum of four. The QC work per round stays the same.
- Trade-off: cost and quality worse. Four testers work on one case at once. A defect the code review finds can make a test that ran next to it worthless.

## C2: Retest only what was fixed

- Heuristic: Activity elimination (Appendix A.2). Rerunning checks that already passed is a control step that adds no value for the customer. This was the student's own idea (`models/as_is_changelog.md`, answered questions 3 and 4).
- Model: after `Task_FixDefects` the case goes to the new task `Task_RetestFixedDefects` "Retest fixed defects" in the QC lane, then to the new XOR-join `Gateway_RetestJoin` right before `Gateway_TestSplit`. The first round also enters that join. So a rework loop is now fix, retest, decide, and the four checks run once per case.
- New flows: `Flow_DefectsRetested` (retest to join), `Flow_TestRoundCompleted` (join to decision).
- Rerouted: `Flow_DefectsFixed` now ends at the retest. `Flow_AcceptanceTested` ends at the new join (in `to_be.bpmn`, `Flow_ChecksCompleted` does). `Flow_ReleaseCandidateReady` goes straight to the first check (or the AND-split in `to_be.bpmn`).
- Removed: `Gateway_TestJoin` and `Flow_TestsStarted`. Once fixed cases skip the checks, that join has only one incoming flow left, and a gateway with one in and one out does nothing (G1, §5.4.4 p.192).
- The outgoing flows of `Gateway_TestSplit` keep their IDs `Flow_TestsPassed` and `Flow_DefectsFound`, so the as-is branch parameters still apply.
- New task duration: triangular 1, 2, 4 working days, about one code review, against about 18 days of QC work for a full round. A retest finds new defects with the same chance as a full round, which is on the safe side for time.
- Trade-off: time and cost better, quality worse. A fix can break something a skipped check would have caught. Outside the model this needs automated regression tests, or a full rerun for security fixes.

## C3: Triage risky cases into an extended requirements version

- Heuristic: Triage (Appendix A.2), "split an activity into alternative versions". This is the change that links the ML to the redesign: it targets the two attributes the ML ranks first.
- Model: no change. Complex and highly classified cases get a longer `Task_SpecifyRequirements` with a threat model and an integration design. The simulator can't branch on a case attribute inside a task, so the two versions are approximated by a duration that grows with complexity and security level.
- Duration: 10% of the as-is base more for each complexity step and each security level step above 1. A simple internal app (complexity 1, security level 1) takes exactly what it takes today. About 1.6 days more on average, 3.9 for the riskiest case. 10% keeps the business unit lane below about 0.9 busy; at 15 to 20% it would come close to saturation.
- Defects: in `Gateway_TestSplit`, complexity goes from 0.6 to 0.4 per step and security level from 0.5 to 0.3, with the intercept raised so the simple case keeps its as-is rate. Over all cases, the chance that a round finds defects falls from about 35% to 27%.
- Trade-off: cost worse (more analyst time), quality better. The size of the defect reduction is assumed, so it belongs in the threats to validity.

## C4: Add one QC tester

- Heuristic: Extra resources (Appendix A.4).
- Parameters: `Lane_QualityControl` capacity 8 to 9. Utilisation drops from about 0.87 to about 0.77.
- Trade-off: cost worse (one more salary), flexibility better (slack for peaks and absences).

## G7: the to-be models are over 30 elements

7PMG G7 says to decompose a model with more than 30 elements (§5.4.4 p.193). The as-is model has exactly 30 flow nodes. The redesign adds some:

| Model | Flow nodes | Lint |
| --- | --- | --- |
| `as_is.bpmn` | 30 | clean |
| `to_be_c1.bpmn` | 32 (+2 AND gateways) | one G7 warning |
| `to_be_c2.bpmn` | 31 (+1 task, +1 join, -1 join) | one G7 warning |
| `to_be.bpmn` | 33 | one G7 warning |

The book's fix is to move part of the model into a sub-process. Our models stick to the subset the simulator can run, and sub-processes are not in it. The 7PMG are guidelines, not rules (p.192), and 33 nodes is only just over the limit. So the student accepted the G7 warning on the to-be models only: they have zero lint errors and no other warnings, and the as-is model still lints fully clean. The tests check exactly that.

## Labels

- New task "Retest fixed defects" follows the verb-object style (§3.1 p.77, G6). "Retest" was added to the linter's list of known verbs.
- AND and XOR gateways have no labels; the conditions stay on the arcs out of `Gateway_TestSplit` (§5.4.3 p.190).
