// Read-only GitHub REST -> existing source-free merge-policy bridge.
// No GitHub write/merge action, no authenticated checkout-log verifier, no
// independent CODEOWNERS attestation. This module CANNOT authorize a merge.
import { qualifyMergeEvidence } from './merge-qualification-policy-20261106.mjs';

const SHA = /^[0-9a-f]{40}$/;
const REPO = /^ores-truffle-oreslang\/[A-Za-z0-9._-]+$/;
const goodId = n => Number.isSafeInteger(n) && n > 0;
const validSHA = s => typeof s === 'string' && SHA.test(s);
const BLOCK = (reasons, observed = {}, policy = null) =>
  ({ status: 'BLOCKED', merge_authorized: false, guest_certified: false,
     source_authenticated: false, reasons: [...new Set(reasons)], observed, policy });
const MAX_BYTES = 1024 * 1024;

export function githubRestReader({ token, fetcher = fetch, maxBytes = MAX_BYTES } = {}) {
  if (typeof token !== 'string' || !token.length || typeof fetcher !== 'function' ||
      !Number.isSafeInteger(maxBytes) || maxBytes < 256 || maxBytes > MAX_BYTES)
    throw TypeError('read-only GitHub client requires token, transport and bounded size');
  return async path => {
    // Deliberately allow only metadata needed by this audit. Never allow
    // contents/blobs/code-search, workflow logs, repository source or arbitrary
    // GitHub endpoints: a read-only token can still disclose private source.
    const route = typeof path === 'string' && /^\/repos\/ores-truffle-oreslang\/[A-Za-z0-9._-]+\/(.+)$/.exec(path);
    const suffix = route?.[1];
    const allowed = typeof suffix === 'string' && (
      /^pulls\/[1-9]\d*(?:\/reviews\?per_page=100&page=[1-8])?$/.test(suffix) ||
      /^branches\/main(?:\/protection)?$/.test(suffix) ||
      /^git\/commits\/[0-9a-f]{40}$/.test(suffix) ||
      /^actions\/runs\/[1-9]\d*(?:\/attempts\/[1-9]\d*\/jobs\?per_page=100&page=[1-8]|\/artifacts\?per_page=100&page=[1-8])?$/.test(suffix) ||
      /^commits\/[0-9a-f]{40}\/check-runs\?per_page=100&page=[1-8]$/.test(suffix) ||
      /^actions\/jobs\/[1-9]\d*$/.test(suffix)
    );
    if (!allowed || path.includes('..') || path.includes('//') ||
        path.includes('%') || path.includes('\\') || path.includes('#'))
      throw Error('READ_PATH_DENIED');
    const response = await fetcher('https://api.github.com' + path, {
      method: 'GET', redirect: 'manual', headers: {
        authorization: 'Bearer ' + token,
        accept: 'application/vnd.github+json',
        'x-github-api-version': '2022-11-28'
      }
    });
    if (!response || response.status !== 200) {
      const e = Error('GITHUB_READ_FAILED_' + (Number.isSafeInteger(response?.status) ? response.status : 'UNKNOWN'));
      e.status = response?.status ?? null;
      throw e;
    }
    const declared = Number(response.headers?.get('content-length'));
    if (Number.isFinite(declared) && declared > maxBytes) throw Error('GITHUB_BODY_TOO_LARGE');
    if (!response.body || typeof response.body.getReader !== 'function')
      throw Error('GITHUB_BODY_UNOBSERVED');
    const chunks = [], reader = response.body.getReader(); let size = 0;
    try {
      while (true) {
        const next = await reader.read();
        if (next.done) break;
        if (!(next.value instanceof Uint8Array)) throw Error('GITHUB_BODY_INVALID');
        size += next.value.byteLength;
        if (size > maxBytes) throw Error('GITHUB_BODY_TOO_LARGE');
        chunks.push(next.value);
      }
    } catch (e) {
      await reader.cancel().catch(() => {});
      throw e;
    }
    if (size === 0) throw Error('GITHUB_BODY_EMPTY');
    let parsed;
    try {
      parsed = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(
        Buffer.concat(chunks.map(c => Buffer.from(c)), size)));
    } catch { throw Error('GITHUB_BODY_INVALID_JSON'); }
    return parsed;
  };
}

