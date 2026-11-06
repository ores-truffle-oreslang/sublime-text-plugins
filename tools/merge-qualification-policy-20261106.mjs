#!/usr/bin/env node
// Source-free, offline candidate gate. Do NOT equate self-reported JSON with
// authenticated GitHub evidence, branch enforcement or compiled guest parity.
import { openSync, closeSync, fstatSync, readSync, constants } from 'node:fs';
import { pathToFileURL } from 'node:url';

const SHA = /^[0-9a-f]{40}$/;
const SHA256 = /^[0-9a-f]{64}$/;
const obj = x => x !== null && typeof x === 'object' && !Array.isArray(x);
const id = x => Number.isSafeInteger(x) && x > 0;
const isSha = x => typeof x === 'string' && SHA.test(x);
const str = x => typeof x === 'string' && x.length > 0 && x.trim() === x;
const unique = arr => new Set(arr).size === arr.length;
const denied = reason => ({ classification: 'UNVERIFIED', qualified: false, reason, compiler_guest_parity: false });
const blocked = reason => ({ classification: 'RUNNER_ADMISSION_BLOCKED', qualified: false, reason, compiler_guest_parity: false });

function strictUtc(value) {
  if (typeof value !== 'string') return false;
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$/.exec(value);
  if (!m) return false;
  const [year, month, day, hour, minute, second] = m.slice(1).map(Number);
  if (year < 1970 || year > 9999 || month < 1 || month > 12 || day < 1 ||
      hour > 23 || minute > 59 || second > 59) return false;
  const d = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
  return d.getUTCFullYear() === year && d.getUTCMonth() + 1 === month &&
    d.getUTCDate() === day && d.getUTCHours() === hour &&
    d.getUTCMinutes() === minute && d.getUTCSeconds() === second;
}

