const test = require('node:test');
const assert = require('node:assert/strict');
let qualifyMergeEvidence;
test.before(async () => {
  ({ qualifyMergeEvidence } = await import('../tools/merge-qualification-policy-20261106.mjs'));
});

function fixture() {
  const head = 'a'.repeat(40), tree = 'b'.repeat(40);
  const steps = [
    { number: 1, name: 'Exact source checkout', status: 'completed', conclusion: 'success' },
    { number: 2, name: 'Run security tests', status: 'completed', conclusion: 'success' }
  ];
  return {
    expected: { repository: 'ores-truffle-oreslang/example', number: 7, head_sha: head,
      tree_sha: tree, author: 'author', base_ref: 'main',
      required_jobs: [{ name: 'test', required_steps: ['Exact source checkout', 'Run security tests'] }],
      code_owners: ['other-reviewer'], required_artifacts: ['test-receipt'] },
    pr: { repository: 'ores-truffle-oreslang/example', number: 7, head_sha: head,
      author: 'author', base_ref: 'main', state: 'open', draft: false },
    branch: { name: 'main', protected: true, enforce_admins: true, allow_bypass: false,
      required_pull_request_reviews: { required_approving_review_count: 1,
        require_code_owner_reviews: true, dismiss_stale_reviews: true },
      required_status_checks: { strict: true, contexts: ['test'] } },
    run: { id: 51, run_attempt: 2, event: 'pull_request', head_sha: head,
      repository: 'ores-truffle-oreslang/example', status: 'completed', conclusion: 'success' },
    jobs: [{ id: 71, name: 'test', run_id: 51, run_attempt: 2, head_sha: head,
      status: 'completed', conclusion: 'success', runner_id: 5, steps }],
    checkouts: [{ run_id: 51, run_attempt: 2, job_id: 71, step_number: 1,
      head_sha: head, tree_sha: tree }],
    reviews: [{ user: 'other-reviewer', state: 'APPROVED',
      commit_id: head, submitted_at: '2026-11-06T21:00:00Z' }],
    artifacts: [{ name: 'test-receipt', run_id: 51, run_attempt: 2, job_id: 71,
      head_sha: head, sha256: 'c'.repeat(64), size: 42 }]
  };
}