async function paged(get, root, field = null, maxPages = 8) {
  if (!Number.isSafeInteger(maxPages) || maxPages < 1 || maxPages > 8)
    throw Error('INVALID_PAGE_BUDGET');
  const values = [], seen = new Set(); let done = false, declared = null;
  for (let page = 1; page <= maxPages; page++) {
    const path = root + (root.includes('?') ? '&' : '?') + 'per_page=100&page=' + page;
    const data = await get(path);
    const arr = field ? data?.[field] : data;
    if (!Array.isArray(arr) || arr.length > 100)
      throw Error('PAGINATION_SHAPE_INVALID');
    if (field) {
      if (!Number.isSafeInteger(data.total_count) || data.total_count < 0)
        throw Error('PAGINATION_COUNT_MISSING');
      if (declared !== null && declared !== data.total_count)
        throw Error('PAGINATION_TOTAL_CHANGED');
      declared = data.total_count;
    }
    for (const item of arr) {
      if (!item || typeof item !== 'object' || Array.isArray(item) ||
          !goodId(item.id) || seen.has(item.id))
        throw Error('PAGINATION_IDENTITY_INVALID');
      seen.add(item.id); values.push(item);
    }
    if (arr.length < 100) { done = true; break; }
  }
  if (!done || (declared !== null && declared !== values.length))
    throw Error('PAGINATION_INCOMPLETE');
  return values;
}

