/** Real production browser/actions. Raw credentials, HTTP and child logs stay private. */
import assert from 'node:assert/strict';
import { createHash, randomBytes, randomUUID } from 'node:crypto';
import { createServer as createHttpsServer } from 'node:https';
import { request as httpRequest } from 'node:http';
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, readdirSync, openSync, closeSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { spawn } from 'node:child_process';

const config = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const requireOwner = createRequire(join(config.owner, 'package.json'));
const { chromium } = requireOwner('@playwright/test');
const postgres = requireOwner('postgres');
const report = {
  status: 'running', controls: [], upstreamPageTests: 0,
  credentialsCaptured: false, rawHttpUploaded: false, traceEnabled: false,
  origin: 'owned HTTPS loopback', productionServer: true,
};
let stage = 'https-proxy';
const save = () => writeFileSync(config.receipt, JSON.stringify(report, null, 2) + '\n');
const pass = name => { report.controls.push({ name, passed: true }); save(); };
const check = (value, label) => {
  if (!value) { report.failedCheck = label; save(); }
  assert.ok(value, label);
};
const contexts = [];
let browser;
const sql = postgres(process.env.POSTGRES_URL, { max: 2, connect_timeout: 5 });
const proxy = createHttpsServer({
  key: readFileSync(join(config.private, 'key.pem')),
  cert: readFileSync(join(config.private, 'cert.pem')),
}, (req, res) => {
  const origin = new URL(config.origin);
  const forward = httpRequest({ host: '127.0.0.1', port: config.nextPort, path: req.url,
    method: req.method, headers: { ...req.headers, host: origin.host,
      'x-forwarded-host': origin.host, 'x-forwarded-proto': 'https' } }, upstream => {
    res.writeHead(upstream.statusCode, upstream.headers); upstream.pipe(res);
  });
  forward.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end(); });
  req.on('error', () => forward.destroy());
  let bytes = 0;
  req.on('data', data => { bytes += data.length; if (bytes > 1048576) { forward.destroy(); req.destroy(); } });
  req.pipe(forward);
});
proxy.requestTimeout = 30000;
proxy.headersTimeout = 15000;

async function context() {
  const value = await browser.newContext({ baseURL: config.origin, ignoreHTTPSErrors: true });
  await value.route('**/*', route => new URL(route.request().url()).origin === config.origin ? route.continue() : route.abort());
  contexts.push(value);
  return value;
}
async function pageFor(ctx, path) {
  const page = await ctx.newPage();
  page.setDefaultTimeout(20000);
  await page.goto(path, { waitUntil: 'domcontentloaded' });
  return page;
}
async function submit(page, email, password, button, state) {
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  // Reach the real server validator rather than stopping in HTML input validation.
  await page.locator('form').evaluate(form => { form.noValidate = true; });
  const awaited = page.waitForResponse(response => response.request().method() === 'POST' && Boolean(response.request().headers()['next-action']));
  await page.getByRole('button', { name: button, exact: true }).click();
  const response = await awaited;
  report.lastAction = { httpStatus: response.status(),
    responseIsRsc: (response.headers()['content-type'] ?? '').includes('text/x-component'), expectedState: state };
  save();
  check(response.status() === 200 && (response.headers()['content-type'] ?? '').includes('text/x-component'), 'real action response');
  const body = await response.text();
  report.lastAction.observedStates = ['idle', 'in_progress', 'success', 'failed', 'invalid_data', 'user_exists'].filter(value => body.includes('"' + value + '"'));
  save();
  check(body.includes('"' + state + '"'), 'expected action state');
  return response.request();
}
async function count(email) {
  const rows = await sql`select count(*)::int as count from "User" where email=${email}`;
  report.lastDatabaseCount = rows[0].count;
  return rows[0].count;
}
async function session(ctx) {
  const response = await ctx.request.get('/api/auth/session');
  check(response.status() === 200, 'session response');
  return response.json();
}
async function regular(ctx, email) {
  const value = await session(ctx);
  check(value.user?.type === 'regular' && value.user.email === email && typeof value.user.id === 'string', 'real credential session');
  return value.user.id;
}
async function guest(ctx) {
  const type = (await session(ctx)).user?.type;
  report.lastSessionType = ['guest', 'regular'].includes(type) ? type : 'absent-or-unknown';
  check(type !== 'regular', 'refusal must not create a regular session');
}
async function upstreamPages() {
  const path = join(config.private, 'upstream.config.mjs');
  const result = join(config.private, 'upstream-report.json');
  const definition = { testDir: join(config.owner, 'tests'), testMatch: '**/e2e/auth.test.ts',
    retries: 0, workers: 1, timeout: 30000,
    outputDir: join(config.private, 'upstream-results'),
    reporter: [['json', { outputFile: result }]],
    use: { baseURL: config.origin, ignoreHTTPSErrors: true, trace: 'off', screenshot: 'off', video: 'off' } };
  writeFileSync(path, 'export default ' + JSON.stringify(definition) + ';\n');
  const stdout = openSync(join(config.private, 'upstream.stdout'), 'wx');
  const stderr = openSync(join(config.private, 'upstream.stderr'), 'wx');
  const child = spawn(process.execPath, [requireOwner.resolve('@playwright/test/cli'), 'test', '--config', path], {
    cwd: config.owner, env: process.env, stdio: ['ignore', stdout, stderr],
  });
  const deadline = setTimeout(() => child.kill('SIGTERM'), 180000);
  try {
    const code = await new Promise((resolve, reject) => { child.on('error', reject); child.on('exit', resolve); });
    check(code === 0, 'unchanged upstream page tests');
    const data = JSON.parse(readFileSync(result, 'utf8'));
    check(data.stats.expected === 4 && data.stats.unexpected === 0 && data.stats.flaky === 0 && data.stats.skipped === 0, 'four upstream page tests');
    report.upstreamPageTests = 4;
    report.upstreamTestDigest = 'sha256:' + createHash('sha256').update(readFileSync(join(config.owner, 'tests/e2e/auth.test.ts'))).digest('hex');
    pass('unchanged-upstream-four-auth-page-tests');
  } finally { clearTimeout(deadline); closeSync(stdout); closeSync(stderr); }
}

