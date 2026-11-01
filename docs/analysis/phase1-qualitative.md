# Phase 1: Problem and objective (qualitative analysis)

> **Draft, awaiting student review.** Written from the model only, with no knowledge of how the real process runs. Every class, priority and number below is a proposal until the student signs off in ticket 09. Review questions are at the end.
>
> Numbers refreshed in ticket 14 from the proposed parameters (`models/as_is.params.toml`, version `proposed-1`) and the simulated log (seed 42, 2,000 cases). Classes, priorities and judgments are unchanged.

Model: `models/as_is.bpmn` (corrected in ticket 06, changes in `models/as_is_changelog.md`). Book: Dumas et al., *Fundamentals of BPM*, 2nd ed., printed page numbers. DSRM steps 1 and 2 (identify the problem, define the objective).

## Problem statement

The bank's application development process runs a request through three management approvals, a requirements and planning phase, a build, four checks in a row, deployment and a monitoring period. Work changes hands between five teams, every approval and test can send the work back, and all approvals queue at the same IT management lane. Nobody measures how long a request takes or where the time goes. This analysis names the likely causes of long cycle time; ticket 14 measures them on the simulated log.

## 1. Value-added analysis (§6.1, pp.213-218)

- Customer of the process (p.214): the business unit that asked for the application.
- Outcome they want: a working, secure application in live operation that does what they asked.
- Classes as defined on pp.214-215:
  - VA: the customer would see the outcome as less valuable without it.
  - BVA: the bank needs it (control, risk, regulation, records), but the customer doesn't pay for it.
  - NVA: neither.
- Rules of thumb from Example 6.1: control steps are generally BVA (p.216), handoffs are NVA (p.216), documentation required by the business is BVA (p.217).
- The book classifies steps, which can be finer than tasks (p.213). Here each task gets the class of its main step. A BVA approval can still hide NVA steps, like waiting for the next management meeting.
- The data lives in `models/as_is.value_added.toml` and goes into the `value_added` section of `web/results.json`.

| Task | Class | Reason |
| --- | --- | --- |
| Register development request | BVA | Lets the PMO track and prioritize requests; the requester gets nothing from the record |
| Approve project proposal | BVA | Control step: budget and fit checked before money is spent |
| Revise project proposal | NVA | Rework after the first proposal wasn't accepted |
| Hold project kick-off | BVA | Aligns business and IT on scope and roles, lowers risk |
| Specify business and technical requirements | VA | Decides what the application will do |
| Draft detailed project plan | BVA | Needed to book people and dates; adds nothing to the application |
| Approve project plan | BVA | Control step on the plan |
| Build application | VA | Produces what the customer asked for |
| Review source code | BVA | Control step |
| Run functional tests | BVA | Control step |
| Run security tests | BVA | Control step required by the bank's security rules |
| Run acceptance tests | BVA | Control step by the acceptance unit |
| Fix defects | NVA | Rework, defect waste (p.222) |
| Approve application release | BVA | Control step before production |
| Refine application | NVA | Rework after a rejected release (VA if it adds missing scope, see open question 6) |
| Deploy application to production | VA | Users get no value before this |
| Start live operation | BVA | Formal go-live and handover; the app is already deployed |
| Monitor live operation | BVA | Keeps the app stable, lowers incident risk |
| Evaluate project results | BVA | Archives records and lessons learned for the bank |

What this shows:

- 3 VA, 13 BVA, 3 NVA. A bank process full of controls is mostly BVA, which is expected.
- With the mean durations of the proposed parameters, a project that passes everything first time has about 102 days of processing: 54 VA (53%), 48 BVA, 0 NVA. The NVA time only comes from the loops (section 3, issues 1, 4, 6, 7).
- On the simulated log, over all cases including rejected ones and all loops, task time per case is 48 days VA (44%), 58 BVA (52%) and 4 NVA (4%).
- Removing BVA steps is a trade-off, not a free win (p.218). So the time saving should come from waiting, rework and how the BVA steps are arranged, not from dropping controls.

## 2. Waste analysis (§6.2, pp.218-223)