export async function inspectLiveMergeCandidate({
  get, repository, number, expectedHead, runId, attempt,
  requiredJobs, codeOwners, requiredArtifacts = []
} = {}) {
  const errors = [];
  if (typeof get !== 'function' || typeof repository !== 'string' || !REPO.test(repository) ||
      !goodId(number) || !goodId(runId) || !goodId(attempt) || !validSHA(expectedHead) ||
      !Array.isArray(requiredJobs) || requiredJobs.length === 0 ||
      !requiredJobs.every(j => j && typeof j.name === 'string' &&
        Array.isArray(j.required_steps) && j.required_steps.length > 0) ||
      !Array.isArray(codeOwners) || codeOwners.length === 0 ||
      !codeOwners.every(x => typeof x === 'string' && x.length > 0) ||
      !Array.isArray(requiredArtifacts))
    return BLOCK(['INVALID_LIVE_REQUEST']);
  const base = '/repos/' + repository;
  let pr, branch, protection, commit, run, reviews, allJobs, checks, artifacts;
  try {
    pr = await get(base + '/pulls/' + number);
    branch = await get(base + '/branches/main');
    protection = await get(base + '/branches/main/protection');
    commit = await get(base + '/git/commits/' + expectedHead);
    reviews = await paged(get, base + '/pulls/' + number + '/reviews');
    run = await get(base + '/actions/runs/' + runId);
    allJobs = await paged(get, base + '/actions/runs/' + runId +
      '/attempts/' + attempt + '/jobs', 'jobs');
    checks = await paged(get, base + '/commits/' + expectedHead + '/check-runs', 'check_runs');
    artifacts = await paged(get, base + '/actions/runs/' + runId + '/artifacts', 'artifacts');
  } catch (e) {
    return BLOCK(['LIVE_READ_INCOMPLETE', String(e?.message || 'UNKNOWN').slice(0,120)]);
  }
  const head = pr?.head?.sha, tree = commit?.tree?.sha;
  if (head !== expectedHead || commit?.sha !== expectedHead || !validSHA(tree) ||
      pr?.head?.repo?.full_name !== repository || pr?.base?.repo?.full_name !== repository ||
      pr?.base?.ref !== 'main' || pr?.state !== 'open' || pr?.draft !== false)
    errors.push('PR_OR_TREE_IDENTITY_UNVERIFIED');
  if (pr?.base?.sha !== branch?.commit?.sha || branch?.protected !== true)
    errors.push('BASE_OR_PROTECTION_UNVERIFIED');
  const rules = protection?.required_pull_request_reviews;
  const statuses = protection?.required_status_checks;
  const noBypass = rules?.bypass_pull_request_allowances &&
    ['users','teams','apps'].every(k =>
      Array.isArray(rules.bypass_pull_request_allowances[k]) &&
      rules.bypass_pull_request_allowances[k].length === 0);
  if (!noBypass || rules?.require_code_owner_reviews !== true ||
      rules?.dismiss_stale_reviews !== true ||
      !goodId(rules?.required_approving_review_count) ||
      protection?.enforce_admins?.enabled !== true ||
      statuses?.strict !== true || !Array.isArray(statuses?.checks))
    errors.push('ADMIN_POLICY_UNVERIFIED');
  const expectedNames = requiredJobs.map(j => j.name);
  if (new Set(expectedNames).size !== expectedNames.length ||
      !expectedNames.every(name => statuses?.checks?.some(c => c.context === name &&
        goodId(c.app_id) && checks.filter(x => x.name === name && x.app?.id === c.app_id &&
          x.head_sha === expectedHead && x.status === 'completed' &&
          x.conclusion === 'success').length === 1)))
    errors.push('REQUIRED_CHECK_UNVERIFIED');
  if (run?.id !== runId || run?.run_attempt !== attempt ||
      run?.head_sha !== expectedHead || run?.event !== 'pull_request' ||
      run?.repository?.full_name !== repository)
    errors.push('RUN_IDENTITY_UNVERIFIED');
  const selected = [];
  for (const req of requiredJobs) {
    const matches = allJobs.filter(j => j.name === req.name);
    if (matches.length !== 1) { errors.push('REQUIRED_JOB_AMBIGUOUS'); continue; }
    const j = matches[0];
    let detail;
    try { detail = await get(base + '/actions/jobs/' + j.id); }
    catch { errors.push('JOB_DETAIL_UNREADABLE'); continue; }
    if (JSON.stringify(detail) !== JSON.stringify(j))
      errors.push('JOB_SUMMARY_DETAIL_MISMATCH');
    selected.push(detail);
  }
  const prAgain = await get(base + '/pulls/' + number).catch(() => null);
  const branchAgain = await get(base + '/branches/main').catch(() => null);
  const protectionAgain = await get(base + '/branches/main/protection').catch(() => null);
  if (!prAgain || prAgain.head?.sha !== expectedHead ||
      prAgain.base?.sha !== pr?.base?.sha || prAgain.draft !== pr?.draft ||
      prAgain.state !== pr?.state || !branchAgain ||
      branchAgain.commit?.sha !== branch?.commit?.sha ||
      branchAgain.protected !== branch?.protected ||
      !protectionAgain ||
      JSON.stringify(protectionAgain) !== JSON.stringify(protection))
    errors.push('SOURCE_OR_GOVERNANCE_DRIFT');
  const normalizedReviews = reviews.map(r => ({
    user: r.user?.login, state: r.state, commit_id: r.commit_id,
    submitted_at: r.submitted_at
  }));
  const policyInput = {
    expected: { repository, number, head_sha: expectedHead, tree_sha: tree,
      author: pr?.user?.login, base_ref: 'main', required_jobs: requiredJobs,
      code_owners: codeOwners, required_artifacts: requiredArtifacts },
    pr: { repository, number: pr?.number, head_sha: head, author: pr?.user?.login,
      base_ref: pr?.base?.ref, state: pr?.state, draft: pr?.draft },
    branch: { name: branch?.name, protected: branch?.protected,
      enforce_admins: protection?.enforce_admins?.enabled,
      allow_bypass: noBypass !== true,
      required_pull_request_reviews: rules,
      required_status_checks: { strict: statuses?.strict,
        contexts: Array.isArray(statuses?.checks) ?
          statuses.checks.map(c => c.context) : [] } },
    run: { id: run?.id, run_attempt: run?.run_attempt, event: run?.event,
      head_sha: run?.head_sha, repository, status: run?.status, conclusion: run?.conclusion },
    jobs: selected.map(j => ({ id:j.id, name:j.name, run_id:j.run_id,
      run_attempt:j.run_attempt, head_sha:j.head_sha, status:j.status,
      conclusion:j.conclusion, runner_id:j.runner_id, steps:j.steps })),
    // GitHub job metadata does not prove the checked-out tree or job artifact
    // producer. Never synthesize these receipts from a green job/conclusion.
    checkouts: [], reviews: normalizedReviews, artifacts: []
  };
  const policy = qualifyMergeEvidence(policyInput);
  if (policy.classification !== 'CANDIDATE_QUALIFIED')
    errors.push('POLICY_' + policy.reason);
  // Additional essential guarantees require separate trusted evidence
  // collectors; this bridge never transforms self-reported data into authority.
  errors.push('CHECKOUT_RECEIPTS_NOT_AUTHENTICATED',
              'CODEOWNER_AUTHORITY_NOT_ATTESTED',
              'ARTIFACT_JOB_ORIGIN_NOT_ATTESTED',
              'SERVER_SIDE_MERGE_GATE_NOT_ENFORCED');
  return BLOCK(errors, {
    repository, number, head_sha: head, tree_sha: tree, run_id: run?.id,
    run_attempt: run?.run_attempt, review_events: reviews.length,
    job_count: selected.length,
    executed_jobs: selected.filter(j => Array.isArray(j.steps) && j.steps.length > 0 &&
      goodId(j.runner_id)).length,
    artifact_count: artifacts.length,
    branch_protected: branch?.protected === true
  }, policy);
}
