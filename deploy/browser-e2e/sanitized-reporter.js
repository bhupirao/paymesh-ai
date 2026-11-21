// Never serialize Playwright TestResult, Error, attachments, URLs or browser state.
import fs from 'node:fs';
import path from 'node:path';
import { guard, ACTION_CODES } from './fixtures.js';
const CODES = new Set(['COMPLETE_NATIVE_BROWSER_JOURNEY', 'MOBILE_KEYBOARD_AND_VALIDATION', 'DESKTOP_KEYBOARD_AND_VALIDATION', 'MERCHANT_REGISTRATION_VALIDATION', 'ADMIN_LOGIN_AND_NATIVE_APPROVAL', 'DASHBOARD_SESSION_AND_ROLE_PROTECTION', 'PAYMENT_CREATION_PROCESSING_AND_LIST', 'MERCHANT_OWNERSHIP_ISOLATION', 'NATIVE_INVESTIGATION_REAL_QWEN', 'PARTIAL_AND_FULL_REFUND_UI', 'PAYMENT_LINK_AND_CUSTOMER_CHECKOUT', 'MERCHANT_ADMIN_CHAT_AND_SAVED_HISTORY', 'CROSS_TAB_LOGOUT_AND_PROTECTED_ROUTE']);
// Inspect bounded error text only to select constants; never retain text/stack.
const SAFE_ERRORS = new Set(['HOSTED_RUNNER_REQUIRED','MANUAL_MAIN_REQUIRED','FIXED_LOCAL_STACK_REQUIRED','RUN_ID_REQUIRED','FIXTURE_SCOPE_REQUIRED','PRIVATE_FIXTURE_DIRECTORY_REQUIRED','PRIVATE_SECRET_DIRECTORY_REQUIRED','FIXTURE_CREDENTIAL_INVALID','BROWSER_HTTP_STATUS_MISMATCH','BROWSER_RESPONSE_TOO_LARGE','BROWSER_RESPONSE_INVALID','REAL_MODEL_REQUIRED','HORIZONTAL_OVERFLOW','EXACT_AMOUNT_REQUIRED','OWNERSHIP_DENIAL_REQUIRED','RESTORE_INVOKED_MODEL','AUTOMATIC_AI_REQUEST','SHIFT_ENTER_SENT_QUESTION','INVESTIGATION_SCOPE','REGISTRATION_STATUS','UNIQUE_PENDING_MERCHANT_REQUIRED','CREATED_PAYMENT_CONTRACT','PAYMENT_PROCESSING_STATUS','REFUND_RECORD','FIXED_CHECKOUT_URL','PAID_CHECKOUT_REQUIRED','VISIBLE_ANSWER_REQUIRED','SAVED_TURN_REQUIRED','OWNED_HISTORY_SEARCH','OTHER_MERCHANT_PRIVATE_HISTORY','ADMIN_MERCHANT_HISTORY_ISOLATION','CHROMIUM_WITNESS_REQUIRED','FIXED_OUTPUT_DIRECTORY_REQUIRED','PRIVATE_OUTPUT_REQUIRED','FIXED_CREDENTIAL_REQUIRED','AUTH_LIMIT_OBSERVED','AUTH_ACTION_SCOPE_REQUIRED','AUTH_BUDGET_WAIT_LIMIT','FIXED_BROWSER_TARGET_REQUIRED','AUTH_OBSERVATION_FAILED','FIXED_ACTION_CODE_REQUIRED','SESSION_RESTORE_HTTP_STATUS','APPROVAL_STATE_REQUIRED']);
export function classifyFailure(error, status) {
  const message = (typeof error?.message === 'string' ? error.message.slice(0,8192) : '').replace(/\u001b\[[0-?]*[ -/]*[@-~]/g, '');
  const firstLine = message.split(/\r?\n/,1)[0].trim().replace(/^Error:[ \t]*/, '');
  let category='UNKNOWN', errorCode='UNCLASSIFIED_TEST_FAILURE', timeoutCategory='NONE', assertionCategory='NONE';
  const known = SAFE_ERRORS.has(firstLine) ? firstLine : null;
  if (known) { category='SAFE_TEST_GUARD'; errorCode=known; }
  else if (/Executable (?:doesn't|does not) exist/.test(message)) { category='BROWSER_LAUNCH'; errorCode='BROWSER_EXECUTABLE_MISSING'; }
  else if (/error while loading shared libraries|Host system is missing dependencies/.test(message)) { category='BROWSER_LAUNCH'; errorCode='BROWSER_SYSTEM_DEPENDENCY_MISSING'; }
  else if (/First argument must use the object destructuring pattern|Fixture .{0,120}(?:references itself|unknown|scope)|unknown parameter|worker fixture.{0,100}test fixture/i.test(message)) { category='FIXTURE_CONFIGURATION'; errorCode='FIXTURE_CONFIGURATION_ERROR'; }
  else if (/worker process exited unexpectedly/i.test(message)) { category='WORKER_INFRASTRUCTURE'; errorCode='WORKER_EXITED'; }
  else if (/browserType[.]launch/.test(message)) { category='BROWSER_LAUNCH'; errorCode='CHROMIUM_LAUNCH_FAILED'; }
  else if (status==='timedOut' || error?.name==='TimeoutError' || /Test timeout of \d+ms exceeded|Timeout \d+ms exceeded/.test(message)) {
    category='TIMEOUT';errorCode='TEST_OR_ACTION_TIMEOUT';
    timeoutCategory=status==='timedOut'?'TEST_TIMEOUT':/page[.]goto/.test(message)?'NAVIGATION_TIMEOUT':/waitForResponse/.test(message)?'RESPONSE_TIMEOUT':'ACTION_TIMEOUT';
  } else if (error?.name==='AssertionError' || error?.matcherResult || /expect\(/.test(message)) {
    category='ASSERTION';errorCode='UI_ASSERTION_FAILED';
    const kinds={toBeVisible:'VISIBILITY',toBeHidden:'VISIBILITY',toBeFocused:'FOCUS',toBeEnabled:'ENABLED',toBeDisabled:'ENABLED',toHaveCount:'COUNT',toHaveURL:'URL_MATCH',toHaveText:'TEXT_MATCH',toContainText:'TEXT_MATCH',toHaveValue:'VALUE',toHaveAttribute:'ATTRIBUTE'};
    assertionCategory=Object.entries(kinds).find(([key])=>message.includes(key))?.[1]||'OTHER_ASSERTION';
  } else if (['TypeError','ReferenceError','SyntaxError','RangeError'].includes(error?.name) || /^(?:TypeError|ReferenceError|SyntaxError|RangeError):/.test(message)) {
    category='TEST_RUNTIME';errorCode='TEST_RUNTIME_ERROR';
  } else if (/ENOENT|EACCES/.test(message)) { category='FIXTURE_FILESYSTEM';errorCode='FIXTURE_FILE_UNAVAILABLE'; }
  const location=error?.location;
  const file=typeof location?.file==='string'?path.basename(location.file):'';
  const safeLocation=['accessibility.spec.js','journey.spec.js','fixtures.js','playwright.config.js'].includes(file) && Number.isInteger(location.line) && location.line>0 && location.line<10000 ? {file,line:location.line} : null;
  return {category,errorCode,timeoutCategory,assertionCategory,location:safeLocation};
}
function elapsed(value) { return Number.isFinite(value) && value>=0 && value<=1800000 ? Math.round(value) : 0; }
function witness(folder, code) {
  if (!['COMPLETE_NATIVE_BROWSER_JOURNEY','MOBILE_KEYBOARD_AND_VALIDATION','DESKTOP_KEYBOARD_AND_VALIDATION'].includes(code)) return 'NOT_OBSERVED';
  try {
    const file=path.join(folder,'browser-launch-'+code+'.json'),stat=fs.lstatSync(file);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.uid!==process.getuid() || stat.mode&0o077 || stat.size>512) return 'NOT_OBSERVED';
    const data=JSON.parse(fs.readFileSync(file,'utf8'));
    return data.testCode===code && data.chromiumLaunchStatus==='SUCCEEDED' ? 'SUCCEEDED' : 'NOT_OBSERVED';
  } catch { return 'NOT_OBSERVED'; }
}

function loginWitness(folder, code) {
  if(!['COMPLETE_NATIVE_BROWSER_JOURNEY','MOBILE_KEYBOARD_AND_VALIDATION','DESKTOP_KEYBOARD_AND_VALIDATION'].includes(code))return null;
  try {
    const file=path.join(folder,'browser-login-'+code+'.json'),stat=fs.lstatSync(file);
    if(!stat.isFile()||stat.isSymbolicLink()||stat.uid!==process.getuid()||stat.mode&0o077||stat.size>1024)return null;
    const value=JSON.parse(fs.readFileSync(file,'utf8'));
    if(value.testCode!==code||!['MERCHANT','ADMIN'].includes(value.portalRole)
      ||!(value.httpStatus===null||Number.isInteger(value.httpStatus)&&value.httpStatus>=100&&value.httpStatus<=599)
      ||!['MERCHANT_LOGIN','MERCHANT_DASHBOARD','MERCHANT_SIGNUP','ADMIN_LOGIN','ADMIN_DASHBOARD','OTHER_ORIGIN','OTHER_ROUTE','UNAVAILABLE'].includes(value.routeCode)
      ||typeof value.suffixPresent!=='boolean'
      ||!['NO_FEEDBACK','LOGIN_PENDING','CREDENTIALS_REJECTED','INVALID_AUTH_RESPONSE','SESSION_INVALID','SESSION_EXPIRED','STALE_RESPONSE','ROLE_REJECTED','OTHER_FEEDBACK','UNAVAILABLE','RATE_LIMITED'].includes(value.feedbackCode))return null;
    return {portalRole:value.portalRole,httpStatus:value.httpStatus,routeCode:value.routeCode,suffixPresent:value.suffixPresent,feedbackCode:value.feedbackCode};
  } catch {return null;}
}

export default class SanitizedReporter {
  constructor() { this.tests = []; this.steps = []; this.infrastructureError = false; this.activeStage = new Map(); this.failedStage = new Map(); this.began = new Map(); this.infrastructureFailure = null; this.lastAction=new Map();this.pendingAction=new Map();this.actionStack=new Map(); }
  onStdOut() {}
  onStdErr() {}
  onError(error) { this.infrastructureError = true; this.infrastructureFailure=classifyFailure(error,'failed'); }
  onTestBegin(test) { this.began.set(test.id,Date.now()); this.activeStage.set(test.id,'HOOK_OR_FIXTURE_SETUP'); }
  onStepBegin(test, result, step) {
    if(step.category==='test.step' && ACTION_CODES.has(step.title)){
      const stack=this.actionStack.get(test.id)||[];stack.push(step.title);this.actionStack.set(test.id,stack);this.pendingAction.set(test.id,step.title);
    }
    if(step.category==='test.step' && CODES.has(step.title)) this.activeStage.set(test.id,step.title);
  }
  onStepEnd(test, result, step) {
    if(step.category==='test.step'&&ACTION_CODES.has(step.title)){
      if(!step.error){this.lastAction.set(test.id,step.title);const stack=this.actionStack.get(test.id)||[];stack.pop();this.pendingAction.set(test.id,stack.at(-1)||null);}
      // Retain the innermost failed checkpoint; never overwrite with its parent.
      return;
    }
    if (this.steps.length >= 64) { this.infrastructureError = true; return; }
    if(step.error && !this.failedStage.has(test?.id)) this.failedStage.set(test?.id,CODES.has(step.title)?step.title:this.activeStage.get(test?.id)||'HOOK_OR_FIXTURE_SETUP');
    if (step.category === 'test.step') this.steps.push({ code: CODES.has(step.title) ? step.title : 'UNCLASSIFIED_STEP', passed: !step.error, durationMs: elapsed(step.duration) });
    if(step.category==='test.step' && !step.error) this.activeStage.set(test?.id,'TEST_BODY_OR_TEARDOWN');
  }
  onTestEnd(test, result) {
    if (this.tests.length >= 16) { this.infrastructureError = true; return; }
    const code=CODES.has(test.title)?test.title:'UNCLASSIFIED_TEST';
    const launch=witness(guard(),code),failed=['failed','timedOut','interrupted'].includes(result.status);
    const diagnostic=failed?classifyFailure(result.error||result.errors?.[0],result.status):null;
    const status=['passed','failed','timedOut','skipped','interrupted'].includes(result.status)?result.status:'unknown';
    this.tests.push({code,status,durationMs:elapsed(result.duration),elapsedMs:elapsed(Date.now()-(this.began.get(test.id)||Date.now())),
      chromiumLaunchStatus:launch==='SUCCEEDED'?'SUCCEEDED':diagnostic?.category==='BROWSER_LAUNCH'?'FAILED':'NOT_OBSERVED',
      failedStage:failed?(this.failedStage.get(test.id)||this.activeStage.get(test.id)||'HOOK_OR_FIXTURE_SETUP'):null,
      diagnostic,loginState:failed?loginWitness(guard(),code):null,
      lastCompletedActionCode:this.lastAction.get(test.id)||null,pendingActionCode:this.pendingAction.get(test.id)||null,
      lastObservedHttpStatus:(test.annotations||[]).filter(a=>a.type==='safe-http-status'&&/^[1-5][0-9]{2}$/.test(a.description)).map(a=>Number(a.description)).at(-1)||null});
  }
  onEnd(result) {
    const folder = guard();
    const requiredTests = ['COMPLETE_NATIVE_BROWSER_JOURNEY','MOBILE_KEYBOARD_AND_VALIDATION','DESKTOP_KEYBOARD_AND_VALIDATION'];
    const complete = this.tests.length === 3 && requiredTests.every(code => this.tests.some(t => t.code === code && t.status === 'passed')) && [...CODES].filter(code => !requiredTests.includes(code)).every(code => this.steps.some(s => s.code === code && s.passed));
    const report = { success: result.status === 'passed' && complete && !this.infrastructureError && this.tests.every(t => t.status === 'passed'), tests: this.tests, steps: this.steps, infrastructureError: this.infrastructureError, infrastructureFailure: this.infrastructureFailure, browser: 'chromium', nativeBrowserTested: this.tests.some(t => t.status === 'passed') || this.steps.length > 0, publishedImagesOnly: process.env.E2E_FRONTEND_KIND !== 'source-built-candidate', frontendArtifactKind: process.env.E2E_FRONTEND_KIND === 'source-built-candidate' ? 'source-built-candidate' : 'published-release', retries: 0, rawDiagnosticsRetained: false, modelInferenceVerified: this.steps.some(s => s.code === 'NATIVE_INVESTIGATION_REAL_QWEN' && s.passed) && this.steps.some(s => s.code === 'MERCHANT_ADMIN_CHAT_AND_SAVED_HISTORY' && s.passed) };
    const output = JSON.stringify(report, null, 2);
    if (Buffer.byteLength(output) > 32768) throw new Error('BROWSER_REPORT_TOO_LARGE');
    fs.writeFileSync(path.join(folder, 'sanitized-browser.json'), output + '\n', { mode: 0o600, flag: 'wx' });
    // Emit ONLY already-allowlisted scalar fields, never Error/TestResult.
    for (const t of this.tests.filter(t => ['failed','timedOut','interrupted'].includes(t.status))) {
      const d = t.diagnostic || classifyFailure(undefined, t.status);
      process.stdout.write('BROWSER_FAILURE_DIAGNOSTIC=' + JSON.stringify({testCode:t.code,stageCode:t.failedStage,
        category:d.category,errorCode:d.errorCode,elapsedMs:t.elapsedMs,chromiumLaunchStatus:t.chromiumLaunchStatus,
        assertionCategory:d.assertionCategory,timeoutCategory:d.timeoutCategory,loginState:t.loginState,location:d.location,
        lastCompletedActionCode:t.lastCompletedActionCode,pendingActionCode:t.pendingActionCode,lastObservedHttpStatus:t.lastObservedHttpStatus}) + '\n');
    }
    if (this.infrastructureError) {
      const d = this.infrastructureFailure || classifyFailure(undefined, 'failed');
      process.stdout.write('BROWSER_FAILURE_DIAGNOSTIC=' + JSON.stringify({testCode:'INFRASTRUCTURE',stageCode:'RUNNER_OR_CONFIGURATION',
        category:d.category,errorCode:d.errorCode,elapsedMs:0,chromiumLaunchStatus:'NOT_OBSERVED',
        assertionCategory:d.assertionCategory,timeoutCategory:d.timeoutCategory}) + '\n');
    }
    process.stdout.write(report.success ? 'NATIVE_CHROMIUM_E2E_PASS\n' : 'NATIVE_CHROMIUM_E2E_FAILED_NO_RAW_OUTPUT\n');
    return { status: report.success ? 'passed' : 'failed' };
  }
}