The book groups seven wastes into three categories (p.219).

### Move

- **Transportation** (p.219). Every sequence flow that crosses a lane is a handoff.
  - 15 of the 33 sequence flows cross a lane.
  - A project that passes every check the first time still has 8 handoffs: business unit → IT management → business unit → development → IT management → development → QC → IT management → IT operations.
  - Each loop adds 2 more (out to the team that reworks, back to the team that checks).
  - "Revise project proposal" sits in the IT operations lane (open question 1). If the business unit revises instead, the count stays the same but the waiting moves to another team.
- **Motion** (pp.220-221). Not visible in the model. In digital work it would be switching between tools during a task. No data, so it isn't analysed.

### Hold

- **Inventory** (p.221). Every started request that isn't closed is work in progress. By Little's law (p.266), WIP = arrival rate × cycle time, so at the same arrival rate a shorter cycle time means fewer open projects.
  - "Monitor live operation" keeps the project open for about 12 days on average after go-live (5 to 20 days). If that's a fixed warranty period, it is WIP with nobody adding value to the project (open question 9).
- **Waiting** (pp.221-222).
  - All three approvals sit in the IT management lane, plus every re-approval after a revision. The same few managers form one queue for every project.
  - Every handoff above is a place to wait. "Transportation waste often implies waiting waste" (p.222).
  - Measured on the log: 29.3 days of waiting per case on average, 21% of the mean cycle time. By lane, per case: QC 12.3 days, IT management 6.5, business unit 4.1, IT operations 3.7, development 2.6.
  - The three approvals have the longest wait per run (2.0, 1.9 and 1.8 days). QC adds the most waiting per case because the four checks rerun after every defect.
  - The simulation only has waiting for a free resource. It has no handoff delay, batching or calendar, so real waiting is likely higher.

### Overdo

- **Defects** (p.222). Four rework loops:
  - test loop: "Fix defects" then all four checks again;
  - release loop: "Refine application" then the whole test block and the release approval again;
  - proposal loop: "Revise project proposal" then approval again;
  - plan loop: "Draft detailed project plan" then approval again.
- **Overprocessing** (pp.222-223).
  - The checks run in sequence with one decision at the end (change log trade-off 3). If code review finds a defect, the functional, security and acceptance tests still run before anyone acts on it.
  - After a fix, all four checks rerun, including the ones that passed (open question 4).
  - A release rejected after all checks passed means the whole test cycle ran on a version that wasn't going to ship.
- **Overproduction** (p.223). A proposal rejected outright after registration and at least one approval round. If the reason for rejecting could have been seen at registration, the whole case was overproduction. Whether that happens depends on open question 2.

## 3. Issue register (§6.3.2, pp.229-232)

- Columns as on p.229: name, description, priority, data and assumptions, qualitative impact, quantitative impact. Added the optional "possible resolution" (p.230). One block per issue, one row per field, like Table 6.2 (p.231).
- Only issues with a direct effect on cycle time are listed (p.232).
- Numbers use the mean durations of the proposed parameters, the rework rates measured on the log, and the book's rework formula CT = T / (1 − r) (Eq. 7.4, p.260). They are ballpark figures, which the book accepts at this stage (p.229). Where the log gives a direct measure, it is shown too.
- Expected extra passes through a loop with rework probability r: r / (1 − r).

### Issue 1: Full test cycle repeats

| Field | Value |
| --- | --- |
| Priority | 1 |
| Description | When any check finds a defect, developers fix it and all four checks run again from code review. |
| Data and assumptions | Defects found in 38% of passes (measured). Checks 2.3 + 6.3 + 4.4 + 4.7 = 17.8 days per pass, fix 4.7 days. A project that reaches testing runs 1.75 passes on the log. Assumes everything reruns (open question 4). |
| Qualitative impact | Late go-live for the business unit. QC retests work that already passed. Developers switch back to old code. |
| Quantitative impact | 0.38 / 0.62 × (4.7 + 17.8) ≈ 13.6 days of extra processing per project, before any waiting. Measured on the log: about 16.5 days of extra processing plus 6.6 days of waiting in the extra passes, about 23 days. The formula is lower because the defect chance differs between projects. |
| Possible resolution | Rerun only the failed check; find defects earlier. Decided in ticket 15. |

