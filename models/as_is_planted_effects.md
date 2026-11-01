# Planted attribute effects in the as-is parameters

The event log is synthetic, so any pattern the ML finds was either put into the simulator on purpose or is noise. This page lists every effect put in `models/as_is.params.toml`, so the report and the notebook can check the ML drivers against it (spec user story 33, threats to validity).

All effects are proposed defaults, like the rest of the parameters. The same list is in `models/as_is.planted_effects.toml`, which the notebook reads. A test (`tests/test_as_is_parameters.py`) checks that file against the parameter file both ways, and this table against that file.

## Effects

Duration effects multiply the drawn duration by 1 + the terms. Branch effects add to the log-odds z of a logistic, p = 1 / (1 + e^-z).

| # | Element | Attribute | Kind | Size | Meaning |
|---|---|---|---|---|---|
| 1 | `Task_BuildApplication` | `complexity` | duration | +0.4 x base per step (1-3) | Complex apps take longer to build, about +6 days per step |
| 2 | `Task_BuildApplication` | `integrations` | duration | +0.1 x base per integration | Each connected system adds about 1.6 days |
| 3 | `Task_BuildApplication` | `team_workload` | duration | +0.6 x base x workload (0.5-1) | A busier team builds slower; workload varies little, so this is a weak effect |
| 4 | `Task_SpecifyRequirements` | `complexity` | duration | +0.3 x base per step | Complex apps need longer requirements, about +3 days per step |
| 5 | `Task_RunSecurityTests` | `security_level` | duration | +0.5 x base per level (1-3) | Critical systems get penetration tests, about +1.2 days per test round |
| 6 | `Gateway_TestSplit` | `complexity` | branch | +0.6 log-odds per step | Complex apps fail testing more often |
| 7 | `Gateway_TestSplit` | `integrations` | branch | +0.15 log-odds per integration | Integration defects |
| 8 | `Gateway_TestSplit` | `security_level` | branch | +0.5 log-odds per level | Stricter security checks find more issues. The four checks share one decision, so this acts on the whole test round |
| 9 | `Gateway_PlanSplit` | `project_type` | branch | +1.0 log-odds for `new_system` | Plans for new systems are sent back more (31% vs 14%) |
| 10 | `Gateway_ReleaseSplit` | `project_type` | branch | +1.0 log-odds for `regulatory` | Compliance rejects more regulatory releases (17% vs 7%) |

## No effect

| Attribute | Why |
|---|---|
| `requesting_unit` | Negative control. It's drawn like the others but nothing reads it. Any importance the ML gives it is noise |

`Gateway_ProposalSplit` has fixed probabilities (a three-way split can't be logistic), so no attribute predicts a revised or rejected proposal. A rework model for that split should do no better than the majority-class baseline.

Queueing adds noise that no attribute explains: waiting depends on how busy the lanes are when the case arrives, not on the case.

## What the ML should find

- Cycle time: `complexity` first, since it acts on three places (requirements, build, test failures). Then `security_level` and `integrations`. `project_type` and `team_workload` are weak and may not stand out from noise. `requesting_unit` should rank last. A quick linear fit on the 2,000-case log (closed projects, seed 42) gives about 21 days per complexity step, 12 per security level and 6 per integration, with R² of only about 0.15. Most of the variation comes from the random number of rework loops and from queueing.
- Test rework: `complexity`, `security_level`, `integrations`. Nothing else.
- Plan rework: `project_type` only (`new_system`).
- Release rework: `project_type` only (`regulatory`). Few releases are rejected, so this signal is weak.
- Proposal rework: nothing.

On a 2,000-case log the weak effects and the negative control can look alike. That is a finding to report, not a bug.