async function main() {
  save();
  try {
    await new Promise((resolve, reject) => { proxy.once('error', reject); proxy.listen(config.tlsPort, '127.0.0.1', resolve); });
    stage = 'upstream-production-page-tests';
    await upstreamPages();
    browser = await chromium.launch({ headless: true });
    report.browserVersion = browser.version();
    const suffix = randomBytes(10).toString('hex');
    const emailA = `a-${suffix}@qualification.invalid`;
    const emailB = `b-${suffix}@qualification.invalid`;
    const emailOrigin = `o-${suffix}@qualification.invalid`;
    const password = randomBytes(24).toString('base64url');
    const ctxA = await context();
    const pageA = await pageFor(ctxA, '/register');
    stage = 'invalid-registration-action';
    await submit(pageA, 'invalid-email', 'tiny', 'Sign up', 'invalid_data');
    check(await count('invalid-email') === 0, 'invalid registration has no database effect');
    await guest(ctxA);
    pass(stage);
    stage = 'successful-registration-action';
    const registerRequest = await submit(pageA, emailA, password, 'Sign up', 'success');
    const idA = await regular(ctxA, emailA);
    check(await count(emailA) === 1, 'registration persisted one real user');
    pass(stage);
    stage = 'production-secure-session-cookie';
    const cookies = await ctxA.cookies();
    check(cookies.some(cookie => cookie.name.startsWith('__Secure-authjs.session-token') && cookie.secure && cookie.httpOnly && cookie.sameSite === 'Lax'), 'production secure session cookie');
    pass(stage);

    const duplicate = await context();
    const duplicatePage = await pageFor(duplicate, '/register');
    stage = 'duplicate-registration-action-refusal';
    await submit(duplicatePage, emailA, password, 'Sign up', 'user_exists');
    check(await count(emailA) === 1, 'duplicate registration must not insert');
    await guest(duplicate);
    pass(stage);

    const login = await context();
    const loginPage = await pageFor(login, '/login');
    stage = 'invalid-login-action';
    await submit(loginPage, emailA, 'tiny', 'Sign in', 'invalid_data');
    await guest(login);
    pass(stage);
    stage = 'wrong-password-action-refusal';
    await submit(loginPage, emailA, password + 'wrong', 'Sign in', 'failed');
    await guest(login);
    pass(stage);
    stage = 'successful-login-action';
    await submit(loginPage, emailA, password, 'Sign in', 'success');
    check(await regular(login, emailA) === idA, 'login matches registered principal');
    pass(stage);

    const originContext = await context();
    await pageFor(originContext, '/register');
    const original = registerRequest.postDataBuffer();
    check(original && original.includes(Buffer.from(emailA)), 'captured real action request');
    const payload = Buffer.from(original.toString('utf8').split(emailA).join(emailOrigin));
    check(!payload.includes(Buffer.from(emailA)) && payload.includes(Buffer.from(emailOrigin)), 'fresh origin control principal');
    const originalHeaders = await registerRequest.allHeaders();
    const headers = { 'content-type': originalHeaders['content-type'], 'next-action': originalHeaders['next-action'], origin: 'https://foreign.invalid' };
    stage = 'off-origin-action-refusal-before-database-effect';
    check(await count(emailOrigin) === 0, 'new origin principal absent');
    const denied = await originContext.request.post('/register', { headers, data: payload, maxRedirects: 0 });
    check(denied.status() >= 400 && denied.status() < 600, 'cross-origin action must refuse');
    check(await count(emailOrigin) === 0, 'cross-origin refusal leaves database unchanged');
    await guest(originContext);
    pass(stage);
    stage = 'same-request-valid-origin-positive-control';
    const allowed = await originContext.request.post('/register', { headers: { ...headers, origin: config.origin }, data: payload, maxRedirects: 0 });
    check(allowed.status() === 200 && (await allowed.text()).includes('"success"'), 'same action payload must work at valid origin');
    check(await count(emailOrigin) === 1, 'valid-origin control persists user');
    await regular(originContext, emailOrigin);
    pass(stage);

    const ctxB = await context();
    const pageB = await pageFor(ctxB, '/register');
    stage = 'independent-second-user-registration';
    await submit(pageB, emailB, password, 'Sign up', 'success');
    check(await regular(ctxB, emailB) !== idA, 'distinct authenticated principal');
    pass(stage);
    const documentId = randomUUID();
    const content = 'private-' + randomBytes(12).toString('hex');
    const endpoint = '/api/document?id=' + documentId;
    stage = 'owner-private-document-create-and-read';
    const created = await ctxA.request.post(endpoint, { data: { title: 'Qualification private document', content, kind: 'text' } });
    check(created.status() === 200, 'owner document creation');
    const own = await ctxA.request.get(endpoint);
    check(own.status() === 200 && (await own.json())[0]?.content === content, 'owner private document read');
    pass(stage);
    stage = 'cross-user-private-document-read-refusal';
    const forbidden = await ctxB.request.get(endpoint);
    check(forbidden.status() === 403 && !(await forbidden.text()).includes(content), 'cross-user private content refused');
    pass(stage);
    stage = 'cross-user-private-document-write-refusal';
    const mutation = await ctxB.request.post(endpoint, { data: { title: 'Unauthorized', content: 'overwrite', kind: 'text', isManualEdit: true } });
    check(mutation.status() === 403, 'cross-user private write refused');
    const preserved = await ctxA.request.get(endpoint);
    check(preserved.status() === 200 && (await preserved.json())[0]?.content === content, 'refused write preserves owner content');
    pass(stage);
    stage = 'guest-private-document-read-refusal';
    const deniedGuest = await duplicate.request.get(endpoint);
    check(deniedGuest.status() === 403 && !(await deniedGuest.text()).includes(content), 'guest private content refused');
    pass(stage);
    stage = 'credential-and-cookie-evidence-barrier';
    const secretValues = [password, emailA, emailB, emailOrigin];
    for (const ctx of contexts) for (const cookie of await ctx.cookies()) {
      if (cookie.value.length > 16) secretValues.push(cookie.value);
    }
    let files = 0;
    function inspect(directory) {
      for (const entry of readdirSync(directory, { withFileTypes: true })) {
        const path = join(directory, entry.name);
        if (entry.isDirectory()) inspect(path);
        else if (entry.isFile()) {
          check(++files <= 1024 && statSync(path).size <= 67108864, 'bounded public evidence');
          const data = readFileSync(path);
          check(!secretValues.some(value => data.includes(Buffer.from(value))), 'test credential/cookie in public evidence');
        } else check(false, 'unexpected evidence entry type');
      }
    }
    inspect(dirname(config.receipt));
    pass(stage);
    report.status = 'passed';
  } catch (error) {
    report.status = 'failed'; report.failedStage = stage;
    report.errorClass = ['AssertionError', 'TimeoutError', 'Error', 'TypeError'].includes(error.name) ? error.name : 'Other';
    process.exitCode = 1;
  } finally {
    for (const ctx of contexts) await ctx.close().catch(() => {});
    if (browser) await browser.close();
    report.ownedBrowserStopped = true;
    await sql.end({ timeout: 3 });
    proxy.closeAllConnections();
    await new Promise(resolve => proxy.close(resolve));
    report.ownedHttpsProxyStopped = true;
    save();
  }
}
main().catch(() => { report.status = 'failed'; report.failedStage = stage; save(); process.exitCode = 1; });