export function qualifyMergeEvidence(input) {
  if (!obj(input)) return denied('INVALID_BUNDLE');
  const { expected: e, pr, branch: b, run, jobs, checkouts, reviews, artifacts } = input;
  if (![e, pr, b, run].every(obj) || !Array.isArray(jobs) ||
      !Array.isArray(checkouts) || !Array.isArray(reviews) || !Array.isArray(artifacts))
    return denied('INCOMPLETE_BUNDLE');
  if (!str(e.repository) || !id(e.number) || !isSha(e.head_sha) ||
      !isSha(e.tree_sha) || !str(e.author) || !str(e.base_ref) ||
      !Array.isArray(e.required_jobs) || e.required_jobs.length === 0 ||
      !e.required_jobs.every(j => obj(j) && str(j.name) && Array.isArray(j.required_steps) &&
        j.required_steps.length > 0 && j.required_steps.every(str) && unique(j.required_steps)) ||
      !unique(e.required_jobs.map(j => j.name)) ||
      !Array.isArray(e.code_owners) || e.code_owners.length === 0 ||
      !e.code_owners.every(str) || !unique(e.code_owners.map(x => x.toLowerCase())) ||
      !Array.isArray(e.required_artifacts) ||
      !e.required_artifacts.every(str) || !unique(e.required_artifacts))
    return denied('INVALID_EXPECTATIONS');
  if (pr.number !== e.number || pr.repository !== e.repository ||
      pr.head_sha !== e.head_sha || pr.author !== e.author ||
      pr.base_ref !== e.base_ref || pr.state !== 'open' || pr.draft !== false)
    return denied('PR_HEAD_OR_STATE_CHANGED');
  if (b.name !== e.base_ref || b.protected !== true || b.enforce_admins !== true ||
      b.allow_bypass !== false || !obj(b.required_pull_request_reviews) ||
      !id(b.required_pull_request_reviews.required_approving_review_count) ||
      b.required_pull_request_reviews.require_code_owner_reviews !== true ||
      b.required_pull_request_reviews.dismiss_stale_reviews !== true ||
      !obj(b.required_status_checks) || b.required_status_checks.strict !== true ||
      !Array.isArray(b.required_status_checks.contexts) ||
      !unique(b.required_status_checks.contexts) ||
      !e.required_jobs.every(j => b.required_status_checks.contexts.includes(j.name)))
    return denied('BRANCH_GOVERNANCE_NOT_ENFORCED');
  if (!id(run.id) || !id(run.run_attempt) || run.event !== 'pull_request' ||
      run.head_sha !== e.head_sha || run.repository !== e.repository ||
      run.status !== 'completed' || !['success', 'failure'].includes(run.conclusion))
    return denied('RUN_IDENTITY_OR_STATUS_MISMATCH');
  if (run.conclusion !== 'success') {
    const unstarted = jobs.some(j => obj(j) && j.run_id === run.id &&
      j.run_attempt === run.run_attempt && j.head_sha === e.head_sha &&
      j.status === 'completed' && j.conclusion === 'failure' &&
      (j.steps == null || (Array.isArray(j.steps) && j.steps.length === 0)));
    return unstarted
      ? blocked('FAILED_RUN_WITH_NO_RECORDED_EXECUTED_STEPS')
      : denied('WORKFLOW_FAILED_OR_UNVERIFIED');
  }
  if (!jobs.every(obj) || !checkouts.every(obj) || !reviews.every(obj) ||
      !artifacts.every(obj) || jobs.length !== e.required_jobs.length ||
      !unique(jobs.map(j => j.name)) || !unique(jobs.map(j => j.id)))
    return denied('JOB_SET_MISSING_OR_AMBIGUOUS');
  for (const required of e.required_jobs) {
    const job = jobs.find(j => j.name === required.name);
    if (!job || !id(job.id) || job.run_id !== run.id ||
        job.run_attempt !== run.run_attempt || job.head_sha !== e.head_sha ||
        job.status !== 'completed' || job.conclusion !== 'success' ||
        !id(job.runner_id) || !Array.isArray(job.steps) || job.steps.length === 0 ||
        !job.steps.every(s => obj(s) && id(s.number) && str(s.name) &&
          s.status === 'completed' && s.conclusion === 'success') ||
        !unique(job.steps.map(s => s.number)))
      return denied('JOB_NOT_EXECUTED_ON_EXACT_HEAD');
    for (const stepName of required.required_steps) {
      if (job.steps.filter(s => s.name === stepName).length !== 1)
        return denied('REQUIRED_STEP_MISSING_OR_DUPLICATED');
    }
    const receipts = checkouts.filter(c => c.job_id === job.id);
    if (receipts.length !== 1) return denied('CHECKOUT_RECEIPT_MISSING_OR_AMBIGUOUS');
    const c = receipts[0];
    if (c.run_id !== run.id || c.run_attempt !== run.run_attempt ||
        c.head_sha !== e.head_sha || c.tree_sha !== e.tree_sha ||
        !id(c.step_number) || !job.steps.some(s => s.number === c.step_number &&
          required.required_steps.includes(s.name)))
      return denied('CHECKOUT_RECEIPT_NOT_BOUND_TO_SUCCESSFUL_STEP');
  }
  if (checkouts.length !== jobs.length) return denied('FOREIGN_CHECKOUT_RECEIPT');
  const approvals = reviews.filter(r => r.state === 'APPROVED' &&
    str(r.user) && r.user.toLowerCase() !== e.author.toLowerCase() &&
    e.code_owners.some(owner => owner.toLowerCase() === r.user.toLowerCase()) &&
    r.commit_id === e.head_sha && strictUtc(r.submitted_at));
  if (unique(approvals.map(r => r.user.toLowerCase())) === false ||
      approvals.length < b.required_pull_request_reviews.required_approving_review_count)
    return denied('INDEPENDENT_CURRENT_HEAD_CODEOWNER_APPROVAL_MISSING');
  if (artifacts.length !== e.required_artifacts.length ||
      !unique(artifacts.map(a => a.name)))
    return denied('ARTIFACT_SET_MISSING_OR_AMBIGUOUS');
  for (const name of e.required_artifacts) {
    const a = artifacts.find(x => x.name === name);
    if (!a || a.run_id !== run.id || a.run_attempt !== run.run_attempt ||
        a.head_sha !== e.head_sha || !jobs.some(j => j.id === a.job_id) ||
        !id(a.size) || typeof a.sha256 !== 'string' || !SHA256.test(a.sha256))
      return denied('ARTIFACT_RECEIPT_UNBOUND_OR_MALFORMED');
  }
  // This cannot establish that the supplied snapshot actually came from GitHub.
  return { classification: 'CANDIDATE_QUALIFIED', qualified: true,
    reason: 'offline snapshot passes policy; authenticate source data and enforce server-side',
    head_sha: e.head_sha, tree_sha: e.tree_sha, run_id: run.id,
    run_attempt: run.run_attempt, compiler_guest_parity: false };
}

export function readBundle(path) {
  if (!str(path) || !Number.isInteger(constants.O_NOFOLLOW) ||
      !Number.isInteger(constants.O_NONBLOCK))
    throw new Error('unsafe or missing input path');
  const fd = openSync(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  try {
    const stat = fstatSync(fd);
    if (!stat.isFile() || stat.size < 1 || stat.size > 262144)
      throw new Error('input must be regular file <=256 KiB');
    const buf = Buffer.alloc(262145);
    let len = 0;
    while (len < buf.length) {
      const n = readSync(fd, buf, len, buf.length - len, null);
      if (n === 0) break;
      len += n;
    }
    if (len === 0 || len > 262144) throw new Error('truncated or oversized input');
    return JSON.parse(buf.toString('utf8', 0, len));
  } finally {
    closeSync(fd);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    if (process.argv.length !== 3) throw new Error('usage: node tools/merge-qualification-policy-20261106.mjs evidence.json');
    const result = qualifyMergeEvidence(readBundle(process.argv[2]));
    process.stdout.write(JSON.stringify(result) + '\n');
    if (!result.qualified) process.exitCode = 1;
  } catch (err) {
    process.stderr.write(JSON.stringify(denied('INPUT_ERROR: ' + err.message)) + '\n');
    process.exitCode = 2;
  }
}
