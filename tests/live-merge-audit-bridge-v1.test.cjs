const test=require('node:test');
const assert=require('node:assert/strict');
let githubRestReader,inspectLiveMergeCandidate;
test.before(async()=>{
 ({githubRestReader,inspectLiveMergeCandidate}=await import('../tools/live-merge-audit-bridge-v1.mjs'));
});
const A='a'.repeat(40), B='b'.repeat(40);
const REPO='ores-truffle-oreslang/sublime-text-plugins';
const ROOT='/repos/'+REPO;
const copy=x=>structuredClone(x);
function mock() {
  const pr={number:7,state:'open',draft:false,user:{id:10,login:'author'},
    head:{sha:A,repo:{full_name:REPO}},
    base:{ref:'main',sha:B,repo:{full_name:REPO}}};
  const branch={name:'main',protected:true,commit:{sha:B}};
  const protection={enforce_admins:{enabled:true},
    required_pull_request_reviews:{require_code_owner_reviews:true,
      dismiss_stale_reviews:true,required_approving_review_count:1,
      bypass_pull_request_allowances:{users:[],teams:[],apps:[]}},
    required_status_checks:{strict:true,checks:[{context:'test',app_id:42}]}};
  const job={id:71,run_id:51,run_attempt:1,name:'test',head_sha:A,
    runner_id:9,status:'completed',conclusion:'success',
    steps:[{number:1,name:'Exact checkout',status:'completed',conclusion:'success'},
           {number:2,name:'Security tests',status:'completed',conclusion:'success'}]};
  const records={
    [ROOT+'/pulls/7']:pr,
    [ROOT+'/branches/main']:branch,
    [ROOT+'/branches/main/protection']:protection,
    [ROOT+'/git/commits/'+A]:{sha:A,tree:{sha:B}},
    [ROOT+'/pulls/7/reviews?per_page=100&page=1']:
      [{id:81,user:{id:80,login:'other-reviewer'},state:'APPROVED',
        commit_id:A,submitted_at:'2026-11-06T21:00:00Z'}],
    [ROOT+'/actions/runs/51']:{id:51,run_attempt:1,event:'pull_request',head_sha:A,
      repository:{full_name:REPO},status:'completed',conclusion:'success'},
    [ROOT+'/actions/runs/51/attempts/1/jobs?per_page=100&page=1']:
      {total_count:1,jobs:[job]},
    [ROOT+'/commits/'+A+'/check-runs?per_page=100&page=1']:
      {total_count:1,check_runs:[{id:91,name:'test',app:{id:42},head_sha:A,
        status:'completed',conclusion:'success'}]},
    [ROOT+'/actions/runs/51/artifacts?per_page=100&page=1']:
      {total_count:0,artifacts:[]},
    [ROOT+'/actions/jobs/71']:job
  };
  const calls=[];
  const get=async path=>{
    calls.push(path);
    if (!(path in records)) throw Error('UNMOCKED:'+path);
    return copy(records[path]);
  };
  const args={get,repository:REPO,number:7,expectedHead:A,runId:51,attempt:1,
    requiredJobs:[{name:'test',required_steps:['Exact checkout','Security tests']}],
    codeOwners:['other-reviewer'],requiredArtifacts:[]};
  return {records,calls,get,args,pr,branch,protection,job};
}
test('complete live metadata still cannot authorize merge without trusted receipts',async()=>{
  const f=mock(),r=await inspectLiveMergeCandidate(f.args);
  assert.equal(r.status,'BLOCKED');
  assert.equal(r.merge_authorized,false);
  assert.equal(r.guest_certified,false);
  assert.equal(r.source_authenticated,false);
  assert.equal(r.observed.executed_jobs,1);
  assert.equal(r.observed.review_events,1);
  assert.equal(r.policy.classification,'UNVERIFIED');
  assert.ok(r.reasons.includes('CHECKOUT_RECEIPTS_NOT_AUTHENTICATED'));
  assert.ok(r.reasons.includes('CODEOWNER_AUTHORITY_NOT_ATTESTED'));
  assert.ok(f.calls.filter(p=>p===ROOT+'/pulls/7').length===2);
});
test('unprotected main and unknown bypass allowances cannot be normalized into enforced governance',async()=>{
  const f=mock();f.branch.protected=false;
  let r=await inspectLiveMergeCandidate(f.args);
  assert.ok(r.reasons.includes('BASE_OR_PROTECTION_UNVERIFIED'));
  f.branch.protected=true;
  delete f.protection.required_pull_request_reviews.bypass_pull_request_allowances;
  r=await inspectLiveMergeCandidate(f.args);
  assert.ok(r.reasons.includes('ADMIN_POLICY_UNVERIFIED'));
});
test('403 or failed admin read must block, never silently assume protection',async()=>{
  const f=mock();const original=f.args.get;
  f.args.get=async p=>{if(p.endsWith('/protection')){const e=Error('GITHUB_READ_FAILED_403');e.status=403;throw e;}return original(p);};
  const r=await inspectLiveMergeCandidate(f.args);
  assert.equal(r.status,'BLOCKED');
  assert.ok(r.reasons.includes('LIVE_READ_INCOMPLETE'));
  assert.ok(r.reasons.some(x=>x.includes('403')));
});
test('original HEAD and Git tree remain immutable identities',async()=>{
  const f=mock();f.pr.head.sha='c'.repeat(40);
  const r=await inspectLiveMergeCandidate(f.args);
  assert.ok(r.reasons.includes('PR_OR_TREE_IDENTITY_UNVERIFIED'));
});
test('wrong app issuer, wrong SHA, and duplicate check contexts all deny',async()=>{
  for(const mutate of [
    x=>x.records[ROOT+'/commits/'+A+'/check-runs?per_page=100&page=1'].check_runs[0].app.id=999,
    x=>x.records[ROOT+'/commits/'+A+'/check-runs?per_page=100&page=1'].check_runs[0].head_sha='c'.repeat(40),
    x=>{const rec=x.records[ROOT+'/commits/'+A+'/check-runs?per_page=100&page=1'];rec.check_runs.push({...rec.check_runs[0],id:93});rec.total_count=2;}
  ]) {
    const f=mock();mutate(f);
    const r=await inspectLiveMergeCandidate(f.args);
    assert.ok(r.reasons.includes('REQUIRED_CHECK_UNVERIFIED'));
  }
});
test('failed zero-step workflow is runner admission, never positive execution',async()=>{
  const f=mock();
  f.records[ROOT+'/actions/runs/51'].conclusion='failure';
  f.job.conclusion='failure';
  f.job.steps=[];
  f.job.runner_id=0;
  const r=await inspectLiveMergeCandidate(f.args);
  assert.equal(r.observed.executed_jobs,0);
  assert.equal(r.policy.classification,'RUNNER_ADMISSION_BLOCKED');
  assert.equal(r.merge_authorized,false);
});
test('null-step workflow is unverified, not a test pass',async()=>{
  const f=mock();
  f.records[ROOT+'/actions/runs/51'].conclusion='failure';
  f.job.steps=null; f.job.runner_id=0;
  const r=await inspectLiveMergeCandidate(f.args);
  assert.equal(r.observed.executed_jobs,0);
  assert.equal(r.policy.classification,'UNVERIFIED');
});
test('run attempt and job identity mismatches fail closed',async()=>{
  const f=mock(), original=f.args.get;
  f.args.get=async path=>{
    const record=await original(path);
    // Change only the independently re-fetched job, not the list summary.
    if(path===ROOT+'/actions/jobs/71')record.run_attempt=2;
    return record;
  };
  const r=await inspectLiveMergeCandidate(f.args);
  assert.ok(r.reasons.includes('JOB_SUMMARY_DETAIL_MISMATCH'));
});
test('pagination duplicates and count inconsistencies fail closed',async()=>{
  for(const mutate of [
    x=>x.records[ROOT+'/pulls/7/reviews?per_page=100&page=1'].push(
      {...x.records[ROOT+'/pulls/7/reviews?per_page=100&page=1'][0]}),
    x=>x.records[ROOT+'/actions/runs/51/artifacts?per_page=100&page=1'].total_count=2
  ]) {
    const f=mock();mutate(f);
    const r=await inspectLiveMergeCandidate(f.args);
    assert.ok(r.reasons.includes('LIVE_READ_INCOMPLETE'));
  }
});
test('100-record capped review history cannot count as complete',async()=>{
  const f=mock(); const rec=f.records[ROOT+'/pulls/7/reviews?per_page=100&page=1'];
  const original=rec[0]; rec.splice(0,rec.length);
  for(let i=0;i<100;i++)rec.push({...copy(original),id:1000+i});
  const r=await inspectLiveMergeCandidate(f.args);
  assert.equal(r.status,'BLOCKED');
  assert.ok(r.reasons.includes('LIVE_READ_INCOMPLETE'));
});
test('final PR drift and branch protection drift are explicitly denied',async()=>{
  const f=mock(), original=f.args.get;let count=0;
  f.args.get=async p=>{
    let v=await original(p);
    if(p===ROOT+'/pulls/7'&&++count===2)v.head.sha='c'.repeat(40);
    return v;
  };
  const r=await inspectLiveMergeCandidate(f.args);
  assert.ok(r.reasons.includes('SOURCE_OR_GOVERNANCE_DRIFT'));
});
test('invalid request short-circuits before any GitHub reads',async()=>{
  const f=mock(); f.args.expectedHead='notsha';
  const r=await inspectLiveMergeCandidate(f.args);
  assert.deepEqual(r.reasons,['INVALID_LIVE_REQUEST']);
  assert.equal(f.calls.length,0);
});
test('read-only REST transport sends GET and bearer token to exact GitHub host',async()=>{
  let captured;
  const get=githubRestReader({token:'secret-do-not-print',fetcher:async (url,options)=>{
    captured={url,options};
    return new Response(JSON.stringify({ok:true}),{status:200,
      headers:{'content-type':'application/json'}});
  }});
  const got=await get(ROOT+'/pulls/7');
  assert.deepEqual(got,{ok:true});
  assert.equal(captured.url,'https://api.github.com'+ROOT+'/pulls/7');
  assert.equal(captured.options.method,'GET');
  assert.equal(captured.options.redirect,'manual');
  assert.equal(captured.options.headers.authorization,'Bearer secret-do-not-print');
});
test('transport allowlist admits only bounded evidence metadata endpoints',async()=>{
  const seen=[];
  const get=githubRestReader({token:'secret',fetcher:async(url,options)=>{
    seen.push(url);
    assert.equal(options.method,'GET');
    return new Response(JSON.stringify({id:1}),{status:200});
  }});
  const routes=[
    ROOT+'/pulls/7',
    ROOT+'/branches/main',
    ROOT+'/branches/main/protection',
    ROOT+'/git/commits/'+A,
    ROOT+'/pulls/7/reviews?per_page=100&page=1',
    ROOT+'/actions/runs/51',
    ROOT+'/actions/runs/51/attempts/1/jobs?per_page=100&page=2',
    ROOT+'/commits/'+A+'/check-runs?per_page=100&page=3',
    ROOT+'/actions/runs/51/artifacts?per_page=100&page=4',
    ROOT+'/actions/jobs/71'
  ];
  for(const route of routes)assert.deepEqual(await get(route),{id:1});
  assert.equal(seen.length,routes.length);
});
test('transport denies traversal, redirected credentials, oversized and non-200 responses',async()=>{
  let count=0;
  const get=githubRestReader({token:'secret',maxBytes:512,fetcher:async ()=>{
    count++;return new Response(JSON.stringify({ok:true}),{status:200});
  }});
  for(const path of [
    'https://evil.example/steal',ROOT+'/../users',ROOT+'/%2e%2e/users',
    ROOT+'//pulls/7',ROOT+'/pulls/7#x',ROOT+'/pulls/7?q=%2f',
    ROOT+'/contents/README.md',ROOT+'/git/blobs/'+A,
    ROOT+'/actions/jobs/71/logs',ROOT+'/issues/7',
    ROOT+'/pulls/7/files',ROOT+'/branches/not-main',
    ROOT+'/pulls/7?unsafe=true'
  ])await assert.rejects(get(path),/READ_PATH_DENIED/);
  assert.equal(count,0);
  const bad=githubRestReader({token:'secret',fetcher:async()=>
    new Response(null,{status:302,headers:{location:'https://evil.example/'}})});
  await assert.rejects(bad(ROOT+'/pulls/7'),/GITHUB_READ_FAILED_302/);
  const big=githubRestReader({token:'secret',maxBytes:512,fetcher:async()=>
    new Response('x'.repeat(800),{status:200})});
  await assert.rejects(big(ROOT+'/pulls/7'),/GITHUB_BODY_TOO_LARGE/);
  const forbidden=githubRestReader({token:'secret',fetcher:async()=>
    new Response('no', {status:403})});
  await assert.rejects(forbidden(ROOT+'/pulls/7'),/GITHUB_READ_FAILED_403/);
});


