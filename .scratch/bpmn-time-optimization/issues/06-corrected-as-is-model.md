# 06: Corrected as-is model (Phase 0)

**What to build:** A new as-is BPMN model in English that fixes the current model against the book, and lints clean. The original `current_process.bpmn` stays unchanged for reference. Changes include a pool around the lanes, event labels as object + past participle, explicit conditions instead of Có/Không, the compound test activity split into code review, functional testing, security testing and acceptance, a "Proposal rejected" end event, and verb-object activity labels. A short change log maps every change to the book rule it satisfies.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] New model lints with zero errors
- [ ] Every element of the original model is accounted for in the change log (kept, renamed, split or removed, with the reason)
- [ ] Lane of "revise proposal" is raised as an open question for the student in the change log, not silently moved
- [ ] Model opens and renders in bpmn-js
- [ ] Model uses only the simulator's supported subset
