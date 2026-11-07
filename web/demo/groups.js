// The groups the "Phân nhóm" view shows, read from the `clusters` section of web/results.json.
// No number is typed into the page: tests/test_demo.py runs this in Node against results.json.

// A group is named after the loops its cases take: a gateway counts when its cases loop back
// there at least this often on average.
export const LOOP_NAME_MIN = 0.5;

/** Case groups, slowest first: size, mean cycle time, the loops that name it, rejected share and profile. */
export function caseGroups(results) {
  const cases = results.clusters.cases;
  const total = cases.groups.reduce((sum, g) => sum + g.case_count, 0);
  return cases.groups
    .map((g) => ({
      id: g.id,
      cases: g.case_count,
      share: g.case_count / total,
      days: g.cycle_time.mean,
      loops: g.loops.filter((l) => l.mean >= LOOP_NAME_MIN).map((l) => l.gateway_id),
      ends: g.outcomes,
      profile: g.profile,
    }))
    .sort((a, b) => b.days - a.days || a.id - b.id);
}

/** Mean cycle time over every case of the run the groups come from (the baseline run). */
export function overallDays(results) {
  return results.baseline.cycle_time.mean;
}

/** The case IDs of each group, and every point, for the scatter. */
export function casePoints(results) {
  return results.clusters.cases.points;
}

/** Activity groups: activity ID -> group, and the number of groups. */
export function activityGroups(results) {
  const a = results.clusters.activities;
  return { k: a.k, of: Object.fromEntries(a.points.map((p) => [p.activity_id, p.group])) };
}

/** What step 3 leads with, read off the groups: the clean path, the slowest group, the QC loop and the attributes of the slow groups. */
export function findings(results) {
  const rows = caseGroups(results);
  const overall = overallDays(results);
  const clean = rows.find((g) => g.loops.length === 0) ?? null;
  const slowest = rows[0];
  const qc = rows.filter((g) => g.loops.includes("Gateway_TestSplit"));
  const slow = rows.filter((g) => g.days > overall);
  return {
    clean: clean && { share: clean.share, days: clean.days },
    slowest: { loops: slowest.loops, days: slowest.days, ratio: clean ? slowest.days / clean.days : null },
    qc: clean && qc.length ? {
      share: qc.reduce((sum, g) => sum + g.share, 0),
      low: Math.min(...qc.map((g) => g.days)) - clean.days,
      high: Math.max(...qc.map((g) => g.days)) - clean.days,
    } : null,
    features: [...new Set(slow.flatMap((g) => g.profile.map((p) => p.feature)))],
  };
}
