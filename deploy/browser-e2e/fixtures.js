import fs from 'node:fs';
import path from 'node:path';
import { test as base, expect } from '@playwright/test';
export const ORIGIN = 'http://127.0.0.1:15500';
export function requireSafe(ok, code) { if (!ok) throw new Error(code); }
export function guard(env = process.env) {
  requireSafe(env.GITHUB_ACTIONS === 'true' && env.RUNNER_OS === 'Linux' && env.RUNNER_ENVIRONMENT === 'github-hosted', 'HOSTED_RUNNER_REQUIRED');
  requireSafe(env.GITHUB_REPOSITORY === 'bhupirao/paymesh-ai' && env.GITHUB_REF === 'refs/heads/main' && env.GITHUB_EVENT_NAME === 'workflow_dispatch', 'MANUAL_MAIN_REQUIRED');
  requireSafe(env.E2E_VERIFY_QWEN === 'true' && ['', 'unix:///var/run/docker.sock'].includes(env.DOCKER_HOST || ''), 'FIXED_LOCAL_STACK_REQUIRED');
  requireSafe(/^\d+$/.test(env.GITHUB_RUN_ID || '') && /^\d+$/.test(env.GITHUB_RUN_ATTEMPT || ''), 'RUN_ID_REQUIRED');
  const project = `paymesh-e2e-${env.GITHUB_RUN_ID}-${env.GITHUB_RUN_ATTEMPT}`;
  const folder = path.join(fs.realpathSync(env.RUNNER_TEMP), project);
  requireSafe(env.E2E_PROJECT === project && env.E2E_DIR === folder && env.E2E_ENV === path.join(folder, 'container.env'), 'FIXTURE_SCOPE_REQUIRED');
  const stat = fs.lstatSync(folder);
  requireSafe(stat.isDirectory() && !stat.isSymbolicLink() && !(stat.mode & 0o077) && stat.uid === process.getuid(), 'PRIVATE_FIXTURE_DIRECTORY_REQUIRED');
  return folder;
}
export function privateDirectory(name, env = process.env) {
  requireSafe(name === 'browser-private-output', 'FIXED_OUTPUT_DIRECTORY_REQUIRED');
  const run = guard(env); // Canonical temp parent; private, owned, non-symlink run.
  const folder = path.resolve(run, name);
  requireSafe(fs.realpathSync(run) === run && folder !== run && path.dirname(folder) === run
    && path.relative(run, folder) === name, 'PRIVATE_OUTPUT_REQUIRED');
  let fd;
  try {
    // No recursive creation/chmod: the private run must already exist.
    try { fs.mkdirSync(folder, { mode: 0o700 }); }
    catch (error) { if (error.code !== 'EEXIST') throw error; }
    const before = fs.lstatSync(folder);
    requireSafe(before.isDirectory() && !before.isSymbolicLink() && before.uid === process.getuid()
      && fs.realpathSync(folder) === folder, 'PRIVATE_OUTPUT_REQUIRED');
    fd = fs.openSync(folder, fs.constants.O_RDONLY | fs.constants.O_DIRECTORY | fs.constants.O_NOFOLLOW);
    const opened = fs.fstatSync(fd);
    const current = fs.lstatSync(folder);
    requireSafe(opened.isDirectory() && opened.uid === process.getuid()
      && opened.dev === before.dev && opened.ino === before.ino
      && current.isDirectory() && !current.isSymbolicLink()
      && current.dev === opened.dev && current.ino === opened.ino, 'PRIVATE_OUTPUT_REQUIRED');
    // Playwright can recreate this exact leaf with its default umask. Secure the
    // validated inode through its no-follow descriptor, never a substituted path.
    fs.fchmodSync(fd, 0o700);
    const secured = fs.fstatSync(fd), after = fs.lstatSync(folder);
    requireSafe(secured.isDirectory() && secured.uid === process.getuid() && (secured.mode & 0o7777) === 0o700
      && after.isDirectory() && !after.isSymbolicLink() && after.uid === process.getuid() && (after.mode & 0o7777) === 0o700
      && after.dev === secured.dev && after.ino === secured.ino
      && fs.realpathSync(folder) === folder, 'PRIVATE_OUTPUT_REQUIRED');
    return folder;
  } catch { throw new Error('PRIVATE_OUTPUT_REQUIRED'); }
  finally { if (fd !== undefined) fs.closeSync(fd); }
}
export function credential(name) {
  requireSafe(['admin_password', 'merchant_password'].includes(name), 'FIXED_CREDENTIAL_REQUIRED');
  const folder = path.join(guard(), 'secrets');
  const directory = fs.lstatSync(folder);
  requireSafe(directory.isDirectory() && !directory.isSymbolicLink() && !(directory.mode & 0o077), 'PRIVATE_SECRET_DIRECTORY_REQUIRED');
  const file = path.join(folder, name), stat = fs.lstatSync(file);
  requireSafe(stat.isFile() && !stat.isSymbolicLink() && stat.uid === process.getuid() && !(stat.mode & 0o022) && stat.size >= 20 && stat.size <= 72, 'FIXTURE_CREDENTIAL_INVALID');
  return fs.readFileSync(file, 'utf8');
}
export const accounts = {
  admin: 'ci-admin@e2e.example.test',
  a: 'browser-a@e2e.example.test',
  b: 'browser-b@e2e.example.test'
};
export function recordBrowserReady(browser, title) {
  const allowed=['COMPLETE_NATIVE_BROWSER_JOURNEY','MOBILE_KEYBOARD_AND_VALIDATION','DESKTOP_KEYBOARD_AND_VALIDATION'];
  requireSafe(allowed.includes(title) && browser.isConnected() && browser.browserType().name()==='chromium', 'CHROMIUM_WITNESS_REQUIRED');
  fs.writeFileSync(path.join(guard(),'browser-launch-'+title+'.json'), JSON.stringify({testCode:title,chromiumLaunchStatus:'SUCCEEDED'}), {mode:0o600,flag:'wx'});
}
export const test = base.extend({
  browserDiagnostics: [async ({ browser }, use, testInfo) => {
    recordBrowserReady(browser, testInfo.title);
    await use();
  }, { auto: true }],
  context: async ({ context }, use) => {
    guard();
    await restrictNetwork(context);
    await use(context);
  }
});
export { expect };
export async function restrictNetwork(context) {
  await context.route('**/*', route => {
    let allowed = false;
    try { allowed = new URL(route.request().url()).origin === ORIGIN; } catch { /* deny */ }
    return allowed ? route.continue() : route.abort('blockedbyclient');
  });
}
export async function newPage(browser) {
  const context = await browser.newContext({ baseURL: ORIGIN, viewport: { width: 1440, height: 1000 }, acceptDownloads: false, serviceWorkers: 'block' });
  await restrictNetwork(context);
  return { context, page: await context.newPage() };
}
export async function login(page, role, account) {
  await page.goto(`/${role}/login`);
  await page.locator('#login').fill(accounts[account]);
  await page.locator('#password').fill(credential(account === 'admin' ? 'admin_password' : 'merchant_password'));
  await page.locator('#login-submit').click();
  await expect(page).toHaveURL(`${ORIGIN}/${role}/dashboard`);
  await expect(page.locator('#identity')).toBeVisible();
}
export function responseFor(page, method, pathname) {
  return page.waitForResponse(response => {
    const url = new URL(response.url());
    return url.origin === ORIGIN && response.request().method() === method && (typeof pathname === 'string' ? url.pathname === pathname : pathname.test(url.pathname));
  }, { timeout: 55_000 });
}
export async function body(response, statuses = [200]) {
  requireSafe(statuses.includes(response.status()), 'BROWSER_HTTP_STATUS_MISMATCH');
  const text = await response.text();
  requireSafe(Buffer.byteLength(text) <= 524288, 'BROWSER_RESPONSE_TOO_LARGE');
  try { return JSON.parse(text); } catch { throw new Error('BROWSER_RESPONSE_INVALID'); }
}
export function modelSuccess(value) {
  const result = value.turn?.response || value.investigation || value;
  requireSafe(result.analysisMode === 'RAG_LLM' && result.generationStatus === 'SUCCEEDED' && result.knowledgeReferences?.length > 0, 'REAL_MODEL_REQUIRED');
  return result;
}
export async function noOverflow(page) {
  requireSafe(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'HORIZONTAL_OVERFLOW');
}
export async function openHistory(root) {
  const summary = root.locator('details.conversation-history > summary');
  if (!await root.locator('details.conversation-history').evaluate(node => node.open)) await summary.click();
}
export async function safeDialog(page, action, accept = true) {
  const handler = dialog => accept ? dialog.accept() : dialog.dismiss();
  page.on('dialog', handler);
  try { return await action(); } finally { page.off('dialog', handler); }
}

export function exactAmount(value) {
  const match = /^(0|[1-9][0-9]*)(?:[.]([0-9]{1,2}))?$/.exec(String(value));
  requireSafe(Boolean(match), 'EXACT_AMOUNT_REQUIRED');
  return match[1] + '.' + (match[2] || '').padEnd(2, '0');
}
export async function logout(page) {
  const reply = responseFor(page, 'POST', '/api/v1/auth/logout');
  await page.locator('#logout').click();
  await body(await reply);
  await expect(page.locator('#login-form')).toBeVisible();
}
