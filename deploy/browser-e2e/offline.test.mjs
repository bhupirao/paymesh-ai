// Pure helper/reporter tests. No Playwright install, browser, Docker or sockets.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
const fixtureSource=fs.readFileSync(new URL('./fixtures.js',import.meta.url),'utf8').replace("import { test as base, expect } from '@playwright/test';", "const base={extend: definitions => definitions}; const expect=()=>{throw new Error('UI_NOT_EXECUTED_OFFLINE');};");
const f=await import('data:text/javascript;base64,'+Buffer.from(fixtureSource).toString('base64'));
function context() {
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'paymesh-browser-offline-'));
  const real=fs.realpathSync(temp),dir=path.join(real,'paymesh-e2e-123-1');fs.mkdirSync(dir,{mode:0o700});
  const env={GITHUB_ACTIONS:'true',RUNNER_OS:'Linux',RUNNER_ENVIRONMENT:'github-hosted',GITHUB_REPOSITORY:'bhupirao/paymesh-ai',GITHUB_REF:'refs/heads/main',GITHUB_EVENT_NAME:'workflow_dispatch',E2E_VERIFY_QWEN:'true',GITHUB_RUN_ID:'123',GITHUB_RUN_ATTEMPT:'1',RUNNER_TEMP:real,E2E_PROJECT:'paymesh-e2e-123-1',E2E_DIR:dir,E2E_ENV:path.join(dir,'container.env')};
  return {env,dir};
}
test('hosted run guard accepts exact isolated scope',()=>{const c=context();assert.equal(f.guard(c.env),c.dir);});
test('hosted guard rejects wrong role of runner, repository, branch, event, remote Docker or fallback',()=>{
  const c=context();for(const [key,value] of Object.entries({RUNNER_ENVIRONMENT:'self-hosted',GITHUB_REPOSITORY:'foreign/repo',GITHUB_REF:'refs/heads/other',GITHUB_EVENT_NAME:'pull_request',DOCKER_HOST:'tcp://foreign:2375',E2E_VERIFY_QWEN:'false',E2E_DIR:'/protected',GITHUB_RUN_ID:'../unsafe'}))assert.throws(()=>f.guard({...c.env,[key]:value}));
});
test('guard rejects world-readable fixture directory',()=>{const c=context();fs.chmodSync(c.dir,0o755);assert.throws(()=>f.guard(c.env),/PRIVATE_FIXTURE/);});
test('money comparison uses decimal text with no arithmetic',()=>{assert.equal(f.exactAmount('10'),'10.00');assert.equal(f.exactAmount('3.25'),'3.25');assert.equal(f.exactAmount('9007199254740993.01'),'9007199254740993.01');for(const v of ['1e2','NaN','-1','1.001'])assert.throws(()=>f.exactAmount(v));});
test('model validator rejects fallback, missing knowledge and false success',()=>{
  const good={analysisMode:'RAG_LLM',generationStatus:'SUCCEEDED',knowledgeReferences:[{}]};assert.equal(f.modelSuccess({turn:{response:good}}),good);assert.equal(f.modelSuccess({investigation:good}),good);
  for(const value of [{...good,analysisMode:'RAG_ASSISTED'},{...good,generationStatus:'TIMEOUT'},{...good,knowledgeReferences:[]}])assert.throws(()=>f.modelSuccess(value),/REAL_MODEL_REQUIRED/);
});
test('response observer cannot accept another origin or method',()=>{
  let filter;f.responseFor({waitForResponse:fn=>{filter=fn;}},'POST','/api/v1/auth/login');
  const response=(url,method)=>({url:()=>url,request:()=>({method:()=>method})});
  assert.equal(filter(response('http://127.0.0.1:15500/api/v1/auth/login','POST')),true);
  assert.equal(filter(response('http://127.0.0.1:18080/api/v1/auth/login','POST')),false);
  assert.equal(filter(response('https://foreign.invalid/api/v1/auth/login','POST')),false);
  assert.equal(filter(response('http://127.0.0.1:15500/api/v1/auth/login','GET')),false);
});
test('response parser is bounded and errors contain only fixed codes',async()=>{
  assert.deepEqual(await f.body({status:()=>200,text:async()=>'{"ok":true}'}),{ok:true});
  for(const response of [{status:()=>403,text:async()=> 'PRIVATE_CANARY'},{status:()=>200,text:async()=> 'PRIVATE_CANARY'},{status:()=>200,text:async()=> 'x'.repeat(524289)}])await assert.rejects(f.body(response),error=>!error.message.includes('PRIVATE_CANARY'));
});
test('browser network policy permits only frontend origin',async()=>{
  let handler;await f.restrictNetwork({route:async(pattern,fn)=>{handler=fn;}});
  for(const [url,allowed] of [['http://127.0.0.1:15500/merchant/ai',true],['http://127.0.0.1:18080/api/v1/auth/login',false],['https://third-party.invalid',false]]){
    let result;await handler({request:()=>({url:()=>url}),continue:()=>{result=true;},abort:()=>{result=false;}});assert.equal(result,allowed);
  }
});
async function reporter() {
  const c=context();process.env.BROWSER_OFFLINE_FIXTURE=c.dir;
  const source=fs.readFileSync(new URL('./sanitized-reporter.js',import.meta.url),'utf8').replace("import { guard } from './fixtures.js';","const guard=()=>process.env.BROWSER_OFFLINE_FIXTURE;");
  const {default:Reporter}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  return {instance:new Reporter(),classify:(await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'))).classifyFailure,dir:c.dir};
}
function finish(reporter,result) { const original=process.stdout.write;process.stdout.write=()=>true;try{return reporter.onEnd(result);}finally{process.stdout.write=original;} }
test('reporter discards raw errors, attachments, stdout, URLs and secrets',async()=>{
  const {instance:r,dir}=await reporter();const canary='PRIVATE_CANARY_TOKEN_RESPONSE';
  r.onStdOut(canary);r.onStdErr(canary);r.onError(new Error(canary));
  r.onTestEnd({title:canary},{status:'failed',duration:1,errors:[{message:canary}],attachments:[canary]});
  r.onStepEnd(null,null,{category:'test.step',title:canary,error:new Error(canary)});
  assert.equal(finish(r,{status:'failed'}).status,'failed');
  const file=path.join(dir,'sanitized-browser.json'),text=fs.readFileSync(file,'utf8');assert.equal(text.includes(canary),false);assert.equal(fs.statSync(file).mode&0o777,0o600);
});
test('partial suite cannot report browser success',async()=>{
  const {instance:r,dir}=await reporter();r.onTestEnd({title:'DESKTOP_KEYBOARD_AND_VALIDATION'},{status:'passed',duration:1});assert.equal(finish(r,{status:'passed'}).status,'failed');assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'sanitized-browser.json'))).success,false);
});
test('reporter requires complete native journey and both responsive tests',async()=>{
  const {instance:r,dir}=await reporter();
  for(const title of ['COMPLETE_NATIVE_BROWSER_JOURNEY','MOBILE_KEYBOARD_AND_VALIDATION','DESKTOP_KEYBOARD_AND_VALIDATION'])r.onTestEnd({title},{status:'passed',duration:1});
  for(const title of ['MERCHANT_REGISTRATION_VALIDATION','ADMIN_LOGIN_AND_NATIVE_APPROVAL','DASHBOARD_SESSION_AND_ROLE_PROTECTION','PAYMENT_CREATION_PROCESSING_AND_LIST','MERCHANT_OWNERSHIP_ISOLATION','NATIVE_INVESTIGATION_REAL_QWEN','PARTIAL_AND_FULL_REFUND_UI','PAYMENT_LINK_AND_CUSTOMER_CHECKOUT','MERCHANT_ADMIN_CHAT_AND_SAVED_HISTORY','CROSS_TAB_LOGOUT_AND_PROTECTED_ROUTE'])r.onStepEnd(null,null,{category:'test.step',title});
  assert.equal(finish(r,{status:'passed'}).status,'passed');const result=JSON.parse(fs.readFileSync(path.join(dir,'sanitized-browser.json')));assert.equal(result.modelInferenceVerified,true);
});