// Wave 2: more adversarial live metadata, transport, pagination and TOCTOU
// checks. All outcomes remain read-only and non-authorizing.
test('REST client denies invalid token, transport, and body bounds before fetch',()=>{
  for (const options of [
    {},{token:''},{token:'secret',fetcher:null},
    {token:'secret',maxBytes:255},{token:'secret',maxBytes:1048577},
    {token:'secret',maxBytes:NaN},{token:'secret',maxBytes:1.5}
  ]) assert.throws(()=>githubRestReader(options),/requires token/);
});
test('REST reader denies nonexistent and out-of-range page and attempt identities',async()=>{
  let reads=0;
  const get=githubRestReader({token:'secret',fetcher:async()=>{reads++;throw Error('SHOULD_NOT_FETCH');}});
  for(const path of [
    ROOT+'/pulls/7/reviews?per_page=100&page=0',
    ROOT+'/pulls/7/reviews?per_page=100&page=9',
    ROOT+'/pulls/7/reviews?per_page=100&page=01',
    ROOT+'/actions/runs/51/attempts/0/jobs?per_page=100&page=1',
    ROOT+'/actions/runs/51/attempts/1/jobs?per_page=100&page=9',
    ROOT+'/actions/runs/51/artifacts?per_page=100&page=999',
    ROOT+'/commits/'+A+'/check-runs?per_page=100&page=-1',
    ROOT+'/actions/runs/51/rerun',
    ROOT+'/git/trees/'+A
  ]) await assert.rejects(get(path),/READ_PATH_DENIED/);
  assert.equal(reads,0);
});
test('HTTP 200 without an observable response body is not a valid JSON receipt',async()=>{
  const get=githubRestReader({token:'secret',fetcher:async()=>
    new Response(null,{status:200})});
  await assert.rejects(get(ROOT+'/pulls/7'),/GITHUB_BODY_UNOBSERVED/);
});
test('HTTP 200 with invalid UTF-8 cannot enter a trusted JSON evidence model',async()=>{
  const get=githubRestReader({token:'secret',fetcher:async()=>
    new Response(Uint8Array.of(0xff,0xfe,0x7b,0x7d),{status:200})});
  await assert.rejects(get(ROOT+'/pulls/7'),/GITHUB_BODY_INVALID_JSON/);
});
test('HTTP 200 with truncated JSON is rejected rather than assumed empty',async()=>{
  const get=githubRestReader({token:'secret',fetcher:async()=>
    new Response('{"pr":true', {status:200})});
  await assert.rejects(get(ROOT+'/pulls/7'),/GITHUB_BODY_INVALID_JSON/);
});
test('declared oversize Content-Length is denied even with a tiny body',async()=>{
  const get=githubRestReader({token:'secret',maxBytes:512,fetcher:async()=>
    new Response('{}',{status:200,headers:{'content-length':'1024'}})});
  await assert.rejects(get(ROOT+'/pulls/7'),/GITHUB_BODY_TOO_LARGE/);
});
test('malformed second review page cannot be treated as a full history',async()=>{
  const f=mock();
  const one=f.records[ROOT+'/pulls/7/reviews?per_page=100&page=1'][0];
  f.records[ROOT+'/pulls/7/reviews?per_page=100&page=1']=
    Array.from({length:100},(_,i)=>({...copy(one),id:1000+i}));
  // A 100-item first page followed by an empty page is legitimate; instead
  // inject an invalid entry in the second page to prove fail-closed parsing.
  f.records[ROOT+'/pulls/7/reviews?per_page=100&page=2']=[
    {...copy(one),id:2001},null
  ];
  const r=await inspectLiveMergeCandidate(f.args);
  assert.ok(r.reasons.includes('LIVE_READ_INCOMPLETE'));
  assert.equal(r.merge_authorized,false);
});
test('declared total_count changing between two job pages fails closed',async()=>{
  const f=mock();
  const jobs=Array.from({length:100},(_,i)=>({...copy(f.job),id:500+i}));
  f.records[ROOT+'/actions/runs/51/attempts/1/jobs?per_page=100&page=1']={
    total_count:101,jobs
  };
  f.records[ROOT+'/actions/runs/51/attempts/1/jobs?per_page=100&page=2']={
    total_count:102,jobs:[{...copy(f.job),id:601}]
  };
  const r=await inspectLiveMergeCandidate(f.args);
  assert.ok(r.reasons.includes('LIVE_READ_INCOMPLETE'));
});
test('duplicate different-ID required job names cannot masquerade as one job',async()=>{
  const f=mock();
  f.records[ROOT+'/actions/runs/51/attempts/1/jobs?per_page=100&page=1']={
    total_count:2,jobs:[copy(f.job),{...copy(f.job),id:72}]
  };
  const r=await inspectLiveMergeCandidate(f.args);
  assert.ok(r.reasons.includes('REQUIRED_JOB_AMBIGUOUS'));
  assert.equal(r.merge_authorized,false);
});
test('stale base SHA or PR base branch is rejected before any authorization',async()=>{
  for(const change of [
    f=>{f.pr.base.sha='c'.repeat(40)},
    f=>{f.pr.base.ref='feature'}
  ]){
    const f=mock();change(f);
    const r=await inspectLiveMergeCandidate(f.args);
    assert.ok(r.reasons.includes(f.pr.base.ref!=='main' ?
      'PR_OR_TREE_IDENTITY_UNVERIFIED':'BASE_OR_PROTECTION_UNVERIFIED'));
  }
});
test('late branch-protection downgrade is observable as governance drift',async()=>{
  const f=mock(),get=f.args.get;let reads=0;
  f.args.get=async path=>{
    const value=await get(path);
    if(path===ROOT+'/branches/main'&&++reads===2)value.protected=false;
    return value;
  };
  const r=await inspectLiveMergeCandidate(f.args);
  assert.ok(r.reasons.includes('SOURCE_OR_GOVERNANCE_DRIFT'));
  assert.equal(r.merge_authorized,false);
});
test('fake green CI with no executed steps still has zero executed jobs',async()=>{
  const f=mock();f.job.steps=[];f.job.runner_id=0;
  const r=await inspectLiveMergeCandidate(f.args);
  assert.equal(r.observed.executed_jobs,0);
  assert.equal(r.status,'BLOCKED');
  assert.equal(r.merge_authorized,false);
  assert.equal(r.guest_certified,false);
});
