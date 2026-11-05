# Phase 1: Problem and objective (qualitative analysis)

> **Signed off by the student on 2026-11-05 (ticket 09).** Written from the model, then checked against the student's answers. The numbers are simulated, not measured. The answers are at the end.
>
> Numbers refreshed after the student's answers and the arrival-rate decision, from the parameters (`models/as_is.params.toml`, version `proposed-3`) and the simulated log (seed 42, 2,000 cases). Cycle time now ends at go-live. Where the new numbers changed a judgment, it is listed below.

Model: `models/as_is.bpmn` (corrected in ticket 06, changes and the student's answers in `models/as_is_changelog.md`). Book: Dumas et al., *Fundamentals of BPM*, 2nd ed., printed page numbers. DSRM steps 1 and 2 (identify the problem, define the objective).

## Changes since first draft

For the student to check. Each one is a judgment that moved because the numbers moved.

- Arrival rate lowered from 0.25 to 0.234 requests per working day (about 58 a year instead of 62), the student's decision. It keeps QC, the busiest lane, near the 88% it had in the first draft, so the results aren't dominated by queueing close to saturation (§7.2, p.276). At 0.25, rarer rejections had pushed QC to 93%. Utilisation now: business unit 78%, IT management 77%, development 81%, IT operations 79%, QC 87%. No priority changed with it.
- The approvals queue is no longer a top priority. It was issue 2 with priority 1; it is now issue 4 with priority 2. QC adds 13.0 days of waiting per case against 5.5 at the three approvals, and every check waits longer per run (1.9 to 2.0 days) than any approval (1.5 to 1.6).
- New issue 2, "Checks queue at QC", priority 1. QC is busy 87% of the time and holds almost half of all waiting. Old issues 3 to 7 are now issues 3 and 5 to 8 (old 3 stays 3, old 4 becomes 5, and so on).
- Issue 1 (test cycle repeats) stays first. Its measured cost is about 21 days per project instead of 23. The waiting in the extra rounds went from 6.6 to 6.2 days.
- Waiting is 21% of the cycle time, the same as the first draft. Rarer rejections had pushed it to 31% at the old arrival rate (more projects reach QC with the same eight testers); the lower rate takes it back.
- The baseline mean went down, from 140.4 to 132.5 days. The go-live cut-off takes off about 16, rarer rejections add about 27 (fewer short rejected cases, longer queues), and the lower arrival rate takes off about 18.
- The case for 20% is rewritten. The first draft said to lower X if cycle time efficiency came out above 0.5. It is 0.79, but the student set 20%. 20% is about 27 days, nearly all of the 28 days of waiting, so it can't come from shorter queues alone. The new wording says 20% probably needs two or three changes aimed at testing that also cut processing, not one.
- Overproduction is now minor. Rejection is rare (about 4% of requests instead of 10%), so few cases use approval time and end with nothing.
- "Monitor live operation" moved out of the cycle time. It is still work in progress (the project stays open) but no longer part of the target.

## Problem statement

The bank's application development process runs a request through three management approvals, a requirements and planning phase, a build, four checks in a row, deployment and go-live, followed by a monitoring period. Work changes hands between five teams, every approval and test can send the work back, and the four checks all queue at one QC team. Nobody measures how long a request takes or where the time goes. This analysis names the likely causes of long cycle time; the simulated log (ticket 14) measures them.

## 1. Value-added analysis (§6.1, pp.213-218)

- Customer of the process (p.214): the business unit that asked for the application. It is an internal customer: the book calls the one who consumes the output the customer, even when that is an employee of the organization (§1.2, p.5).
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
| Register development request | VA | The business unit fills in its own request, and nothing can start without it. The book classes "Fill request" as VA (Table 6.1, p.217); the logging part is BVA but smaller |
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
| Refine application | NVA | Rework after a rejected release (VA if it adds missing scope; the student confirmed it is different work from fixing defects) |
| Deploy application to production | VA | Users get no value before this |
| Start live operation | BVA | Formal go-live and handover; the app is already deployed |
| Monitor live operation | BVA | Keeps the app stable, lowers incident risk. After go-live, so outside the cycle time |
| Evaluate project results | BVA | Archives records and lessons learned for the bank. After go-live, so outside the cycle time |

What this shows:

- 4 VA, 12 BVA, 3 NVA. A bank process full of controls is mostly BVA, which is expected.
- With the mean durations of the parameters, a project that passes everything first time has about 88 days of processing up to go-live: 55 VA (63%), 33 BVA, 0 NVA. Monitoring and evaluation add another 14 BVA days after go-live, outside the cycle time. The NVA time only comes from the loops (section 3, issues 1, 5, 7, 8).
- On the simulated log, up to go-live and over all cases including rejected ones and all loops, task time per case is 53 days VA (51%), 47 BVA (45%) and 5 NVA (4%).
- Removing BVA steps is a trade-off, not a free win (p.218). So the time saving should come from waiting, rework and how the BVA steps are arranged, not from dropping controls.

## 2. Waste analysis (§6.2, pp.218-223)

The book groups seven wastes into three categories (p.219).

### Move

- Transportation (p.219). Every sequence flow that crosses a lane is a handoff.
  - 15 of the 33 sequence flows cross a lane.
  - A project that passes every check the first time still has 8 handoffs: business unit → IT management → business unit → development → IT management → development → QC → IT management → IT operations.
  - Each loop adds 2 more (out to the team that reworks, back to the team that checks).
  - "Revise project proposal" sits in the IT operations lane, as in the original. The student confirmed this.
- Motion (pp.220-221). Not visible in the model. In digital work it would be switching between tools during a task. No data, so it isn't analysed.

### Hold

- Inventory (p.221). Every started request that isn't closed is work in progress. By Little's law (p.266), WIP = arrival rate × cycle time, so at the same arrival rate a shorter cycle time means fewer open projects.
  - "Monitor live operation" keeps the project open for about 12 days on average after go-live (5 to 20 days). The student confirmed this hypercare period. It is still work in progress, but it's outside the cycle time, which ends at go-live.
- Waiting (pp.221-222).
  - Measured on the log: 27.8 days of waiting per case on average, 21% of the mean cycle time. By lane, per case: QC 13.0 days, IT management 5.5, business unit 4.1, development 2.8, IT operations 2.4.
  - QC adds almost half of all waiting. Its eight testers are busy 87% of the time, and a project that reaches testing needs about 7 check runs (four checks, 1.74 rounds).
  - The four checks have the longest wait per run (1.9 to 2.0 days). The three approvals come next (1.5 to 1.6 days).
  - All three approvals sit in the IT management lane, plus every re-approval after a revision. That is one shared queue too, but a smaller one.
  - Every handoff above is a place to wait. "Transportation waste often implies waiting waste" (p.222).
  - The simulation only has waiting for a free resource. It has no handoff delay, batching or calendar, so real waiting is likely higher.

### Overdo

- Defects (p.222). Four rework loops:
  - test loop: "Fix defects" then all four checks again;
  - release loop: "Refine application" then the whole test block and the release approval again;
  - proposal loop: "Revise project proposal" then approval again;
  - plan loop: "Draft detailed project plan" then approval again.
- Overprocessing (pp.222-223).
  - The checks run in sequence with one decision at the end (change log trade-off 3; the student confirmed the sequence). If code review finds a defect, the functional, security and acceptance tests still run before anyone acts on it.
  - After a fix, all four checks rerun, including the ones that passed. The student confirmed this and said it can be optimized, so it is a redesign candidate for ticket 15.
  - A release rejected after all checks passed means the whole test cycle ran on a version that wasn't going to ship.
- Overproduction (p.223). A proposal rejected outright after registration and at least one approval round. If the reason for rejecting could have been seen at registration, the whole case was overproduction. The student says outright rejection is possible but rare: 3% of proposal decisions, about 4% of requests. So this waste is small.

## 3. Issue register (§6.3.2, pp.229-232)

- Columns as on p.229: name, description, priority, data and assumptions, qualitative impact, quantitative impact. Added the optional "possible resolution" (p.230). One block per issue, one row per field, like Table 6.2 (p.231).
- Only issues with a direct effect on cycle time are listed (p.232). Issues are numbered in priority order.
- Numbers use the mean durations of the parameters, the rework rates measured on the log, and the book's rework formula CT = T / (1 − r) (Eq. 7.4, p.260). They are ballpark figures, which the book accepts at this stage (p.229). Where the log gives a direct measure, it is shown too. All log numbers stop at go-live.
- Expected extra passes through a loop with rework probability r: r / (1 − r).

### Issue 1: Full test cycle repeats

| Field | Value |
| --- | --- |
| Priority | 1 |
| Description | When any check finds a defect, developers fix it and all four checks run again from code review. |
| Data and assumptions | Defects found in 37% of passes (measured). Checks 2.3 + 6.3 + 4.4 + 4.7 = 17.8 days per pass, fix 4.7 days. A project that reaches testing runs 1.74 passes on the log. All four checks rerun (student confirmed). |
| Qualitative impact | Late go-live for the business unit. QC retests work that already passed. Developers switch back to old code. |
| Quantitative impact | 0.37 / 0.63 × (4.7 + 17.8) ≈ 13.2 days of extra processing per project, before any waiting. Measured on the log: about 14.7 days of extra processing plus 6.2 days of waiting in the extra passes, about 21 days. The formula is lower because the defect chance differs between projects. |
| Possible resolution | Rerun only the failed check (the student says this can be optimized); find defects earlier. Decided in ticket 15. |

### Issue 2: Checks queue at QC

| Field | Value |
| --- | --- |
| Priority | 1 |
| Description | All four checks, and every rerun, go to the same QC / acceptance team. It is the busiest lane, so checks wait for a free tester before they start. |
| Data and assumptions | Eight testers, busy 87% of the time (88% in the first draft; 93% after rejections became rare, before the arrival rate was lowered). About 7 check runs per project that reaches testing (4 × 1.74). All four checks sit in the QC lane (student confirmed). The QC capacity is a proposed default and the estimate that moves the results most (ticket 10). |
| Qualitative impact | Every check waits, and each failed round adds four more waits. Developers wait longer for feedback. |
| Quantitative impact | Measured on the log: 13.0 days of waiting per case at QC, 47% of all waiting. Each check waits 1.9 to 2.0 days per run, the longest of all tasks. Close to full load a queue reacts strongly to small changes in load (p.276), so less QC work per project should cut this waiting by more than the work saved. |
| Possible resolution | Less QC work per project (issues 1 and 3), more testers, or test automation. Decided in ticket 15. |

### Issue 3: Checks run one after another

| Field | Value |
| --- | --- |
| Priority | 2 |
| Description | Code review, functional tests, security tests and acceptance tests run in sequence, and the pass/fail decision waits for all four. |
| Data and assumptions | 17.8 days per pass, about 1.74 passes per project (issue 1). If code review, functional and security tests could run at the same time, a pass would take max(2.3, 6.3, 4.4) + 4.7 = 11.0 days (Eq. 7.3, p.258). The student confirmed they run in sequence today, all in the QC lane. |
| Qualitative impact | Developers hear about defects late. Later checks run on code that already failed. |
| Quantitative impact | 17.8 × 1.74 ≈ 31 days in testing per project (31.0 measured), against 11.0 × 1.74 ≈ 19 days if run side by side: about 12 days. Running them side by side doesn't lower QC's load, so it does little for issue 2. |
| Possible resolution | Run independent checks in parallel. Decided in ticket 15. |

### Issue 4: Approvals queue at IT management

| Field | Value |
| --- | --- |
| Priority | 2 (was 1 in the first draft) |
| Description | IT management approves the proposal, the plan and the release, and approves again after every revision. All approvals share one lane. |
| Data and assumptions | 4.7 + 2.3 + 1.2 = 8.2 days of approval work on the first-time path. Three IT managers, busy about 77% of the time. "CNTT" is IT management (student confirmed). Real approval queues may be longer, since the simulation has no meeting calendar. |
| Qualitative impact | Teams sit idle waiting for a decision. The business unit can't see where its request is. |
| Quantitative impact | Measured on the log: 5.5 days of waiting per case at the three approvals, 20% of all waiting. Wait per run: 1.6 days for the proposal, 1.6 for the plan, 1.5 for the release, all shorter than at the QC checks. |
| Possible resolution | Fewer or lighter approvals for low-risk projects, more approvers. Decided in ticket 15. |

### Issue 5: Release rejected after testing

| Field | Value |
| --- | --- |
| Priority | 2 |
| Description | Management can reject a release after all four checks passed. The application then goes through refinement, the full test block and the release approval again. |
| Data and assumptions | 8.3% of releases rejected (measured). Refine 6 days, test block about 34 days including its own rework (measured), approval 1.2 days. Refining is different work from fixing defects (student confirmed). |
| Qualitative impact | Problems found at the very end cost the most. QC and developers redo work they thought was done. |
| Quantitative impact | 0.083 / 0.917 × (6 + 34 + 1.2) ≈ 3.7 days per project. |
| Possible resolution | Get management's criteria into acceptance testing so issues show up earlier. Decided in ticket 15. |

### Issue 6: Many handoffs between teams

| Field | Value |
| --- | --- |
| Priority | 2 |
| Description | Work moves between five lanes. A project that passes every check the first time changes hands 8 times, and each loop adds 2. |
| Data and assumptions | 15 of 33 sequence flows cross a lane. PMO appears in two lanes; the student kept them as two teams. |
| Qualitative impact | Each handoff is a place where work waits and information gets lost (p.219, p.261). It also feeds issues 2 and 4. |
| Quantitative impact | Measured on the log: 27.8 days of waiting per case, 21% of the mean cycle time. The simulation only has waiting for a free resource in the next lane, not delay from the handoff itself, so this is a lower bound. |
| Possible resolution | Merge steps done by neighbouring teams, or move a task to the lane that does the next step. Decided in ticket 15. |

### Issue 7: Proposal goes back and forth

| Field | Value |
| --- | --- |
| Priority | 3 |
| Description | A proposal can be sent back for changes any number of times, and a few are rejected, some only after one or more rounds. |
| Data and assumptions | Each approval: 77% approved, 20% changes requested, 3% rejected (rejection rare, student's answer). Revise 4.7 days, approve 4.7 days. |
| Qualitative impact | The requester repeats work and the project starts later. |
| Quantitative impact | 0.2 / 0.8 × (4.7 + 4.7) ≈ 2.3 extra days per request. 0.03 / 0.8 ≈ 4% of requests end rejected (3.8% on the log). |
| Possible resolution | Screen requests at registration. Decided in ticket 15. |

### Issue 8: Plan sent back

| Field | Value |
| --- | --- |
| Priority | 3 |
| Description | IT management can return the project plan for changes, and each round needs a new approval. |
| Data and assumptions | 19% of plans need changes (measured; set at 31% for new systems, 14% for the rest). Draft 4.3 days, approve 2.3 days. |
| Qualitative impact | Build starts later; developers wait on the plan. |
| Quantitative impact | 0.19 / 0.81 × (4.3 + 2.3) ≈ 1.6 extra days per project. |
| Possible resolution | Agree the plan's limits at kick-off. Decided in ticket 15. |

Total expected rework with these parameters: about 13.2 + 3.7 + 2.3 + 1.6 ≈ 21 days of processing per project, about 24% on top of the 88 days of first-time processing up to go-live. The waiting in the extra rounds comes on top.

## 4. Objective

Target (the student's decision): reduce the mean cycle time by at least 20% versus the simulated as-is baseline, with the 95% CI of the saving excluding zero (lower bound above 0).

- Baseline on the as-is log (seed 42, 2,000 cases, cycle time up to go-live):
  - All cases, the headline: mean 132.5 working days, median 122.9, P90 198.0. Processing 104.7, waiting 27.8 (21%), cycle time efficiency 0.79.
  - Approved projects only, as a check (1,924 cases that end at "Project closed"): mean 137.3, median 124.3, P90 200.3. Waiting 28.7 (21%), cycle time efficiency 0.79.
  - The 76 rejected proposals take 12.0 days on average.
  - 20% of the all-cases mean is about 27 days.
- How it's measured:
  - cycle time = time from "Development request received" to the end of "Start live operation" (go-live), in working days. A case that ends at "Proposal rejected" ends there. Monitoring and the evaluation stay in the model but don't count. This is the `[cycle_time]` entry in the parameter file, and the baseline, flow analysis, ML and scenario runner all use it;
  - measured on all cases, with the approved-only number reported next to it;
  - same parameter file, arrival rate and random seeds for as-is and to-be (common random numbers, ticket 13);
  - met when, for the chosen design, the mean of `scenarios[].saving` is at least 20% of the as-is mean and the lower bound of its 95% CI is above 0.
- Side conditions:
  - P90 cycle time doesn't get worse;
  - no VA task is removed, and no BVA task is removed without saying which business need it served (p.218);
  - cost, quality and flexibility are reported as trade-offs only (Devil's Quadrangle, pp.303-304).
- Why 20% looks reachable:
  - Waiting is 28 days per case, 21% of the cycle time, and almost half of it sits in one lane, QC. Cycle time efficiency is 0.79, high for a real process (Table 7.4, p.263). The 27-day target is nearly all of the waiting, so shorter queues alone can't reach it; processing has to come down too.
  - Rework adds about 21 days of processing (24% of first-time processing up to go-live), plus the waiting in those extra rounds (6 days per project at the test loop alone).
  - Running the checks side by side could save about 12 days a project.
  - No single change looks big enough on its own: 27 days is a lot. Rerunning only the failed check cuts both the extra processing and QC's load, and with QC at 87% a lower load should still cut its waiting by more than the work saved. 20% most likely needs two or three changes aimed at testing. That is an expectation; the scenario runner will show it.
  - Caveat: what the QC changes save depends heavily on the assumed QC capacity (eight testers, a proposed default). With more testers in reality, the queue and the possible saving are both smaller.
  - It stays modest because 12 of 19 tasks are BVA controls we keep, and "Build application" is the biggest single task.
- Rejected proposals end early and pull the all-cases mean down. A design that rejects more, or earlier, would look faster for that reason alone. Rejection is rare now, so the effect is small, and the approved-only number shows it if a design changes the rejection rate.

## Answers at sign-off

Given by the student on 2026-11-05:

- The customer is the requesting business unit, an internal customer (§1.2, p.5).
- Borderline classes, checked against the book in `docs/analysis/value-added-borderline-tasks.md`:
  - Register request: VA, changed from BVA. It matches "Fill request" in Table 6.1 (p.217).
  - Hold kick-off: BVA. Like "communicate issues", it avoids misunderstandings (p.216).
  - Run acceptance tests: BVA. It is a control step; the business unit taking part doesn't make it VA (p.216).
  - Start live operation: BVA. The task is handover and go-live checks; "Deploy application to production" already delivers the application and is VA.
  - Refine application: NVA. It is rework after a rejected release, defect waste (p.222).
- QC (issues 1 and 2) is the main problem, ahead of the approvals queue (issue 4).
- Eight QC testers stay as the assumed capacity.

Answered earlier:

- Target: at least 20% mean saving, with the 95% CI of the saving above 0.
- Measured on all cases; approved projects only reported next to it.
- Cycle time ends at go-live; "Monitor live operation" and "Evaluate project results" don't count.
- Arrival rate: 0.234 requests per working day, which keeps QC near 88% busy.
- Change log questions 1 to 10 (see "Answered questions" in `models/as_is_changelog.md`).
