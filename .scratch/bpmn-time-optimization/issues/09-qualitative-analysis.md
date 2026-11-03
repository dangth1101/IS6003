# 09: Qualitative analysis (Phase 1)

**What to build:** Following the book's Chapter 6 on the corrected as-is model: a value-added classification (VA / BVA / NVA, §6.1) for every activity, stored as data in the `value_added` section of the results; a waste analysis (§6.2); and an issue register (§6.3.2). The objective is written as a cycle time target. The agent drafts it, the student reviews and corrects it, because it involves judgment about the real company process.

**Blocked by:** 05, 06

**Status:** ready-for-human

- [x] Every activity ID in the corrected model has exactly one classification with a one-line reason
- [x] Waste analysis uses the book's categories (move, hold, overdo)
- [x] Issue register uses the book's columns
- [x] Objective is stated as a measurable cycle time target
- [ ] Draft is marked for student review, and the student has signed off

## Comments

- Draft done, awaiting student review. Not signed off.
- Classification data: `models/as_is.value_added.toml`, one entry per task (19). Loaded by `bpmopt.value_added.load_value_added(path, model)`, which raises if a task is missing or an ID isn't a task of the model. The notebook writes it into `value_added` in `web/results.json`.
- Only tasks are classified, not gateways or events. Each task gets the class of its main step; the book classifies steps (p.213).
- Write-up: `docs/analysis/phase1-qualitative.md` (problem statement, value-added table, waste analysis, issue register with 7 issues, objective).
- Result: 3 VA, 13 BVA, 3 NVA. The 3 NVA are the rework tasks.
- Issue numbers use the placeholder parameters (`placeholder-1`) and Eq. 7.4. Recompute them after ticket 10.
- Objective proposed as "reduce mean cycle time by 20% versus the simulated as-is baseline", met when the saving's 95% CI lower bound is above 0. Revisit X after ticket 14.
- Questions the student must answer to sign off:
  - Is the customer the requesting business unit?
  - Confirm the borderline classes: Register request (BVA), Hold kick-off (BVA or NVA), Run acceptance tests (BVA or VA), Start live operation (BVA or VA), Refine application (NVA or VA, change log Q6).
  - Are issue 1 (test cycle repeats) and issue 2 (approval queue) the top priorities?
  - Is 20% the right X?
  - Measure the target on all cases or only on closed projects? Rejected proposals end early and pull the mean down.
  - Does "Monitor live operation" count in the cycle time (change log Q9)?
  - Change log Q1 to Q5 and Q7 change issues 1 to 6.
- Student answers applied (change log Q1-Q10) and method decided: cycle time ends at go-live, headline on all cases with approved-only next to it, target "mean saving at least 20% and the 95% CI of the saving above 0". The draft now says so in section 4.
- Numbers refreshed from parameters `proposed-2` (seed 42, 2,000 cases). Judgments moved with them, each listed under "Changes since first draft" at the top of `docs/analysis/phase1-qualitative.md`. Main one: QC waiting (23.9 days per case) is now issue 2 with priority 1, and the approvals queue (7.8 days) drops to issue 4, priority 2. Issues renumbered in priority order.
- The 20% reasoning is rewritten: waiting is 31% of cycle time, half of it at QC, so 20% likely needs two or three testing changes together.
- Review questions cut to the open ones, plus two new: is eight QC testers realistic, and does one request a week still fit now that few proposals are rejected.
- Still a draft. Not signed off.

