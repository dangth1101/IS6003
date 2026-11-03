# 16: Final evaluation and page

**What to build:** The notebook simulates the as-is process and every combination of the redesign changes, writes the full results, and the page shows everything with real data: both models, baseline, ML findings, change catalog, toggles, ablation, assumptions and threats to validity. The page is ready to publish on GitHub Pages.

**Blocked by:** 15

**Status:** done

- [x] Notebook runs top to bottom from a fresh kernel and produces the final results file
- [x] Results file validates against the schema
- [x] Page states the headline result as "to-be is X% faster (95% CI …)" and names the change that contributes most
- [x] Threats to validity are listed on the page
- [x] No placeholder or fake data remains on the page
- [x] Instructions for serving the page locally and on GitHub Pages are written down

## Comments

- Done. Scenario run: 2,000 cases × R=30 × 16 scenarios, seed 42, about 6 minutes; the whole notebook about 8. `jupyter execute` from a fresh kernel runs clean and writes `web/results.json`, which validates. `web/models/to_be.bpmn` is copied by `export_results`.
- Baseline vs as-is scenario: same parameter file, same 2,000 cases, same 250-day warm-up, seeds from the same seed. The baseline is one run (seed 42, mean 132.5); the as-is scenario averages 30 runs (140.8, CI 135.3 to 146.3; runs from about 124 to 200). The gap is run-to-run variation with QC at 87% busy. The page says so under the baseline tiles (`baseline_one_run`), the notebook shows where the baseline run sits among the 30.
- Headline: the full design (C1-C4) is 25.3% faster (95% CI 23.7% to 27.0%), 140.8 to 104.5 days, saving 36.3 (32.0 to 40.5). Objective (≥20%, CI above 0) met.
- Ablation (saving alone; days added if dropped from the full design, paired CI): C1 20.4 [19.4, 21.4]; 11.3 [11.1, 11.5]. C2 27.5 [23.3, 31.8]; 3.1 [2.9, 3.3]. C3 15.6 [11.7, 19.5]; -2.8 [-3.2, -2.4]. C4 13.0 [9.4, 16.6]; 0.5 [0.3, 0.7].
- "Contributes most" = largest full_minus, so C1. C2 is largest alone; the page and notebook say both. Best combination C1+C2+C4, 27.4% [25.8, 28.9]; C1+C2 26.9%. The headline still reports the full design (the approved one), and says it isn't the fastest.
- Schema v4: scenarios carry `saving_share` and `replication_means` (one per replication; must average to the mean estimate and count `meta.replications`). New sections `ablation` (full_minus now has a paired CI) and `headline` (`bpmopt.scenarios.headline`), both checked against the scenarios on validate. `build_results(..., replications=R)`. The page reads the ablation from the file instead of deriving it.
- Threats are page text: `[[threats]]` in `page.en.toml`, copied into `threats` by `build_results`. Spec's four, plus assumed change effects (C3 most), QC near its limit (with the book's sensitivity check, §7.3.4 p.287: C4 alone saves 13 days, in the full design 0.5), and G7 on the to-be models.
- Fake fixture regenerated for v4 (still flagged fake, tests only). Real page checked in headless Chrome on a local server: both diagrams draw, headline box, baseline note, toggles (C1 gives 20.4 days / 14.4%, C1+C2 38.4 / 26.9%), ablation, threats, no console errors. Fake page also loads.
- Book check: the book doesn't cover warm-up, replications or common random numbers, so the notebook says they're standard simulation practice rather than citing it.
- For the student: decide whether to keep C3 (costs about 3 days in the full design, aims at quality the model doesn't value) and whether C4's half a day is worth a salary. Publishing steps are in the README (`git subtree push --prefix web origin gh-pages`); nothing was pushed or configured.
- Review fixes (2026-11-03):
  - Saving share is now the mean saving over the as-is mean, with the saving's CI over the same mean (`scenarios.saving_share`), so the headline matches its detail line. Validation rejects a share that doesn't. The page states the method under the headline, the notebook in section 10. New headline: 25.7% faster (95% CI 22.7% to 28.8%), 140.8 to 104.5 days, saving 36.3 (32.0 to 40.5). Best combination C1+C2+C4, 27.8% (24.7% to 30.8%); toggles: C1 14.5%, C1+C2 27.3%. The CIs are wider than before because the as-is mean is treated as fixed rather than paired per run.
  - The to-be parameters (C2 retest duration, C3 requirements and Gateway_TestSplit, C4 QC capacity) are in `assumptions` with a `change` field (`Catalog.assumptions`), shown in an "Applies to" column.
  - Headline box rendered once (top of the page).
  - No results typed into page text: paragraphs and threats use placeholders the page fills from `results.json` (list at the top of `page.en.toml`); a test rejects numbers other than citations. Notebook findings print their numbers from code. Catalog drivers name the run they cite.
  - "Identical resources" threat cites §7.1.2, p.261; notebook's §7.2 p.276 is now §7.2.2.
  - `build_results(..., value_added=, ml=, catalog=, scenarios=)` assembles the evaluation sections; `find_scenario` and `full_design` are the one lookup in Python; `contract.py` holds the schema validator so `results` imports `scenarios` and not the other way round. C3 test goes through the simulator. No bold lead-ins in the notebook.
