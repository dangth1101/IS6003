# As-is model: change log

What changed from `current_process.bpmn` (kept unchanged for reference) to `models/as_is.bpmn`, and which book rule each change follows. Book: Dumas et al., *Fundamentals of BPM*, 2nd ed., printed page numbers.

The new model lints with no errors and no warnings and has 30 flow nodes, the G7 limit (§5.4.4 p.193).

## Whole model

| Change | Rule |
| --- | --- |
| Process `Process_AppDev_ASIS` is now `Process_AppDevelopment_AsIs` inside pool `Participant_Bank` ("Bank"), with the lanes inside the pool | Lanes sit in a pool (§3.4) |
| All labels in English | Project rule (CLAUDE.md), translation later |
| XOR splits have no label; the question moved onto the outgoing arcs as conditions | Avoid labeling XOR splits, use explicit conditions (§5.4.3 p.190, §3.2.1 p.80) |
| Every loop-back now enters an explicit XOR join instead of an activity with two incoming arcs | Rework block = XOR join, body, XOR split (Fig. 7.8 p.260); structured blocks (p.185, G4 p.192) |
| New element IDs in one style (`Task_*`, `Gateway_*`, `Start_*`, `End_*`, `Lane_*`) so later tickets can key parameters by readable IDs | Our choice |

## Lanes

| Original | New | What |
| --- | --- | --- |
| `lane_bu` "Đơn vị nghiệp vụ / PMO" | `Lane_BusinessUnit` "Business unit / PMO" | Renamed |
| `lane_ld` "CNTT" | `Lane_ITManagement` "IT management" | Renamed. Read as IT management because it holds all approvals (see open questions) |
| `lane_dev` "PTUD" | `Lane_Development` "Application development" | Renamed |
| `lane_qa` "QC/ Đơn vị nghiệm thu" | `Lane_QualityControl` "QC / Acceptance unit" | Renamed |
| `lane_ops` "ITO / HTUD / PMO" | `Lane_ITOperations` "IT operations / App support / PMO" | Renamed |

## Flow nodes