### Issue 2: Approvals queue at IT management

| Field | Value |
| --- | --- |
| Priority | 1 |
| Description | IT management approves the proposal, the plan and the release, and approves again after every revision. All approvals share one lane. |
| Data and assumptions | 4.7 + 2.3 + 1.2 = 8.2 days of approval work on the first-time path. Three IT managers, busy about 80% of the time. In practice, cycle time efficiency is around 5% or lower (Table 7.4, p.263), so waiting is likely much larger than the approval work. Assumes "CNTT" is IT management (open question 7). |
| Qualitative impact | Teams sit idle waiting for a decision. The business unit can't see where its request is. Managers become the bottleneck. |
| Quantitative impact | Measured on the log: 6.5 days of waiting per case at the three approvals, 22% of all waiting. The approvals have the longest wait per run of all tasks: 2.0 days for the proposal, 1.9 for the plan, 1.8 for the release. |
| Possible resolution | Fewer or lighter approvals for low-risk projects, more approvers. Decided in ticket 15. |

### Issue 3: Checks run one after another

| Field | Value |
| --- | --- |
| Priority | 2 |
| Description | Code review, functional tests, security tests and acceptance tests run in sequence, and the pass/fail decision waits for all four. |
| Data and assumptions | 17.8 days per pass, about 1.75 passes per project (issue 1). If code review, functional and security tests could run at the same time, a pass would take max(2.3, 6.3, 4.4) + 4.7 = 11.0 days (Eq. 7.3, p.258). Depends on open questions 3 and 5. |
| Qualitative impact | Developers hear about defects late. Later checks run on code that already failed. |
| Quantitative impact | 17.8 × 1.75 ≈ 31 days in testing per project (31.2 measured), against 11.0 × 1.75 ≈ 19 days if run side by side: about 12 days. |
| Possible resolution | Run independent checks in parallel. Decided in ticket 15. |

### Issue 4: Release rejected after testing

| Field | Value |
| --- | --- |
| Priority | 2 |
| Description | Management can reject a release after all four checks passed. The application then goes through refinement, the full test block and the release approval again. |
| Data and assumptions | 8% of releases rejected (measured). Refine 6 days, test block about 34 days including its own rework (measured), approval 1.2 days. Depends on open question 6. |
| Qualitative impact | Problems found at the very end cost the most. QC and developers redo work they thought was done. |
| Quantitative impact | 0.08 / 0.92 × (6 + 34 + 1.2) ≈ 3.8 days per project. |
| Possible resolution | Get management's criteria into acceptance testing so issues show up earlier. Decided in ticket 15. |

### Issue 5: Many handoffs between teams

| Field | Value |
| --- | --- |
| Priority | 2 |
| Description | Work moves between five lanes. A project that passes every check the first time changes hands 8 times, and each loop adds 2. |
| Data and assumptions | 15 of 33 sequence flows cross a lane. PMO appears in two lanes (open question 8). |
| Qualitative impact | Each handoff is a place where work waits and information gets lost (p.219, p.261). It also feeds issue 2. |
| Quantitative impact | Measured on the log: 29.3 days of waiting per case, 21% of the mean cycle time. The simulation only has waiting for a free resource in the next lane, not delay from the handoff itself, so this is a lower bound. |
| Possible resolution | Merge steps done by neighbouring teams, or move a task to the lane that does the next step. Decided in ticket 15. |

### Issue 6: Proposal goes back and forth

| Field | Value |
| --- | --- |
| Priority | 3 |
| Description | A proposal can be sent back for changes any number of times, and some are rejected only after one or more rounds. |
| Data and assumptions | Each approval: 72% approved, 20% changes requested, 8% rejected. Revise 4.7 days, approve 4.7 days. Depends on open questions 1 and 2. |
| Qualitative impact | The requester repeats work and the project starts later. Rejected requests used approval time for nothing. |
| Quantitative impact | 0.2 / 0.8 × (4.7 + 4.7) ≈ 2.3 extra days per request. 0.08 / 0.8 = 10% of requests end rejected (10.2% on the log). |
| Possible resolution | Screen requests at registration. Decided in ticket 15. |

