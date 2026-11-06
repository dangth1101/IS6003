# Spec: Flow demo page, replacing the simulation studio

**Status:** ready-for-agent

## Problem Statement

The simulation studio (`web/studio/`) is an editor: you load BPMN, edit parameters and the diagram, and run Python in the browser. For the presentation the student doesn't want that. They want a demo that shows, in plain visuals and in Vietnamese:

- what the current flow looks like;
- what the improved flow looks like;
- the simulation running on each, so the audience sees projects pile up at QC in the as-is and move faster in the to-be;
- the final result.

BPMN notation is hard to read on a projector for a non-BPM audience, and the studio's 36 MB first load and editing features are a risk in a live demo. The student decided (2026-11-06) to remove the studio and build this demo instead.

## Solution

A static page `web/demo/` with no backend and no Python in the browser:

1. **Swimlane flow**, drawn as simple rounded boxes and arrows in SVG (not BPMN notation): one row per department (Nghiệp vụ / PMO, Quản lý IT, Phát triển, QC, Vận hành), tasks with Vietnamese labels, loops drawn as curved arrows with their rework rate.
2. **As-is / To-be switch.** To-be is the full design C1-C4. The changed parts are highlighted: the four checks in parallel (C1), "Kiểm thử lại phần bị lỗi" replacing the full rerun (C2), and badges for the parameter changes C3 (longer requirements analysis for risky projects) and C4 (QC 8 → 9 people).
3. **"Chạy mô phỏng"**: an animated replay of an event log produced by our real simulator. Each project is a dot. A dot sits on a task while it is being worked on and in a queue badge next to the task while it waits for a free person; rework sends it back along the loop arrow. A simulated-time clock, play/pause, speed control, and live counters (projects in progress, waiting at QC, finished, average cycle time of finished projects).
4. **Compare mode**: as-is and to-be replayed in sync, one above the other, with the same arrivals (common random numbers), so the to-be visibly finishes projects sooner.
5. **Result panel** with the official numbers from `web/results.json` (30 replications, 2,000 cases): as-is 140,8 days, to-be 104,5, saving 36,3 days, 25,7% with its 95% CI, and C1+C2+C4 at 27,8%. The replay's own counters are labelled as one sample run, so they don't get confused with the official numbers.

## User Stories

1. As the presenter, I want to open the demo from a link and have it ready at once, so that nothing can go wrong on stage.
2. As the audience, I want to see the current process as departments and steps in Vietnamese, so that I understand it without knowing BPMN.
3. As the audience, I want to see where work loops back and how often, so that I see the rework problem.
4. As the presenter, I want one switch between As-is and To-be with the changes highlighted, so that I can show what the redesign changes.
5. As the presenter, I want to press "Chạy mô phỏng" and see projects flow through, queue at QC and loop back, so that the bottleneck is visible.
6. As the presenter, I want play, pause and speed control, so that I can fit the demo into the time I have.
7. As the presenter, I want as-is and to-be running side by side with the same arrivals, so that the difference is obvious.
8. As the audience, I want the final numbers with the confidence interval, so that I see the result is real and not one lucky run.
9. As the lecturer, I want the replay to come from the same simulator as the report, so that the demo shows the method and not an invented animation.
10. As the student, I want the studio removed, so that the repo has one demo and nothing unused.
11. As the student, I want all demo text in a content file, so that wording is easy to change.

## Implementation Decisions

- **Replay data:** a Python function in the package writes `web/demo/replay.json` from `simulate` on the as-is model and on the full to-be (catalog resolve of C1-C4), same parameters and seed, so the arrivals match. It keeps the rows of one time window after warm-up (about one to one and a half simulated years, enough to show queues building) with case ID, activity ID, lane, ready, start and end time, plus each finished case's cycle time. The notebook (or a small script) regenerates it; a test checks it matches the simulator for that seed and that both scenarios share arrivals.
- **Layout of the flow:** positions of lanes and tasks are fixed in a small JS/JSON layout for the two models (as-is and full to-be), keyed by element ID, so the replay can place dots by activity ID. Labels in Vietnamese come from the content file.
- **No live computation and no Pyodide.** The result panel reads `web/results.json`.
- **Libraries:** none required beyond plain JS and SVG; if any is used, pinned from an allowed CDN.
- **Language:** Vietnamese UI, technical terms kept in English where the slides keep them (cycle time, QC, rework, As-is, To-be). Natural wording, no em dashes.
- **Studio removal:** delete `web/studio/`, `src/bpmopt/studio/`, `scripts/build_studio.py`, `tests/test_studio*.py`, studio fixtures and README sections, and the studio links/labels on the report page. Shared code the notebook or other tests still use stays. `.scratch/simulation-studio/` stays as history, with a note that the student replaced it.
- **Report page:** its evaluation section links to the demo instead of the studio.

## Testing Decisions

- Python: the replay export through its public function: matches `simulate` for the seed; same arrivals in both scenarios; window bounds respected; schema-like shape check.
- After removing the studio, the full suite passes and the notebook still runs.
- Browser acceptance in headless Chrome: page loads with no console errors, switch works, replay plays and finishes, compare mode shows both, result numbers match `web/results.json`, readable at 1366 px and at 390 px with no horizontal scroll.

## Out of Scope

- Editing the model, importing files, live simulation in the browser.
- Toggling individual changes C1-C4 (the student chose an As-is / To-be switch).
- ML on the demo page.

## Further Notes

- The demo is for the presentation's 3-minute buffer and slide 10. Slide 10 of `docs/presentation/` gets a screenshot of the demo instead of the studio.