| Original | New | What | Rule |
| --- | --- | --- | --- |
| `start` "Bắt đầu" | `Start_RequestReceived` "Development request received" | Renamed | Event = object + past participle (§3.1 p.77, p.190) |
| `request` "Lưu / tiếp nhận yêu cầu" | `Task_RegisterRequest` "Register development request" | Renamed | Verb-object (G6 p.193) |
| `approve` "Phê duyệt thực hiện dự án" | `Task_ApproveProposal` "Approve project proposal" | Renamed; now fed by XOR join `Gateway_ProposalJoin` | G6; rework block (p.260) |
| `g1` "Được phê duyệt?" | `Gateway_ProposalSplit` | Label removed; three conditions: "proposal approved", "changes requested", "proposal rejected" | p.190; G3 |
| (none) | `End_ProposalRejected` "Proposal rejected" | Added. Before, a proposal could only loop back, so a never-approved request could cycle forever | One end event per outcome (G3 p.192); always end with an end event (p.81); livelock (p.185) |
| `revise` "Bổ sung / điều chỉnh đề xuất" | `Task_ReviseProposal` "Revise project proposal" | Renamed. **Kept in the IT operations lane on purpose**, see open question 1 | G6 |
| `kick` "Kick-off dự án" | `Task_HoldKickOff` "Hold project kick-off" | Renamed | G6 |
| `spec` "Đặc tả yêu cầu nghiệp vụ và kỹ thuật" | `Task_SpecifyRequirements` "Specify business and technical requirements" | Renamed | G6 |
| `plan` "Lập kế hoạch dự án chi tiết" | `Task_DraftPlan` "Draft detailed project plan" | Renamed; now fed by XOR join `Gateway_PlanJoin` | G6; p.260 |
| `planapprove` "Phê duyệt kế hoạch" | `Task_ApprovePlan` "Approve project plan" | Renamed | G6 |
| `g2` "Kế hoạch đạt?" | `Gateway_PlanSplit` | Label removed; conditions "plan approved", "plan needs changes" | p.190 |
| `build` "Xây dựng ứng dụng" | `Task_BuildApplication` "Build application" | Renamed | G6 |
| `test` "Kiểm tra mã nguồn, kiểm thử, ATBM và nghiệm thu" | `Task_ReviewSourceCode`, `Task_RunFunctionalTests`, `Task_RunSecurityTests`, `Task_RunAcceptanceTests` | Split into four tasks in sequence, same order as the original label. Fed by XOR join `Gateway_TestJoin` | One verb + one object per activity (§3.1 p.77, G6); each check gets its own time (§7.1) |
| `g3` "Kiểm thử / nghiệm thu đạt?" | `Gateway_TestSplit` | Label removed; conditions "all tests passed", "defects found" | p.190 |
| `fix` "Khắc phục lỗi / hoàn thiện ứng dụng" | `Task_FixDefects` "Fix defects" and `Task_RefineApplication` "Refine application" | Split along the slash in the original label. "Fix defects" follows a failed test, "Refine application" follows a rejected release | G4 structured (p.192); see trade-off 2 |
| `appapprove` "Phê duyệt ứng dụng" | `Task_ApproveRelease` "Approve application release" | Renamed; reached through XOR join `Gateway_ReleaseJoin` on the rework path | G6 |
| `g4` "Ứng dụng được duyệt?" | `Gateway_ReleaseSplit` | Label removed; conditions "release approved", "release rejected" | p.190 |
| `deploy` "Triển khai lên môi trường Live" | `Task_DeployApplication` "Deploy application to production" | Renamed | G6 |
| `operate` "Đưa vào vận hành chính thức" | `Task_StartOperation` "Start live operation" | Renamed | G6 |
| `monitor` "Giám sát vận hành" | `Task_MonitorOperation` "Monitor live operation" | Renamed | G6 |
| `review` "Lưu hồ sơ, đánh giá hiệu quả và cải tiến" | `Task_EvaluateProject` "Evaluate project results" | Renamed, kept as one task. Archiving and improvement are folded in (see trade-off 4) | G6 |
| `end` "Kết thúc" | `End_ProjectClosed` "Project closed" | Renamed | Event = object + past participle (p.77, p.190) |

## Sequence flows

| Original | New | What |
| --- | --- | --- |
| `Flow_1` | `Flow_RequestReceived` | Kept |
| `Flow_2` | `Flow_RequestRegistered` | Now ends at `Gateway_ProposalJoin` instead of the approval task |
| `Flow_3` | `Flow_ProposalDecided` | Kept |
| `Flow_4` "Có" | `Flow_ProposalApproved` "proposal approved" | Yes/no replaced by a condition (p.190) |
| `Flow_5` "Không" | `Flow_ProposalChangesRequested` "changes requested" | Same; a third arc `Flow_ProposalRejected` goes to the new end event |
| `Flow_6` | `Flow_ProposalRevised` | Now ends at `Gateway_ProposalJoin` |
| `Flow_7` | `Flow_KickOffHeld` | Kept |
| `Flow_8` | `Flow_RequirementsSpecified` | Now ends at `Gateway_PlanJoin` |
| `Flow_9` | `Flow_PlanDrafted` | Kept |
| `Flow_10` | `Flow_PlanDecided` | Kept |
| `Flow_11` "Có" | `Flow_PlanApproved` "plan approved" | Condition (p.190) |
| `Flow_12` "Không" | `Flow_PlanChangesRequested` "plan needs changes" | Condition; now ends at `Gateway_PlanJoin` |
| `Flow_13` | `Flow_ApplicationBuilt` | Now ends at `Gateway_ReleaseJoin` |
| `Flow_14` | `Flow_AcceptanceTested` | Kept, from the last of the four checks |
| `Flow_15` "Có" | `Flow_TestsPassed` "all tests passed" | Condition (p.190) |
| `Flow_16` "Không" | `Flow_DefectsFound` "defects found" | Condition (p.190) |
| `Flow_17` | `Flow_DefectsFixed` | Now ends at `Gateway_TestJoin` |
| `Flow_18` | `Flow_ReleaseDecided` | Kept |
| `Flow_19` "Có" | `Flow_ReleaseApproved` "release approved" | Condition (p.190) |
| `Flow_20` "Không" | `Flow_ReleaseRejected` "release rejected" | Condition; now goes to `Task_RefineApplication` |
| `Flow_21` | `Flow_ApplicationDeployed` | Kept |
| `Flow_22` | `Flow_OperationStarted` | Kept |
| `Flow_23` | `Flow_OperationMonitored` | Kept |
| `Flow_24` | `Flow_ProjectEvaluated` | Kept |