### Issue 7: Plan sent back

| Field | Value |
| --- | --- |
| Priority | 3 |
| Description | IT management can return the project plan for changes, and each round needs a new approval. |
| Data and assumptions | 19% of plans need changes (measured; set at 31% for new systems, 14% for the rest). Draft 4.3 days, approve 2.3 days. |
| Qualitative impact | Build starts later; developers wait on the plan. |
| Quantitative impact | 0.19 / 0.81 × (4.3 + 2.3) ≈ 1.6 extra days per project. |
| Possible resolution | Agree the plan's limits at kick-off. Decided in ticket 15. |

Total expected rework with the proposed parameters: about 13.6 + 3.8 + 2.3 + 1.6 ≈ 21 days per project, or about 21% on top of the 102 days of first-time processing.

## 4. Objective

**Proposed target, for review:** reduce the mean cycle time by **X = 20%** versus the simulated as-is baseline.

- Baseline on the as-is log (seed 42, 2,000 cases, all cases, as the pipeline computes it): mean cycle time 140.4 working days, median 136.5, P90 211.3. Processing 111.1, waiting 29.3, cycle time efficiency 0.79.
  - Closed projects only, for comparison (1,797 cases): mean 154.9, median 140.9, P90 216.9.
  - 20% of the all-cases mean is about 28 days.
- How it's measured:
  - cycle time = time from "Development request received" to the case's end event, in working days;
  - same parameter file, arrival rate and random seeds for as-is and to-be (common random numbers, ticket 13);
  - met when `scenarios[].saving` for the chosen design is at least 20% of the as-is mean and the lower bound of its 95% CI is above 0.
- Side conditions:
  - P90 cycle time doesn't get worse;
  - no VA task is removed, and no BVA task is removed without saying which business need it served (p.218);
  - cost, quality and flexibility are reported as trade-offs only (Devil's Quadrangle, pp.303-304).
- Why 20%:
  - Real processes usually have cycle time efficiency around 5% or lower (Table 7.4, p.263). If the synthetic baseline looks like that, most of the time is waiting, and cutting handoffs and approval queues can save a lot without touching the work itself.
  - The rework alone is about 21% of first-time processing with the proposed parameters, and parallel checks could save about 12 more days. So 20% looks reachable without dropping controls.
  - It stays modest because 13 of 19 tasks are BVA controls we keep, and "Build application" is the biggest single task.
  - Revisit after ticket 14: if the baseline's cycle time efficiency is high (say above 0.5), there is little waiting to remove and X should come down. If it's very low, X can go up. Measured: 0.79 (see the baseline above). Left for the student to decide in review question 4.
- Open points that change the target:
  - Open question 9: if "Monitor live operation" is a fixed warranty period, no redesign can shorten it. Either leave it out of the cycle time or accept that it dilutes the percentage.
  - Rejected proposals end early. They pull the mean down, and a design that rejects earlier would look faster for that reason alone. Measure on all cases (as the pipeline does now) or only on closed projects?

## Review questions for sign-off

1. Is the customer the requesting business unit? Every VA call rests on that.
2. Do you agree with these calls?
   - Register request: BVA.
   - Hold kick-off: BVA, or NVA?
   - Run acceptance tests: BVA, or VA because the business unit takes part?
   - Start live operation: BVA, or VA?
   - Refine application: NVA, or VA if it adds scope? (open question 6)
3. Are the approval queue (issue 2) and the repeated test cycle (issue 1) really the two biggest problems?
4. Is 20% the right target?
5. Should the target be measured on all cases or only on closed projects?
6. Should "Monitor live operation" count in the cycle time? (open question 9)
7. Open questions 1, 2, 3, 4, 5 and 7 in the change log change issues 1 to 6. Answering them may move priorities.
