# Value-added class of five borderline tasks

Five tasks in `models/as_is.bpmn` where the VA / BVA / NVA call in `docs/analysis/phase1-qualitative.md` (section 1) was open. Book: Dumas et al., *Fundamentals of BPM*, 2nd ed., §6.1 (pp.213-218) and §6.2.3 (pp.222-223), printed page numbers. The book covers all five cases, so no secondary sources are used.

## The rules used

- Customer: "the one who consumes the output is called the customer ... In this example, the customer is an employee of the organization (internal customer)" (p.5, not p.3; p.3 is where Example 1.1 starts). Here that is the business unit that asked for the application.
- VA: "Would the customer be willing to pay for this step? ... if we remove this step, would the customer perceive that the outcome of the process is less valuable?" (p.214)
- BVA: "necessary or useful for the business to run smoothly ... Does it reduce risk of business losses? Is this step required in order to comply with regulatory requirements?" (p.215)
- NVA: "The step does not fall into any of the other two categories." (p.215)
- The book classifies steps, not tasks: "a step may be a task in the process or part of a task" (p.213). Where a task mixes steps, the class below is that of the step that takes most of the time.
- The book finds the steps "by means of observation and interviewing" (p.214). So where the class turns on what people actually do, that is a question for the student, not something the book settles.
- Page note: the "printed = PDF − 24" offset holds in chapter 6 (p.216 is PDF page 240) but not in chapter 1 (p.5 is PDF page 33).

## 1. Register development request

Recommended: VA (draft says BVA).

- The parameter file describes the task as "Filling in the request form and logging it, about a day" (`models/as_is.params.toml`). So it holds two steps: the business unit writes down what it needs, and the PMO logs it.
- The book classes writing the request as VA: "Arguably, filling the request is VA insofar as the site engineer cannot expect the equipment to be rented if they do not ask for it. In one way or another, the site engineer has to request the equipment in order to obtain it." (p.216; Table 6.1, "Fill request ... VA", p.217)
- The university admission solution does the same: "VA: receive online application, evaluate academic admissibility, send notification to student" (Solution 6.1, p.244).
- The logging part on its own is BVA, like "Record recommended equipment & supplier", which "helps the company to keep track" (p.216). That is what the draft's reason describes, but it is the smaller step.
- Case for keeping BVA: the start event is "Development request received", which suggests the request already exists before the task. If the business unit writes it before the process starts and this task is only the PMO's intake and log, the main step is record keeping, and BVA is right.
- Left to judgment: yes. The book itself says "arguably", and the answer depends on which step fills the day. Worth one question to the student: does the business unit write the request inside this task, or before it?

## 2. Hold project kick-off

Recommended: BVA (as in the draft).

- The closest step in the book is the works engineer telling the clerk about issues with a request: "This communication is another step and it is BVA since it contributes to identifying and avoiding misunderstandings within the company." (p.216)
- A kick-off does the same job: business unit and IT agree on scope, roles and dates before work starts. Removing it would not make the application less useful to the business unit, but it raises the risk of building the wrong thing, which is the BVA question "Does it reduce risk of business losses?" (p.215)
- Case for NVA: the kick-off sits right after IT management approves the proposal and moves the project from the IT management lane to the business unit lane. If the meeting is mostly passing the approved proposal on, it is a handoff, and "steps associated to handoffs between process participants, such as sending and receiving internal messages, are NVA" (p.216). Waiting for a meeting slot would be waiting waste (pp.221-222), not part of the task's class.
- Left to judgment: yes. The book has no rule for meetings. BVA holds as long as the meeting actually aligns people; if it is a formality, NVA is the honest call.

## 3. Run acceptance tests

Recommended: BVA (as in the draft).

- The book defines a control step as "a step where a process participant or a software application checks that something has been done correctly" and says "Control steps are generally BVA." (p.216) Acceptance testing checks the built application against the request, so it is a control step by this definition.
- Who does the step doesn't set its class. Table 6.1 lists "Send request to clerk", performed by the site engineer (the customer), as NVA (p.217). The test is what the step contributes, not whether the customer takes part.
- Apply the VA question (p.214): if the acceptance test were removed and the application would have passed anyway, the business unit gets the same application. What the test buys is lower risk of shipping the wrong thing, which is the BVA question on p.215.
- Case for VA: the business unit sees the application for the first time here and may value that enough "to keep conducting business with us" (p.214). And Solution 6.1 classes one check, "evaluate academic admissibility", as VA (p.244). But that check produces the admission decision the applicant is waiting for. An acceptance test produces a pass or fail, not the application.
- Left to judgment: a little. "Generally" leaves room, but the book gives no reason to treat this check differently from the other three in the same block.
- Not part of the class, but useful for the redesign: a failed acceptance test that sends the work back for fixes is defect waste (p.222), and the earlier checks rerunning after it is overprocessing (pp.222-223).

## 4. Start live operation

