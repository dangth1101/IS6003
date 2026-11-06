// The official numbers the result panel shows, read from web/results.json (30 replications).
// No number is typed into the page: tests/test_demo.py runs this in Node against results.json.

const sameSet = (a, b) => a.length === b.length && a.every((x) => b.includes(x));

export function scenario(results, changes) {
  const s = results.scenarios.find((x) => sameSet(x.changes, changes));
  if (!s) throw new Error(`results.json has no scenario with changes [${changes.join(", ")}]`);
  return s;
}

export function figures(results) {
  const asIs = scenario(results, []);
  const full = scenario(results, results.headline.changes);
  const best = scenario(results, results.headline.best);
  const pick = (s) => ({ changes: s.changes, cycleTime: s.cycle_time.mean, saving: s.saving, share: s.saving_share });
  return {
    replications: results.meta.replications,
    cases: results.meta.case_count,
    seed: results.meta.seed,
    asIs: pick(asIs),
    full: pick(full),
    best: pick(best),
  };
}