test('native dialog handler is removed even when action fails or no dialog appears',async()=>{
  let installed=null;
  const page={on:(event,handler)=>{assert.equal(event,'dialog');installed=handler;},off:(event,handler)=>{assert.equal(handler,installed);installed=null;}};
  await f.safeDialog(page,async()=>{});assert.equal(installed,null);
  await assert.rejects(f.safeDialog(page,async()=>{throw new Error('FIXED_ACTION_FAILURE');}));assert.equal(installed,null);
});

test('failure classification emits fixed codes without messages, stack or matcher values',async()=>{
  const {classify}=await reporter();
  const fixtures=[
    [{message:"browserType.launch: Executable doesn't exist PRIVATE_CANARY"},'failed','BROWSER_LAUNCH','BROWSER_EXECUTABLE_MISSING'],
    [{message:'Host system is missing dependencies PRIVATE_CANARY'},'failed','BROWSER_LAUNCH','BROWSER_SYSTEM_DEPENDENCY_MISSING'],
    [{message:'Fixture "context" references itself PRIVATE_CANARY'},'failed','FIXTURE_CONFIGURATION','FIXTURE_CONFIGURATION_ERROR'],
    [{message:'worker process exited unexpectedly PRIVATE_CANARY'},'failed','WORKER_INFRASTRUCTURE','WORKER_EXITED'],
    [{message:'browserType.launch: PRIVATE_CANARY'},'failed','BROWSER_LAUNCH','CHROMIUM_LAUNCH_FAILED'],
    [{message:'PRIVATE_CANARY'},'timedOut','TIMEOUT','TEST_OR_ACTION_TIMEOUT'],
    [{message:'expect(locator).toBeFocused PRIVATE_CANARY',matcherResult:{actual:'PRIVATE_CANARY'}},'failed','ASSERTION','UI_ASSERTION_FAILED'],
    [{message:'REAL_MODEL_REQUIRED'},'failed','SAFE_TEST_GUARD','REAL_MODEL_REQUIRED'],
    [{name:'TypeError',message:'PRIVATE_CANARY'},'failed','TEST_RUNTIME','TEST_RUNTIME_ERROR'],
    [{message:'ENOENT PRIVATE_CANARY'},'failed','FIXTURE_FILESYSTEM','FIXTURE_FILE_UNAVAILABLE'],
    [{message:'PRIVATE_CANARY',stack:'PRIVATE_CANARY'},'failed','UNKNOWN','UNCLASSIFIED_TEST_FAILURE']
  ];
  for(const [error,status,category,code] of fixtures){const value=classify(error,status);assert.equal(value.category,category);assert.equal(value.errorCode,code);assert.equal(JSON.stringify(value).includes('PRIVATE_CANARY'),false);}
  assert.equal(classify({message:'expect(locator).toBeFocused PRIVATE_CANARY'},'failed').assertionCategory,'FOCUS');
  assert.equal(classify({message:'page.goto: Timeout 30000ms exceeded PRIVATE_CANARY'},'failed').timeoutCategory,'NAVIGATION_TIMEOUT');
  assert.equal(classify({location:{file:'/private/PRIVATE_CANARY/journey.spec.js',line:45}},'failed').location.file,'journey.spec.js');
  assert.equal(classify({location:{file:'https://unsafe.invalid/PRIVATE_CANARY',line:45}},'failed').location,null);
});
test('setup failure records test, fixed stage, timeout category and unproven browser status',async()=>{
  const {instance:r,dir}=await reporter();const t={id:'internal-not-retained',title:'DESKTOP_KEYBOARD_AND_VALIDATION'};
  r.onTestBegin(t);r.onTestEnd(t,{status:'timedOut',duration:0,error:{message:'PRIVATE_CANARY'}});
  finish(r,{status:'failed'});
  const record=JSON.parse(fs.readFileSync(path.join(dir,'sanitized-browser.json'))).tests[0];
  assert.equal(record.failedStage,'HOOK_OR_FIXTURE_SETUP');assert.equal(record.chromiumLaunchStatus,'NOT_OBSERVED');assert.equal(record.diagnostic.timeoutCategory,'TEST_TIMEOUT');assert.equal(record.durationMs,0);assert.equal(record.elapsedMs>=0,true);
});
test('named failed stage and valid private launch witness are correlated to the test',async()=>{
  const {instance:r,dir}=await reporter();const t={id:'private-internal',title:'COMPLETE_NATIVE_BROWSER_JOURNEY'};
  fs.writeFileSync(path.join(dir,'browser-launch-'+t.title+'.json'),JSON.stringify({testCode:t.title,chromiumLaunchStatus:'SUCCEEDED'}),{mode:0o600});
  r.onTestBegin(t);r.onStepBegin(t,null,{category:'test.step',title:'ADMIN_LOGIN_AND_NATIVE_APPROVAL'});
  r.onStepEnd(t,null,{category:'pw:api',title:'UNTRUSTED_PRIVATE_CANARY',error:{message:'PRIVATE_CANARY'}});
  r.onTestEnd(t,{status:'failed',duration:12,error:{message:'expect(locator).toBeVisible PRIVATE_CANARY'}});finish(r,{status:'failed'});
  const record=JSON.parse(fs.readFileSync(path.join(dir,'sanitized-browser.json'))).tests[0];assert.equal(record.chromiumLaunchStatus,'SUCCEEDED');assert.equal(record.failedStage,'ADMIN_LOGIN_AND_NATIVE_APPROVAL');assert.equal(record.diagnostic.assertionCategory,'VISIBILITY');assert.equal(JSON.stringify(record).includes('PRIVATE_CANARY'),false);
});
test('mismatched or world-readable witness does not prove Chromium launch',async()=>{
  for(const mismatch of [true,false]){
    const {instance:r,dir}=await reporter();const t={id:'internal',title:'DESKTOP_KEYBOARD_AND_VALIDATION'};
    fs.writeFileSync(path.join(dir,'browser-launch-'+t.title+'.json'),JSON.stringify({testCode:mismatch?'COMPLETE_NATIVE_BROWSER_JOURNEY':t.title,chromiumLaunchStatus:'SUCCEEDED'}),{mode:mismatch?0o600:0o644});
    r.onTestEnd(t,{status:'failed',duration:0,error:{message:'PRIVATE_CANARY'}});finish(r,{status:'failed'});
    assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'sanitized-browser.json'))).tests[0].chromiumLaunchStatus,'NOT_OBSERVED');
  }
});
test('private output is created owned and mode 0700',()=>{
  const c=context(),output=f.privateDirectory('browser-private-output',c.env);
  assert.equal(path.dirname(output),c.dir);assert.equal(fs.statSync(output).mode&0o7777,0o700);assert.equal(fs.statSync(output).uid,process.getuid());
});
test('Playwright-style removed and recreated output is securely repaired',()=>{
  const c=context(),output=f.privateDirectory('browser-private-output',c.env);
  fs.rmdirSync(output);fs.mkdirSync(path.join(output,'worker-artifacts'),{recursive:true,mode:0o755});fs.chmodSync(output,0o755);
  assert.equal(fs.statSync(output).mode&0o777,0o755);
  assert.equal(f.privateDirectory('browser-private-output',c.env),output);
  assert.equal(fs.statSync(output).mode&0o7777,0o700);
  assert.equal(fs.statSync(path.join(output,'worker-artifacts')).mode&0o777,0o755);
  assert.equal(f.privateDirectory('browser-private-output',c.env),output);
});
test('output repair rejects symlink and leaves external directory untouched',()=>{
  const c=context(),external=fs.mkdtempSync(path.join(os.tmpdir(),'paymesh-offline-external-'));
  fs.chmodSync(external,0o755);fs.symlinkSync(external,path.join(c.dir,'browser-private-output'),'dir');
  assert.throws(()=>f.privateDirectory('browser-private-output',c.env),/PRIVATE_OUTPUT_REQUIRED/);
  assert.equal(fs.statSync(external).mode&0o777,0o755);
});
test('output repair rejects unexpected files without changing mode',()=>{
  const c=context(),output=path.join(c.dir,'browser-private-output');fs.writeFileSync(output,'SYNTHETIC_PRIVATE_CONTENT',{mode:0o644});
  assert.throws(()=>f.privateDirectory('browser-private-output',c.env),/PRIVATE_OUTPUT_REQUIRED/);
  assert.equal(fs.statSync(output).mode&0o777,0o644);
});
test('external or traversal output names cannot be chmod targets',()=>{
  const c=context(),original=fs.fchmodSync;let count=0;fs.fchmodSync=()=>{count++;};
  try{for(const name of ['../outside','/tmp/outside','browser-private-output/../outside','browser-private-output/child','.',c.dir])assert.throws(()=>f.privateDirectory(name,c.env),/FIXED_OUTPUT_DIRECTORY_REQUIRED/);assert.equal(count,0);}finally{fs.fchmodSync=original;}
});
test('foreign inode ownership fails before any chmod',()=>{
  const c=context(),output=path.join(c.dir,'browser-private-output');fs.mkdirSync(output,{mode:0o755});
  const originalStat=fs.fstatSync,originalChmod=fs.fchmodSync;let count=0;
  fs.fstatSync=fd=>{const stat=originalStat(fd);Object.defineProperty(stat,'uid',{value:process.getuid()+1});return stat;};
  fs.fchmodSync=()=>{count++;};
  try{assert.throws(()=>f.privateDirectory('browser-private-output',c.env),/PRIVATE_OUTPUT_REQUIRED/);assert.equal(count,0);assert.equal(fs.statSync(output).mode&0o777,0o755);}finally{fs.fstatSync=originalStat;fs.fchmodSync=originalChmod;}
});
test('post-correction permissions are verified and no path chmod is used',()=>{
  const c=context(),output=path.join(c.dir,'browser-private-output');fs.mkdirSync(output,{mode:0o755});
  const original=fs.fchmodSync;let calls=0;fs.fchmodSync=()=>{calls++;};
  try{assert.throws(()=>f.privateDirectory('browser-private-output',c.env),/PRIVATE_OUTPUT_REQUIRED/);assert.equal(calls,1);assert.equal(fs.statSync(output).mode&0o777,0o755);}finally{fs.fchmodSync=original;}
});
test('decorated guard errors classify only approved complete first-line codes',async()=>{
  const {classify}=await reporter();
  for(const message of ['PRIVATE_OUTPUT_REQUIRED','Error: PRIVATE_OUTPUT_REQUIRED','\x1b[31mError: PRIVATE_OUTPUT_REQUIRED\x1b[0m\nPRIVATE_CANARY','  Error:\tPRIVATE_OUTPUT_REQUIRED  \r\nPRIVATE_CANARY']){
    const d=classify({message},'failed');assert.equal(d.errorCode,'PRIVATE_OUTPUT_REQUIRED');assert.equal(d.category,'SAFE_TEST_GUARD');assert.equal(JSON.stringify(d).includes('PRIVATE_CANARY'),false);
  }
  for(const message of ['PRIVATE_OUTPUT_REQUIRED_PRIVATE_CANARY','Error: PRIVATE_OUTPUT_REQUIRED PRIVATE_CANARY','PRIVATE_CANARY\nPRIVATE_OUTPUT_REQUIRED','Error: PRIVATE_CANARY'])assert.equal(classify({message},'failed').category,'UNKNOWN');
});
test('stdout diagnostics contain only safe fields and retain JSON evidence',async()=>{
  const {instance:r,dir}=await reporter();const t={id:'not-exported',title:'DESKTOP_KEYBOARD_AND_VALIDATION'};
  r.onTestBegin(t);r.onTestEnd(t,{status:'failed',duration:2,error:{message:'\x1b[31mError: PRIVATE_OUTPUT_REQUIRED\x1b[0m\nPRIVATE_CANARY_TOKEN_URL_STACK'}});
  let output='';const original=process.stdout.write;process.stdout.write=chunk=>{output+=chunk;return true;};
  try{assert.equal(r.onEnd({status:'failed'}).status,'failed');}finally{process.stdout.write=original;}
  assert.equal(output.includes('PRIVATE_CANARY'),false);assert.equal(output.includes('not-exported'),false);
  const lines=output.trim().split('\n');assert.equal(lines.length,2);
  assert.ok(lines[0].startsWith('BROWSER_FAILURE_DIAGNOSTIC='));const value=JSON.parse(lines[0].split('=',2)[1]);
  assert.deepEqual(Object.keys(value).sort(),['testCode','stageCode','category','errorCode','elapsedMs','chromiumLaunchStatus','assertionCategory','timeoutCategory'].sort());
  assert.equal(value.errorCode,'PRIVATE_OUTPUT_REQUIRED');assert.equal(value.chromiumLaunchStatus,'NOT_OBSERVED');assert.equal(value.stageCode,'HOOK_OR_FIXTURE_SETUP');
  const saved=fs.readFileSync(path.join(dir,'sanitized-browser.json'),'utf8');assert.equal(saved.includes('PRIVATE_CANARY'),false);assert.equal(JSON.parse(saved).tests[0].diagnostic.errorCode,'PRIVATE_OUTPUT_REQUIRED');
});
test('unknown infrastructure diagnostics remain fixed and do not expose errors',async()=>{
  const {instance:r}=await reporter();r.onError({message:'PRIVATE_CANARY_UNKNOWN',stack:'PRIVATE_CANARY_STACK'});
  let output='';const original=process.stdout.write;process.stdout.write=chunk=>{output+=chunk;return true;};
  try{r.onEnd({status:'failed'});}finally{process.stdout.write=original;}
  assert.equal(output.includes('PRIVATE_CANARY'),false);
  const value=JSON.parse(output.split('\n')[0].split('=',2)[1]);assert.equal(value.testCode,'INFRASTRUCTURE');assert.equal(value.errorCode,'UNCLASSIFIED_TEST_FAILURE');assert.equal(value.category,'UNKNOWN');
});
