// Pure helper/reporter tests. No Playwright install, browser, Docker or sockets.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
const fixtureSource=fs.readFileSync(new URL('./fixtures.js',import.meta.url),'utf8').replace("import { test as base, expect } from '@playwright/test';", "const info={annotations:[]};const base={extend: definitions => ({...definitions,step:async(code,action)=>action(),info:()=>info})}; const expect=()=>{throw new Error('UI_NOT_EXECUTED_OFFLINE');};");
const budgetSource=fs.readFileSync(new URL('./auth-budget.js',import.meta.url),'utf8');
const budgetURL='data:text/javascript;base64,'+Buffer.from(budgetSource).toString('base64');
const fixtureWithBudget=fixtureSource.replace("import { authBudget, AUTH_PATHS } from './auth-budget.js';","import {authBudget,AUTH_PATHS} from '"+budgetURL+"';");
const f=await import('data:text/javascript;base64,'+Buffer.from(fixtureWithBudget).toString('base64'));
const {AuthBudget}=await import(budgetURL);
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
  let handler;await f.restrictNetwork({on:()=>{},route:async(pattern,fn)=>{handler=fn;}});
  for(const [url,allowed] of [['http://127.0.0.1:15500/merchant/ai',true],['http://127.0.0.1:18080/api/v1/auth/login',false],['https://third-party.invalid',false]]){
    let result;await handler({request:()=>({url:()=>url}),continue:()=>{result=true;},abort:()=>{result=false;}});assert.equal(result,allowed);
  }
});
async function reporter() {
  const c=context();process.env.BROWSER_OFFLINE_FIXTURE=c.dir;
  const source=fs.readFileSync(new URL('./sanitized-reporter.js',import.meta.url),'utf8').replace("import { guard, ACTION_CODES, UI_STATES, ROUTE_CODES, HTTP_CODES } from './fixtures.js';","const guard=()=>process.env.BROWSER_OFFLINE_FIXTURE;"+['ACTION_CODES','UI_STATES','ROUTE_CODES','HTTP_CODES'].map(name=>'const '+name+'=new Set('+JSON.stringify([...f[name]])+');').join(''));
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
  assert.deepEqual(Object.keys(value).sort(),['testCode','stageCode','category','errorCode','elapsedMs','chromiumLaunchStatus','assertionCategory','timeoutCategory','loginState','location','lastCompletedActionCode','pendingActionCode','lastObservedHttpStatus','expectedUICategory','actualRouteCategory','lastRelevantHttpStatus','httpEndpointCategory'].sort());
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

test('registration succeeds on signup with pending status and explicit sign-in link contract',async()=>{
  let source=fs.readFileSync(new URL('../../frontend/assets/js/portals/registration.js',import.meta.url),'utf8');
  const signup=fs.readFileSync(new URL('../../frontend/assets/js/portals/signup.js',import.meta.url),'utf8');
  source=source.replace("import { request } from '../api/client.js';", "const request=async()=>({status:201,data:{accountStatus:'PENDING_APPROVAL',message:'Your account has been created successfully. You can now sign in using your email and password.'}});")
    .replace("import { getVersion } from '../auth/session.js';", "const getVersion=()=>0;")
    .replace("import { validateSignup } from './signup.js';", "import {validateSignup} from 'data:text/javascript;base64,"+Buffer.from(signup).toString('base64')+"';");
  const {createRegistration}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  const events=[];await createRegistration(value=>events.push(value)).submit({firstName:'Synthetic',lastName:'Test',businessName:'Disposable',email:'signup@e2e.example.test',mobile:'+12025550101',businessType:'COMPANY',country:'US',password:'Synthetic-passphrase-only',confirmPassword:'Synthetic-passphrase-only',terms:true});
  assert.equal(events.some(v=>v.success===true),true);assert.equal(events.find(v=>v.success===true).message,'Your account has been created successfully. You can now sign in using your email and password.');
  assert.equal(/navigate|location[.]|history[.]/.test(source),false);
});

test('actual router sends authenticated pending Merchant login to onboarding dashboard',async()=>{
  let source=fs.readFileSync(new URL('../../frontend/assets/js/portals/router.js',import.meta.url),'utf8')
    .replace("import { MERCHANT_PAGES } from '../merchant/routes.js';", "const MERCHANT_PAGES={'/merchant/dashboard':'Dashboard'};")
    .replace("import { ADMIN_PAGES } from '../admin/routes.js';", "const ADMIN_PAGES={'/admin/dashboard':'Dashboard'};")
    .replace("import { checkExpiry, getSession, subscribe } from '../auth/session.js';", "const checkExpiry=()=>{},getSession=()=>null,subscribe=()=>()=>{};");
  const {resolveRoute}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  assert.equal(resolveRoute('/merchant/login',{roles:['MERCHANT'],accountStatus:'PENDING_APPROVAL'}).path,'/merchant/dashboard');
  assert.equal(resolveRoute('/merchant/dashboard',null).path,'/merchant/login');
  assert.equal(resolveRoute('/merchant/signup',null).page,'signup');
});
test('login route diagnostics never retain raw URLs, query values or checkout tokens',()=>{
  const token='PRIVATE_CANARY_CHECKOUT_TOKEN';
  assert.deepEqual(f.loginRoute('http://127.0.0.1:15500/merchant/login'),{routeCode:'MERCHANT_LOGIN',suffixPresent:false});
  assert.deepEqual(f.loginRoute('http://127.0.0.1:15500/merchant/dashboard#'+token),{routeCode:'MERCHANT_DASHBOARD',suffixPresent:true});
  assert.deepEqual(f.loginRoute('http://127.0.0.1:15500/checkout/'+token),{routeCode:'OTHER_ROUTE',suffixPresent:false});
  assert.equal(JSON.stringify(f.loginRoute('https://foreign.invalid/'+token)).includes(token),false);
});
test('login feedback diagnostics classify only known UI strings',()=>{
  assert.equal(f.loginFeedback('Invalid authentication response. Please sign in again.'),'INVALID_AUTH_RESPONSE');
  assert.equal(f.loginFeedback('Unable to sign in. Check your username and password.'),'CREDENTIALS_REJECTED');
  assert.equal(f.loginFeedback('PRIVATE_CANARY_USER_DATA'),'OTHER_FEEDBACK');
});
test('reporter retains only typed fixed-code login observation correlated to its test',async()=>{
  const {instance:r,dir}=await reporter(),title='COMPLETE_NATIVE_BROWSER_JOURNEY';
  fs.writeFileSync(path.join(dir,'browser-login-'+title+'.json'),JSON.stringify({testCode:title,portalRole:'MERCHANT',httpStatus:401,routeCode:'MERCHANT_LOGIN',suffixPresent:false,feedbackCode:'CREDENTIALS_REJECTED',private:'PRIVATE_CANARY'}),{mode:0o600});
  r.onTestEnd({id:'internal',title},{status:'failed',duration:1,error:{message:'expect(page).toHaveURL PRIVATE_CANARY'}});finish(r,{status:'failed'});
  const text=fs.readFileSync(path.join(dir,'sanitized-browser.json'),'utf8'),value=JSON.parse(text).tests[0].loginState;
  assert.equal(value.httpStatus,401);assert.equal(value.routeCode,'MERCHANT_LOGIN');assert.equal(value.feedbackCode,'CREDENTIALS_REJECTED');assert.equal(text.includes('PRIVATE_CANARY'),false);
});
test('malformed login observations are ignored without exposing their values',async()=>{
  const {instance:r,dir}=await reporter(),title='COMPLETE_NATIVE_BROWSER_JOURNEY';
  fs.writeFileSync(path.join(dir,'browser-login-'+title+'.json'),JSON.stringify({testCode:title,portalRole:'MERCHANT',httpStatus:200,routeCode:'PRIVATE_CANARY',suffixPresent:false,feedbackCode:'NO_FEEDBACK'}),{mode:0o600});
  r.onTestEnd({id:'internal',title},{status:'failed',duration:1});finish(r,{status:'failed'});
  const text=fs.readFileSync(path.join(dir,'sanitized-browser.json'),'utf8');assert.equal(JSON.parse(text).tests[0].loginState,null);assert.equal(text.includes('PRIVATE_CANARY'),false);
});

test('auth admission allows nine operations then waits the known limiter window',async()=>{
  let now=0;const waits=[],budget=new AuthBudget({now:()=>now,sleep:async ms=>{waits.push(ms);now+=ms;}}),page={};let calls=0;
  for(let i=0;i<10;i++)await budget.run(page,'/api/v1/auth/login',async()=>{calls++;});
  assert.equal(calls,10);assert.deepEqual(waits,[61000]);assert.equal(budget.used,1);
});
test('auth roles and endpoint kinds share one scheduling budget',async()=>{
  let now=0;const budget=new AuthBudget({now:()=>now,sleep:async ms=>{now+=ms;}}),paths=['/api/v1/auth/register','/api/v1/auth/refresh','/api/v1/auth/login','/api/v1/auth/logout','/api/v1/auth/logout-all'];
  for(let i=0;i<10;i++)await budget.run({role:i%2?'ADMIN':'MERCHANT'},paths[i%paths.length],async()=>{});
  assert.equal(now,61000);assert.equal(budget.used,1);
});
test('auth request observation does not double count a reserved submit',async()=>{
  let now=0;const budget=new AuthBudget({now:()=>now,sleep:async ms=>{now+=ms;}}),page={},request={method:()=> 'POST'};
  await budget.run(page,'/api/v1/auth/login',async()=>{budget.request(request,page,'/api/v1/auth/login');budget.response(request,200);});
  assert.equal(budget.used,1);assert.equal(budget.requestCount,1);budget.assertHealthy();
});
test('unplanned startup refreshes consume the same observed auth budget',async()=>{
  let now=0;const waits=[],budget=new AuthBudget({now:()=>now,sleep:async ms=>{waits.push(ms);now+=ms;}});
  for(let i=0;i<9;i++){const request={method:()=> 'POST'};budget.request(request,{},'/api/v1/auth/refresh');budget.response(request,401);}
  let called=false;await budget.run({},'/api/v1/auth/login',async()=>{called=true;});assert.equal(called,true);assert.deepEqual(waits,[61000]);
});
test('pacing waits before HTTP action and uses response completion as quiet-window baseline',async()=>{
  let now=0;const budget=new AuthBudget({now:()=>now,sleep:async ms=>{now+=ms;}}),page={};
  for(let i=0;i<9;i++)await budget.run(page,'/api/v1/auth/login',async()=>{});
  const request={method:()=> 'POST'};budget.request(request,{},'/api/v1/auth/refresh');now=10000;budget.response(request,401);
  let at=0;await budget.run(page,'/api/v1/auth/login',async()=>{at=now;});assert.equal(at,71000);
});
test('observed 429 fails rather than retries a login',async()=>{
  const budget=new AuthBudget(),page={},request={method:()=> 'POST'};let calls=0;
  await budget.run(page,'/api/v1/auth/login',async()=>{calls++;budget.request(request,page,'/api/v1/auth/login');budget.response(request,429);});
  assert.throws(()=>budget.assertHealthy(),/AUTH_LIMIT_OBSERVED/);
  await assert.rejects(budget.run(page,'/api/v1/auth/login',async()=>{calls++;}),/AUTH_LIMIT_OBSERVED/);assert.equal(calls,1);
});
test('auth admission wait is bounded and does not silently retry work',async()=>{
  let now=0;const budget=new AuthBudget({now:()=>now,sleep:async ms=>{now+=ms;budget.lastActivity=now;}});
  for(let i=0;i<9;i++)await budget.run({},'/api/v1/auth/login',async()=>{});
  let called=false;await assert.rejects(budget.run({},'/api/v1/auth/login',async()=>{called=true;}),/AUTH_BUDGET_WAIT_LIMIT/);assert.equal(called,false);
});
test('no auth pacing cost for read-only APIs and observation failure is fail closed',()=>{
  const budget=new AuthBudget();budget.request({method:()=> 'GET'},{},'/api/v1/merchant/dashboard');assert.equal(budget.used,0);
  budget.observationFailed=true;assert.throws(()=>budget.assertHealthy(),/AUTH_OBSERVATION_FAILED/);
});
test('known UI rate-limit feedback is classified without retaining time text',()=>{
  assert.equal(f.loginFeedback('Too many attempts. Wait 43 seconds before trying again.'),'RATE_LIMITED');
  assert.equal(f.loginFeedback('Too many attempts. Please wait before trying again.'),'RATE_LIMITED');
  assert.equal(f.loginFeedback('Too many attempts. PRIVATE_CANARY'),'OTHER_FEEDBACK');
});

// Coordinated source-contract audit. These execute pure routing/model helpers,
// not Chromium, HTTP requests or a replacement for the native journey.
test('protected navigation plans use visible SPA controls and preserve role boundaries',()=>{
  for(const [route,label] of Object.entries(f.PORTAL_BUTTONS)) {
    const role=route.split('/')[1];const plan=f.navigationPlan(`/${role}/dashboard`,route,true);
    assert.equal(plan.spa,true);assert.equal(plan.button,label);
  }
  assert.equal(f.navigationPlan('/admin/dashboard','/merchant/payments',true).spa,false);
  assert.equal(f.navigationPlan('/admin/login','/admin/merchants',false).spa,false);
  assert.equal(f.navigationPlan('/merchant/dashboard','/merchant/payment-links/create',true).createLink,true);
  for(const target of ['https://foreign.invalid/x','/admin/merchants?private=CANARY','/admin/merchants#CANARY'])assert.throws(()=>f.navigationPlan('/admin/dashboard',target,true),/FIXED_BROWSER_TARGET_REQUIRED/);
});
test('actual released router demonstrates hard deep-link redirect and bookmark loss',async()=>{
  let source=fs.readFileSync(new URL('../../frontend/assets/js/portals/router.js',import.meta.url),'utf8')
    .replace("import { MERCHANT_PAGES } from '../merchant/routes.js';", "const MERCHANT_PAGES={'/merchant/dashboard':'Dashboard','/merchant/ai':'AI Assistant'};")
    .replace("import { ADMIN_PAGES } from '../admin/routes.js';", "const ADMIN_PAGES={'/admin/dashboard':'Dashboard','/admin/merchants':'Merchant Management','/admin/ai':'AI Assistant'};")
    .replace("import { checkExpiry, getSession, subscribe } from '../auth/session.js';", "const checkExpiry=()=>{},getSession=()=>null,subscribe=()=>()=>{};");
  const {createRouter}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  for(const initial of ['/admin/merchants','/admin/ai','/merchant/ai']){
    let session=null;const role=initial.split('/')[1].toUpperCase();
    const target={location:{pathname:initial},history:{state:{paymeshConversation:{id:'synthetic-pointer'}},replaceState(value,unused,next){this.state=value;if(next)target.location.pathname=next;},pushState(value,unused,next){this.state=value;target.location.pathname=next;}},addEventListener(){},removeEventListener(){}};
    const router=createRouter(()=>{},{target,session:()=>session,expiry:()=>{},watch:()=>()=>{}});
    assert.equal(router.start().path,`/${role.toLowerCase()}/login`);assert.equal(target.history.state,null);
    session={roles:[role]};assert.equal(router.refresh().path,`/${role.toLowerCase()}/dashboard`);
    // The proper in-session UI route transition reaches the requested view.
    assert.equal(router.navigate(initial).path,initial);
  }
});
test('admin Search exists for merchants but not dashboard in the released view contract',()=>{
  const view=fs.readFileSync(new URL('../../frontend/assets/js/admin/view.js',import.meta.url),'utf8');
  assert.match(view,/if\(view!=='dashboard'\)labeled\(form/);
  assert.ok(view.includes("?'Exact Admin login':'Search'"));
  for(const value of ['External ownership review reference','I attest that ownership was reviewed for this exact Merchant.','Confirm Merchant administration','Cancel review'])assert.ok(view.includes(value));
});
test('ordinary response waits stay narrow while investigation and saved-chat allow client deadlines',()=>{
  assert.equal(f.responseTimeout('/api/v1/admin/merchants'),25000);
  assert.equal(f.responseTimeout('/api/v1/merchant/ai/conversations/synthetic/messages','GET'),25000);
  assert.equal(f.responseTimeout('/api/v1/payments/synthetic/investigate'),70000);
  assert.equal(f.responseTimeout(/^\/api\/v1\/merchant\/ai\/conversations\/[^/]+\/messages$/),70000);
  const client=fs.readFileSync(new URL('../../frontend/assets/js/api/config.js',import.meta.url),'utf8');
  assert.ok(client.includes('investigationTimeoutMs: 65000'));assert.ok(client.includes('chatTimeoutMs: 45000'));assert.ok(client.includes('timeoutMs: 20000'));
});
test('concurrent page admissions share the budget and excess waiters fail within its bound',async()=>{
  let now=0,waiters=[],admitted=[];const budget=new AuthBudget({now:()=>now,sleep:ms=>new Promise(resolve=>waiters.push({at:now+ms,resolve}))});
  const jobs=Array.from({length:25},(_,i)=>budget.run({i},'/api/v1/auth/login',async()=>admitted.push(now)));
  const outcome=Promise.allSettled(jobs);assert.equal(admitted.length,9);
  while(waiters.length){const batch=waiters;waiters=[];now=Math.min(...batch.map(x=>x.at));for(const item of batch)item.resolve();await Promise.resolve();await Promise.resolve();}
  const results=await outcome;assert.equal(results.filter(x=>x.status==='fulfilled').length,18);
  const rejected=results.filter(x=>x.status==='rejected');assert.equal(rejected.length,7);for(const value of rejected)assert.equal(value.reason.message,'AUTH_BUDGET_WAIT_LIMIT');
  assert.deepEqual([...new Set(admitted)],[0,61000]);for(const time of new Set(admitted))assert.ok(admitted.filter(x=>x===time).length<=9);assert.equal(budget.active.size,0);
});
test('same-page concurrent waiter is rejected before it can overwrite a reservation',async()=>{
  let now=0,resume;const budget=new AuthBudget({now:()=>now,sleep:ms=>new Promise(resolve=>{resume=()=>{now+=ms;resolve();};})}),page={};
  for(let i=0;i<9;i++)await budget.run({},'/api/v1/auth/login',async()=>{});
  let calls=0;const first=budget.run(page,'/api/v1/auth/login',async()=>{calls++;});
  await assert.rejects(budget.run(page,'/api/v1/auth/login',async()=>{calls++;}),/AUTH_ACTION_SCOPE_REQUIRED/);
  resume();await first;assert.equal(calls,1);assert.equal(budget.active.size,0);
});
test('checkpoint allowlist rejects dynamic or sensitive action names',async()=>{
  await assert.rejects(f.checkpoint('PRIVATE_CANARY_URL_TOKEN',async()=>{}),/FIXED_ACTION_CODE_REQUIRED/);
  let called=false;await f.checkpoint('MERCHANT_SEARCH_INPUT',async()=>{called=true;});assert.equal(called,true);
});
test('reporter retains innermost pending action, safe HTTP status and source location only',async()=>{
  const {instance:r,dir}=await reporter(),t={id:'synthetic',title:'COMPLETE_NATIVE_BROWSER_JOURNEY',annotations:[{type:'safe-http-status',description:'200'},{type:'private',description:'PRIVATE_CANARY'}]};
  r.onTestBegin(t);r.onStepBegin(t,null,{category:'test.step',title:'ADMIN_LOGIN_AND_NATIVE_APPROVAL'});
  r.onStepBegin(t,null,{category:'test.step',title:'ADMIN_DASHBOARD_VISIBLE'});r.onStepEnd(t,null,{category:'test.step',title:'ADMIN_DASHBOARD_VISIBLE'});
  r.onStepBegin(t,null,{category:'test.step',title:'MERCHANT_SEARCH_STARTED'});r.onStepBegin(t,null,{category:'test.step',title:'MERCHANT_SEARCH_INPUT'});
  r.onStepEnd(t,null,{category:'test.step',title:'MERCHANT_SEARCH_INPUT',error:{message:'PRIVATE_CANARY'}});
  r.onStepEnd(t,null,{category:'test.step',title:'MERCHANT_SEARCH_STARTED',error:{message:'PRIVATE_CANARY'}});
  r.onTestEnd(t,{status:'failed',duration:10,error:{name:'TimeoutError',message:'locator.fill: Timeout 15000ms exceeded PRIVATE_CANARY',location:{file:'/private/journey.spec.js',line:39}}});
  let output='';const write=process.stdout.write;process.stdout.write=value=>{output+=value;return true;};try{r.onEnd({status:'failed'});}finally{process.stdout.write=write;}
  const record=JSON.parse(fs.readFileSync(path.join(dir,'sanitized-browser.json'))).tests[0];
  assert.equal(record.lastCompletedActionCode,'ADMIN_DASHBOARD_VISIBLE');assert.equal(record.pendingActionCode,'MERCHANT_SEARCH_INPUT');assert.equal(record.lastObservedHttpStatus,200);
  assert.equal(record.failedStage,'ADMIN_LOGIN_AND_NATIVE_APPROVAL');assert.equal(record.diagnostic.location.line,39);
  assert.equal(output.includes('PRIVATE_CANARY'),false);assert.ok(output.includes('MERCHANT_SEARCH_INPUT'));
});
test('invalid HTTP status annotations and unclassified steps never enter action diagnostics',async()=>{
  const {instance:r,dir}=await reporter(),t={id:'synthetic',title:'COMPLETE_NATIVE_BROWSER_JOURNEY',annotations:[{type:'safe-http-status',description:'PRIVATE_CANARY'}]};
  r.onTestBegin(t);r.onStepBegin(t,null,{category:'test.step',title:'PRIVATE_CANARY'});r.onTestEnd(t,{status:'failed',duration:1,error:{message:'PRIVATE_CANARY'}});finish(r,{status:'failed'});
  const record=JSON.parse(fs.readFileSync(path.join(dir,'sanitized-browser.json'))).tests[0];assert.equal(record.lastObservedHttpStatus,null);assert.equal(record.pendingActionCode,null);assert.equal(record.diagnostic.category,'UNKNOWN');
});

test('candidate browser evidence cannot claim that every image was published',async()=>{
  const previous=process.env.E2E_FRONTEND_KIND;process.env.E2E_FRONTEND_KIND='source-built-candidate';
  try{
    const {instance:r,dir}=await reporter();r.onTestEnd({title:'DESKTOP_KEYBOARD_AND_VALIDATION'},{status:'passed',duration:1});finish(r,{status:'passed'});
    const report=JSON.parse(fs.readFileSync(path.join(dir,'sanitized-browser.json')));
    assert.equal(report.publishedImagesOnly,false);assert.equal(report.frontendArtifactKind,'source-built-candidate');assert.equal(report.success,false);
  }finally{if(previous===undefined)delete process.env.E2E_FRONTEND_KIND;else process.env.E2E_FRONTEND_KIND=previous;}
});

test('actual link field builder includes option text in implicit select labels',async()=>{
  const {default:vm}=await import('node:vm');const source=fs.readFileSync(new URL('../../frontend/assets/js/payment-links/view.js',import.meta.url),'utf8');
  const start=source.indexOf('function field('),end=source.indexOf('\n  function render',start);
  const element=(tag,text)=>({tag,text:text||'',children:[],append(...nodes){this.children.push(...nodes);},get textContent(){return this.text+this.children.map(x=>x.textContent).join('');}});
  const field=vm.runInNewContext('('+source.slice(start,end)+')',{element,state:{mutating:false}});
  for(const [label,name,options] of [['Currency','currency',[['INR','INR'],['USD','USD']]],['Payment method','paymentMethod',[['UPI','UPI'],['CARD','CARD']]]]){
    const form=element('form');const select=field(form,label,name,options[0][0],options);
    assert.notEqual(form.children[0].textContent,label);assert.equal(select.tag,'select');assert.equal(select.name,name);
    assert.equal(form.children[0].textContent,label+options.map(x=>x[1]).join(''));
  }
  const journey=fs.readFileSync(new URL('./journey.spec.js',import.meta.url),'utf8');
  assert.ok(journey.includes('select[name="currency"]'));assert.ok(journey.includes('select[name="paymentMethod"]'));
  assert.ok(journey.includes("toHaveValue('USD')"));assert.ok(journey.includes("toHaveValue('CARD')"));
  assert.equal(journey.includes("getByLabel('Currency',{exact:true})"),false);
});
test('route and HTTP categories discard checkout tokens, query values and private identifiers',()=>{
  const token='T'.repeat(43),url='http://127.0.0.1:15500/checkout/'+token+'?private=PRIVATE_CANARY';
  assert.equal(f.routeCategory(url),'PUBLIC_CHECKOUT');assert.equal(f.routeCategory('https://foreign.invalid/'+token),'OTHER_ORIGIN');
  assert.equal(f.httpCategory('http://127.0.0.1:15500/api/v1/checkout/'+token+'/pay','POST'),'CHECKOUT_PAY');
  assert.equal(f.httpCategory('http://127.0.0.1:15500/api/v1/checkout/'+token+'/pay','GET'),'OTHER_REQUEST');
  assert.equal(f.httpCategory('http://127.0.0.1:15500/api/v1/merchant/payment-links','POST'),'LINK_CREATE');
  assert.equal(f.routeCategory('http://127.0.0.1:15500/merchant/payment-links/create'),'MERCHANT_LINK_CREATE');
  assert.equal(f.routeCategory('not a URL'),'UNAVAILABLE');
});
test('selector failure records expected form and actual route but cannot attribute an old 201',async()=>{
  const annotations=f.test.info().annotations;annotations.length=0;
  await assert.rejects(f.checkpoint('CHECKOUT_CURRENCY_SELECTED',async()=>{const e=new Error('Timeout 15000ms exceeded PRIVATE_CANARY');e.name='TimeoutError';throw e;},{page:{url:()=> 'http://127.0.0.1:15500/merchant/payment-links/create'},expectedState:'LINK_CREATE_FORM'}));
  const {instance:r,dir}=await reporter(),t={id:'synthetic',title:'COMPLETE_NATIVE_BROWSER_JOURNEY',annotations:[{type:'safe-http-status',description:'201'},...annotations]};
  r.onTestBegin(t);r.onStepBegin(t,null,{category:'test.step',title:'PAYMENT_LINK_AND_CUSTOMER_CHECKOUT'});r.onStepBegin(t,null,{category:'test.step',title:'CHECKOUT_CURRENCY_SELECTED'});
  r.onTestEnd(t,{status:'failed',duration:1,error:{name:'TimeoutError',message:'Timeout 15000ms exceeded PRIVATE_CANARY',location:{file:'journey.spec.js',line:168}}});finish(r,{status:'failed'});
  const record=JSON.parse(fs.readFileSync(path.join(dir,'sanitized-browser.json'))).tests[0];
  assert.equal(record.expectedUICategory,'LINK_CREATE_FORM');assert.equal(record.actualRouteCategory,'MERCHANT_LINK_CREATE');assert.equal(record.lastRelevantHttpStatus,null);assert.equal(record.lastObservedHttpStatus,201);
  assert.equal(JSON.stringify(record).includes('PRIVATE_CANARY'),false);
});
test('HTTP correlation accepts only the expected endpoint within the active checkpoint',async()=>{
  for(const [url,method,status,expected] of [['/api/v1/checkout/'+'T'.repeat(43)+'/pay','POST',200,200],['/api/v1/payments/'+'a'.repeat(36)+'/refund','POST',201,null]]){
    const annotations=f.test.info().annotations;annotations.length=0;
    const response={url:()=>f.ORIGIN+url,status:()=>status,request:()=>({method:()=>method})};
    await assert.rejects(f.checkpoint('CHECKOUT_SUBMITTED',async()=>{await f.responseFor({waitForResponse:()=>Promise.resolve(response)},method,url);throw new Error('SYNTHETIC_UI_FAILURE');},{page:{url:()=> f.ORIGIN+'/checkout/'+'T'.repeat(43)},expectedState:'PAID_RECEIPT',expectedHttp:'CHECKOUT_PAY'}));
    const context=JSON.parse(annotations.find(x=>x.type==='safe-ui-context').description);assert.equal(context.httpStatus,expected);assert.equal(context.routeCode,'PUBLIC_CHECKOUT');assert.equal(JSON.stringify(context).includes('T'.repeat(43)),false);
  }
});
test('malformed or mismatched UI context never leaks into the sanitized reporter',async()=>{
  const {instance:r,dir}=await reporter(),t={id:'synthetic',title:'COMPLETE_NATIVE_BROWSER_JOURNEY',annotations:[{type:'safe-ui-context',description:JSON.stringify({actionCode:'CHECKOUT_SUBMITTED',expectedState:'PRIVATE_CANARY',routeCode:'PUBLIC_CHECKOUT',httpStatus:200,httpCode:'CHECKOUT_PAY'})}]};
  r.onTestBegin(t);r.onStepBegin(t,null,{category:'test.step',title:'CHECKOUT_SUBMITTED'});r.onTestEnd(t,{status:'failed',duration:1,error:{message:'PRIVATE_CANARY'}});finish(r,{status:'failed'});
  const record=JSON.parse(fs.readFileSync(path.join(dir,'sanitized-browser.json'))).tests[0];assert.equal(record.expectedUICategory,null);assert.equal(record.lastRelevantHttpStatus,null);assert.equal(JSON.stringify(record).includes('PRIVATE_CANARY'),false);
  await assert.rejects(f.checkpoint('CHECKOUT_SUBMITTED',async()=>{},{expectedState:'PRIVATE_CANARY'}),/FIXED_ACTION_CODE_REQUIRED/);
});

test('raw payment DTO numbers normalize only for synthetic browser comparisons',async()=>{
  const payment=await f.body({status:()=>200,text:async()=>'{"amount":25.00,"currency":"USD"}'});
  assert.equal(f.exactAmount(payment.amount),'25.00');
  const journey=fs.readFileSync(new URL('./journey.spec.js',import.meta.url),'utf8');
  assert.ok(journey.includes("exactAmount(linkedPayment.amount)==='25.00'"));assert.ok(journey.includes("toContainText('25.00 USD')"));
});
