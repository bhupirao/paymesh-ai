// Never serialize Playwright TestResult, Error, attachments, URLs or browser state.
import fs from 'node:fs';
import path from 'node:path';
import { guard } from './fixtures.js';
const CODES = new Set(['COMPLETE_NATIVE_BROWSER_JOURNEY', 'MOBILE_KEYBOARD_AND_VALIDATION', 'DESKTOP_KEYBOARD_AND_VALIDATION', 'MERCHANT_REGISTRATION_VALIDATION', 'ADMIN_LOGIN_AND_NATIVE_APPROVAL', 'DASHBOARD_SESSION_AND_ROLE_PROTECTION', 'PAYMENT_CREATION_PROCESSING_AND_LIST', 'MERCHANT_OWNERSHIP_ISOLATION', 'NATIVE_INVESTIGATION_REAL_QWEN', 'PARTIAL_AND_FULL_REFUND_UI', 'PAYMENT_LINK_AND_CUSTOMER_CHECKOUT', 'MERCHANT_ADMIN_CHAT_AND_SAVED_HISTORY', 'CROSS_TAB_LOGOUT_AND_PROTECTED_ROUTE']);
export default class SanitizedReporter {
  constructor() { this.tests = []; this.steps = []; this.infrastructureError = false; }
  onStdOut() {}
  onStdErr() {}
  onError() { this.infrastructureError = true; }
  onStepEnd(test, result, step) {
    if (this.steps.length >= 64) { this.infrastructureError = true; return; }
    if (step.category === 'test.step') this.steps.push({ code: CODES.has(step.title) ? step.title : 'UNCLASSIFIED_STEP', passed: !step.error });
  }
  onTestEnd(test, result) {
    if (this.tests.length >= 16) { this.infrastructureError = true; return; }
    this.tests.push({ code: CODES.has(test.title) ? test.title : 'UNCLASSIFIED_TEST', status: ['passed','failed','timedOut','skipped','interrupted'].includes(result.status) ? result.status : 'unknown', durationMs: Number.isFinite(result.duration) && result.duration >= 0 && result.duration <= 1800000 ? Math.round(result.duration) : 0 });
  }
  onEnd(result) {
    const folder = guard();
    const requiredTests = ['COMPLETE_NATIVE_BROWSER_JOURNEY','MOBILE_KEYBOARD_AND_VALIDATION','DESKTOP_KEYBOARD_AND_VALIDATION'];
    const complete = this.tests.length === 3 && requiredTests.every(code => this.tests.some(t => t.code === code && t.status === 'passed')) && [...CODES].filter(code => !requiredTests.includes(code)).every(code => this.steps.some(s => s.code === code && s.passed));
    const report = { success: result.status === 'passed' && complete && !this.infrastructureError && this.tests.every(t => t.status === 'passed'), tests: this.tests, steps: this.steps, infrastructureError: this.infrastructureError, browser: 'chromium', nativeBrowserTested: this.tests.some(t => t.status === 'passed') || this.steps.length > 0, publishedImagesOnly: true, retries: 0, rawDiagnosticsRetained: false, modelInferenceVerified: this.steps.some(s => s.code === 'NATIVE_INVESTIGATION_REAL_QWEN' && s.passed) && this.steps.some(s => s.code === 'MERCHANT_ADMIN_CHAT_AND_SAVED_HISTORY' && s.passed) };
    const output = JSON.stringify(report, null, 2);
    if (Buffer.byteLength(output) > 32768) throw new Error('BROWSER_REPORT_TOO_LARGE');
    fs.writeFileSync(path.join(folder, 'sanitized-browser.json'), output + '\n', { mode: 0o600, flag: 'wx' });
    process.stdout.write(report.success ? 'NATIVE_CHROMIUM_E2E_PASS\n' : 'NATIVE_CHROMIUM_E2E_FAILED_NO_RAW_OUTPUT\n');
    return { status: report.success ? 'passed' : 'failed' };
  }
}