New flows with no original: `Flow_ProposalSubmitted`, `Flow_ProposalRejected`, `Flow_PlanStarted`, `Flow_ReleaseCandidateReady`, `Flow_TestsStarted`, `Flow_CodeReviewed`, `Flow_FunctionsTested`, `Flow_SecurityTested`, `Flow_ApplicationRefined`.

## Trade-offs

The model sits exactly at G7's 30 flow nodes, so every extra node had to pay for itself.

1. **The four checks run in sequence, not in parallel.** An AND block around code review, functional and security testing costs two gateways and gives 31 nodes. The original label lists them one after another, so sequence is also the closer reading. If they really run in parallel, the as-is cycle time is overstated (open question 3). Running them in parallel is a natural redesign candidate for ticket 15.
2. **Two rework tasks instead of one shared "fix" task.** In the original, failed tests and a rejected release both go to the same `fix` task. Keeping that needs an extra XOR join (29 nodes) but gives an unstructured cycle, which the book's flow analysis can't reduce (§7.1.7 p.272). Two tasks give nested rework blocks: 30 nodes, structured (G4), and the flow analysis works on it.
3. **One test decision after all four checks**, as in the original. A decision per check would be more realistic (a failed code review doesn't wait for acceptance testing) but adds at least four nodes (three more splits and a join in front of the fix task).
4. **"Evaluate project results" stays one task** even though the original label has three actions (archive records, evaluate, improve). Splitting it needs nodes we don't have, and its time isn't on the critical question.
5. **The to-be model has no slack.** Ticket 15 must stay at 30 flow nodes too, or decompose. Sub-processes are outside the simulator's subset, so decomposing means removing elements, not collapsing them.

## Open questions for the student

1. **Lane of "Revise project proposal".** The original puts it in "ITO / HTUD / PMO" (IT operations). Usually the requester, i.e. the business unit / PMO lane, revises its own proposal. It's kept where the original has it. Which lane is right? It decides whose capacity the revision uses and where its waiting time shows up.
2. **When is a proposal rejected outright?** The original has no rejection at all. The model now has three outcomes at the approval step (approved, changes requested, rejected). Is that how it works, or is a proposal only dropped after several revision rounds? Can a plan or a release also be cancelled? The model says no: they only loop back.
3. **Do the four checks run in sequence?** Modeled as code review → functional tests → security tests → acceptance tests. Do some run at the same time?
4. **After a failed check, what reruns?** Modeled as all four checks again, like the original (`fix` → `test`). Or only the check that failed?
5. **Who does each check?** All four sit in the QC / Acceptance unit lane, as in the original. Is code review done by developers, and acceptance by the business unit?
6. **Is "Refine application" different work from "Fix defects"?** The split follows the slash in the original label "Khắc phục lỗi / hoàn thiện ứng dụng". If it's the same work done by the same people, say so; the durations can then be equal.
7. **Is "CNTT" IT management?** The lane holds all three approvals, and its original ID `lane_ld` suggests leadership (lãnh đạo).
8. **PMO is in two lanes** ("Đơn vị nghiệp vụ / PMO" and "ITO / HTUD / PMO"). Is it one team? If so, the two lanes share capacity, which the simulator can't express yet.
9. **How long is "Monitor live operation"?** Is it a fixed warranty period before the project closes, or open-ended? It decides whether it belongs in the cycle time at all.
10. **Pool name.** "Bank" is a generic stand-in, since the spec uses no real company data. Change it if the report names the organization differently.
