# 06: Corrected as-is model (Phase 0)

**What to build:** A new as-is BPMN model in English that fixes the current model against the book, and lints clean. The original `current_process.bpmn` stays unchanged for reference. Changes include a pool around the lanes, event labels as object + past participle, explicit conditions instead of Có/Không, the compound test activity split into code review, functional testing, security testing and acceptance, a "Proposal rejected" end event, and verb-object activity labels. A short change log maps every change to the book rule it satisfies.

**Blocked by:** 02

**Status:** done

- [x] New model lints with zero errors
- [x] Every element of the original model is accounted for in the change log (kept, renamed, split or removed, with the reason)
- [x] Lane of "revise proposal" is raised as an open question for the student in the change log, not silently moved
- [x] Model opens and renders in bpmn-js
- [x] Model uses only the simulator's supported subset

## Comments

- Done. Model in `models/as_is.bpmn`, change log in `models/as_is_changelog.md`. The notebook now simulates this model, so `web/models/as_is.bpmn` is a copy of it and the page draws it. `tests/test_as_is_model.py` lints it (zero errors, zero warnings), simulates it, checks every node, flow and lane has DI, and checks the change log mentions every element ID of `current_process.bpmn`.
- 30 flow nodes, exactly the G7 limit. The four checks run in sequence. An AND block would make it 31. Running them in parallel is a good redesign candidate, but the to-be model has no spare node either.
- The shared `fix` task became two tasks, "Fix defects" (after failed tests) and "Refine application" (after a rejected release). That gives nested rework blocks the book's flow analysis can reduce. A shared fix task would make an unstructured cycle.
- `models/as_is.params.toml` holds placeholder parameters (fixed durations, fixed branch probabilities, no arrivals, no capacities). Ticket 10 replaces it. The page numbers mean nothing until then.
- For ticket 08: `theoretical_cycle_time` on this model fails only at `Gateway_ProposalSplit`, the 3-way split whose "proposal rejected" arc goes to `End_ProposalRejected`. With that arc removed it gives 109.2 days on the placeholders, so the rest is block-structured.
- Element IDs: tasks `Task_*`, XOR splits `Gateway_ProposalSplit`, `Gateway_PlanSplit`, `Gateway_TestSplit`, `Gateway_ReleaseSplit`, their joins `Gateway_*Join`, lanes `Lane_BusinessUnit`, `Lane_ITManagement`, `Lane_Development`, `Lane_QualityControl`, `Lane_ITOperations`. Full mapping from the old IDs is in the change log.
- Checked in headless Chrome: bpmn-js 18.28.0 imports it with no warnings, all lanes, nodes and flows draw, no crossing arcs, the page shows it with no errors.
- Open questions for the student (details in the change log):
  - Which lane does "Revise project proposal" belong in? Kept in IT operations / App support / PMO as in the original; the business unit seems more likely.
  - When is a proposal rejected outright, versus sent back for changes? Can a plan or release be cancelled, or do they only loop back?
  - Do code review, functional, security and acceptance tests run in sequence or partly in parallel?
  - After a failed check, do all four checks rerun or only the failed one?
  - Who does code review and acceptance: QC, developers, the business unit?
  - Is refining a rejected release different work from fixing test defects?
  - Is "CNTT" IT management? Is PMO in two lanes one team?
  - How long is "Monitor live operation", and does it belong in the cycle time?