test('valid candidate remains offline-only and guest-unproven', () => {
  const x = qualifyMergeEvidence(fixture());
  assert.equal(x.classification, 'CANDIDATE_QUALIFIED');
  assert.equal(x.qualified, true);
  assert.equal(x.compiler_guest_parity, false);
});
test('all independently required negative mutations fail closed', () => {
  const mutants = [
    x => { x.pr.head_sha = 'c'.repeat(40); },
    x => { x.pr.draft = true; },
    x => { x.branch.protected = false; },
    x => { x.branch.enforce_admins = false; },
    x => { x.branch.allow_bypass = true; },
    x => { x.branch.required_pull_request_reviews.require_code_owner_reviews = false; },
    x => { x.branch.required_pull_request_reviews.dismiss_stale_reviews = false; },
    x => { x.branch.required_status_checks.contexts = []; },
    x => { x.branch.required_status_checks.strict = false; },
    x => { x.run.head_sha = 'c'.repeat(40); },
    x => { x.run.run_attempt = 3; },
    x => { x.run.event = 'workflow_dispatch'; },
    x => { x.jobs[0].runner_id = 0; },
    x => { x.jobs[0].steps = []; },
    x => { x.jobs[0].steps = null; },
    x => { x.jobs[0].run_attempt = 3; },
    x => { x.jobs[0].head_sha = 'c'.repeat(40); },
    x => { x.jobs[0].steps[1].conclusion = 'failure'; },
    x => { x.jobs[0].steps[1].name = 'Unrelated step'; },
    x => { x.jobs[0].steps[1].number = 1; },
    x => { x.checkouts[0].tree_sha = 'c'.repeat(40); },
    x => { x.checkouts[0].run_attempt = 3; },
    x => { x.checkouts[0].step_number = 5; },
    x => { x.checkouts = []; },
    x => { x.reviews = []; },
    x => { x.reviews[0].user = 'author'; },
    x => { x.reviews[0].user = 'unknown-user'; },
    x => { x.reviews[0].commit_id = 'c'.repeat(40); },
    x => { x.reviews[0].state = 'COMMENTED'; },
    x => { x.reviews[0].submitted_at = '2026-02-30T21:00:00Z'; },
    x => { x.reviews[0].submitted_at = '2026-11-06T25:00:00Z'; },
    x => { x.artifacts = []; },
    x => { x.artifacts[0].sha256 = 'untrusted'; },
    x => { x.artifacts[0].head_sha = 'c'.repeat(40); },
    x => { x.artifacts[0].job_id = 99; },
    x => { x.artifacts[0].size = 0; },
    x => { x.jobs.push(structuredClone(x.jobs[0])); },
    x => { x.reviews.push({ ...x.reviews[0], state: 'CHANGES_REQUESTED', submitted_at: '2026-11-06T22:00:00Z' }); },
    x => { x.reviews.push({ ...x.reviews[0], state: 'DISMISSED', submitted_at: '2026-11-06T22:00:00Z' }); },
    x => { x.reviews.push({ ...x.reviews[0], commit_id: 'd'.repeat(40), submitted_at: '2026-11-06T22:00:00Z' }); },
    x => { x.reviews.push({ ...x.reviews[0], user: 'outside-reviewer', state: 'CHANGES_REQUESTED', submitted_at: '2026-11-06T22:00:00Z' }); },
    x => { x.reviews.push(structuredClone(x.reviews[0])); }
  ];
  for (const [i, mutate] of mutants.entries()) {
    const x = fixture();
    mutate(x);
    assert.notEqual(qualifyMergeEvidence(x).classification, 'CANDIDATE_QUALIFIED', 'mutation ' + i);
  }
  assert.equal(mutants.length, 42);
});
test('no steps on a failed run is admission evidence, never test success', () => {
  for (const steps of [[], null]) {
    const x = fixture();
    x.run.conclusion = 'failure';
    x.jobs[0].conclusion = 'failure';
    x.jobs[0].runner_id = 0;
    x.jobs[0].steps = steps;
    const result = qualifyMergeEvidence(x);
    assert.equal(result.classification, 'RUNNER_ADMISSION_BLOCKED');
    assert.equal(result.qualified, false);
  }
});
test('executed test failure is not classified as runner admission failure', () => {
  const x = fixture();
  x.run.conclusion = 'failure';
  x.jobs[0].conclusion = 'failure';
  x.jobs[0].steps[1].conclusion = 'failure';
  assert.equal(qualifyMergeEvidence(x).classification, 'UNVERIFIED');
});
test('bounded exhaustive mutation matrix: every failed control denies', () => {
  const flags = [
    x => { x.branch.protected = false; },
    x => { x.branch.enforce_admins = false; },
    x => { x.branch.allow_bypass = true; },
    x => { x.branch.required_pull_request_reviews.require_code_owner_reviews = false; },
    x => { x.branch.required_pull_request_reviews.dismiss_stale_reviews = false; },
    x => { x.run.head_sha = 'd'.repeat(40); },
    x => { x.jobs[0].runner_id = 0; },
    x => { x.checkouts[0].tree_sha = 'd'.repeat(40); },
    x => { x.reviews[0].user = 'author'; },
    x => { x.artifacts[0].sha256 = 'bad'; }
  ];
  for (let mask = 0; mask < (1 << flags.length); mask++) {
    const x = fixture();
    flags.forEach((fn, i) => { if ((mask & (1 << i)) !== 0) fn(x); });
    const result = qualifyMergeEvidence(x);
    assert.equal(result.qualified, mask === 0, 'mask=' + mask);
  }
});