Recommended: BVA (as in the draft), if users can already work in the application after "Deploy application to production". VA if they can't.

- The parameter file describes the task as "Handover to operations and go-live checks". Go-live checks are control steps, "generally BVA" (p.216). The handover gives IT operations what it needs to run the application, which is about the business running smoothly (p.215).
- The book's convention for formal steps: "documentation and control steps imposed by accounting or legal requirements are BVA" (p.217). A formal go-live decision required by the bank's own rules fits this.
- Case for VA: the book classes the step that actually delivers the outcome as VA. "Sending the PO is value adding: It is this act that makes the supplier know when the equipment has to be delivered" (p.216), and "send notification to student" is VA in Solution 6.1 (p.244). The outcome in phase 1 is "a working, secure application in live operation". If go-live is the moment users get access (accounts turned on, old system switched off, announcement sent), then that step is the "Send PO" of this process and is VA.
- The draft's own reasons need to agree with each other here. "Deploy application to production" is VA because "the customer gets no value before this". If that is true, go-live adds no value for the business unit and BVA is right. If the real switch to users happens at go-live, then go-live should be VA and deploy is the technical step before it.
- That cycle time ends at this task is not an argument either way. The book classes steps by what they contribute to the outcome (p.214), not by where they sit in the timeline.
- Left to judgment: yes, and it turns on a fact the book can't give. Question for the student: after deployment, can business users log in and work before the go-live step?

## 5. Refine application

Recommended: NVA (as in the draft).

- The book's rule: "Defect waste refers to all work performed in order to correct, repair, or compensate for a defect in a process. Defect waste encompasses rework, meaning situations where we have to perform again a task that we have previously executed in the same case, because of a defect the first time the task was performed." (p.222)
- Its example is almost this case: "an example of a defect waste is when a travel requisition request is sent back by the approver to the requestor for revision because some data was missing." (p.222) Here IT management rejects the release and sends it back to development for changes.
- The student is right that refining is different work from fixing defects, and the model keeps them apart. But the book's defect waste isn't limited to fixing bugs. It covers "all work" done to "compensate for a defect in a process", and a release that the approver sends back is such a defect. The same rule already makes "Revise project proposal" NVA, so both loops stay consistent.
- Overprocessing also applies: after the refinement, the whole test block and the release approval run again on work that already passed once (pp.222-223). That is extra waste around the task, not a reason to change its class.
- Case for VA: if the rejection brings features the business unit genuinely wants and that nobody could have known at requirements time, the work makes the application more useful, like "Build application". But the release is approved by IT management (the change advisory board, per the parameter file), not by the business unit, so the changes asked there are more likely control or operational concerns than new scope. And scope that was missing at release usually means the requirements step had a defect, which is exactly what p.222 calls compensating for a defect.
- Left to judgment: only on the fact of what the changes are. If the student says most refinements are new scope from the business unit, the better fix is to model them as a change request, not to call a rework loop VA.

## Recommendations

| Task | Draft | Recommended | Changes? | Task time per case up to go-live (simulated log) |
| --- | --- | --- | --- | --- |
| Register development request | BVA | VA | Yes | 1.17 days |
| Hold project kick-off | BVA | BVA | No | 1.13 days |
| Run acceptance tests | BVA | BVA | No | 7.77 days |
| Start live operation | BVA | BVA (VA if users get access only at go-live) | No, pending one question | 1.12 days |
| Refine application | NVA | NVA | No | 0.52 days |

## What changes in the numbers

Only "Register development request" moves, from BVA to VA.

- Task counts go from 3 / 13 / 3 to 4 / 12 / 3 (VA / BVA / NVA).
- Time per class on the simulated log (seed 42, 2,000 cases, up to go-live), checked by running `bpmopt.value_added.time_per_class` with the one class changed:
  - now: VA 51.8 days (49%), BVA 48.3 (46%), NVA 4.6 (4%)
  - after: VA 53.0 days (51%), BVA 47.1 (45%), NVA 4.6 (4%)
- First-pass path in phase 1 section 1 (88 days of processing): about 1.2 days moves from BVA to VA, so roughly 55 VA (about 63%) and 33 BVA instead of 54 (61%) and 34.
- Nothing else moves. The simulation, baseline, ML and scenarios don't read the classes; the classes only go into the `value_added` table (notebook cell 19), the `value_added` section of `web/results.json` and the activity colours on the page.
- So a rerun is needed only to refresh those outputs after editing `models/as_is.value_added.toml`, plus the table row and the two count and time bullets in `docs/analysis/phase1-qualitative.md` section 1. All other results stay the same with the same seed.
- If the student's answer flips "Start live operation" to VA as well: 5 / 11 / 3, and another 1.1 days per case moves from BVA to VA (about 54.1 VA, 46.0 BVA). The biggest swing in the table would be acceptance tests (7.8 days), which is why it matters that the book's control-step rule keeps it in BVA.
