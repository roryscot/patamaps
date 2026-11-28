/** Real production browser/actions. Raw credentials, HTTP and child logs stay private. */
import assert from 'node:assert/strict';
import { isDeepStrictEqual } from 'node:util';
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
  actionResponseCollector: 'request-body-digest-bound HTTPS proxy; identity encoding; no body rewrite',
  actionResponseMaximumBytes: 1048576,
};
let stage = 'https-proxy';
const save = () => writeFileSync(config.receipt, JSON.stringify(report, null, 2) + '\n');
const pass = name => { report.controls.push({ name, passed: true }); save(); };
const check = (value, label) => {
  if (!value) { report.failedCheck = label; save(); }
  assert.ok(value, label);
};
const contexts = [];
const dynamicEvidenceValues = [];
let generationPostAttempts = 0;
const actionResponses = new Map();
let browser;
const sql = postgres(process.env.POSTGRES_URL, { max: 2, connect_timeout: 5 });
const proxy = createHttpsServer({
  key: readFileSync(join(config.private, 'key.pem')),
  cert: readFileSync(join(config.private, 'cert.pem')),
}, (req, res) => {
  const origin = new URL(config.origin);
  const action = req.method === 'POST' && req.headers['next-action'];
  const requestHash = action ? createHash('sha256') : null;
  let requestDigest;
  const forward = httpRequest({ host: '127.0.0.1', port: config.nextPort, path: req.url,
    method: req.method, headers: { ...req.headers, host: origin.host,
      ...(action ? { 'accept-encoding': 'identity' } : {}),
      'x-forwarded-host': origin.host, 'x-forwarded-proto': 'https' } }, upstream => {
    if (action) {
      let length = 0;
      const chunks = [];
      upstream.on('data', chunk => {
        length += chunk.length;
        if (length > 1048576) { upstream.destroy(); res.destroy(); return; }
        chunks.push(chunk);
      });
      upstream.on('end', () => {
        if (!requestDigest || length > 1048576 || actionResponses.size >= 32 ||
            (upstream.headers['content-encoding'] && upstream.headers['content-encoding'] !== 'identity')) return;
        const body = Buffer.concat(chunks).toString('utf8');
        actionResponses.set(action + ':' + requestDigest, {
          httpStatus: upstream.statusCode,
          responseIsRsc: (upstream.headers['content-type'] ?? '').includes('text/x-component'),
          observedStates: ['idle', 'in_progress', 'success', 'failed', 'invalid_data', 'user_exists'].filter(value => body.includes('"' + value + '"')),
        });
      });
    }
    upstream.on('error', () => res.destroy());
    res.writeHead(upstream.statusCode, upstream.headers); upstream.pipe(res);
  });
  forward.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end(); });
  req.on('error', () => forward.destroy());
  let bytes = 0;
  req.on('data', data => {
    bytes += data.length;
    if (requestHash) requestHash.update(data);
    if (bytes > 1048576) { forward.destroy(); req.destroy(); }
  });
  req.on('end', () => { if (requestHash) requestDigest = requestHash.digest('hex'); });
  req.pipe(forward);
});
proxy.requestTimeout = 30000;
proxy.headersTimeout = 15000;

async function context() {
  const value = await browser.newContext({ baseURL: config.origin, ignoreHTTPSErrors: true });
  await value.route('**/*', route => {
    const request = route.request();
    const url = new URL(request.url());
    if (config.dynamicRoutes && request.method() === 'POST' && url.pathname === '/api/chat') {
      generationPostAttempts++;
      return route.abort();
    }
    return url.origin === config.origin ? route.continue() : route.abort();
  });
  contexts.push(value);
  return value;
}
async function pageFor(ctx, path) {
  const page = await ctx.newPage();
  page.setDefaultTimeout(20000);
  const initialSession = page.waitForResponse(response => response.request().method() === 'GET' && new URL(response.url()).pathname === '/api/auth/session');
  const [, ready] = await Promise.all([page.goto(path, { waitUntil: 'domcontentloaded' }), initialSession]);
  check(ready.status() === 200 && await ready.finished() === null, 'initial browser session readiness');
  report.initialSessionReadyPages = (report.initialSessionReadyPages ?? 0) + 1;
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
  const request = response.request();
  const requestBody = request.postDataBuffer();
  check(requestBody !== null, 'real action request payload');
  const key = request.headers()['next-action'] + ':' + createHash('sha256').update(requestBody).digest('hex');
  const deadline = Date.now() + 20000;
  while (!actionResponses.has(key) && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 20));
  const observed = actionResponses.get(key);
  check(observed, 'request-bound proxy action response');
  actionResponses.delete(key);
  report.lastAction = { ...observed, expectedState: state };
  save();
  check(response.status() === observed.httpStatus && observed.httpStatus === 200 && observed.responseIsRsc, 'real action response');
  check(observed.observedStates.includes(state), 'expected action state');
  return request;
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
  report.lastSessionObservation = {
    principalType: ['guest', 'regular'].includes(value.user?.type) ? value.user.type : 'absent-or-unknown',
    expectedEmailMatches: value.user?.email === email,
    principalIdPresent: typeof value.user?.id === 'string',
  };
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


async function rewriteControls() {
  const ctx = await context();
  const page = await pageFor(ctx, '/login');
  const direct = await session(ctx);
  check(direct.user?.type === 'guest' && typeof direct.user.id === 'string', 'rewrite probes require an actual guest session');
  await page.setExtraHTTPHeaders({ 'x-patamaps-rewrite': 'enabled' });
  for (const [suffix, heading, name] of [
    ['login', 'Welcome back', 'rewrite-login-url-preserved'],
    ['register', 'Create account', 'rewrite-register-url-preserved'],
  ]) {
    stage = name;
    const path = '/qualified/auth/' + suffix;
    const response = await page.goto(path, { waitUntil: 'domcontentloaded' });
    check(response?.status() === 200 && response.request().redirectedFrom() === null, 'rewrite must serve without redirect');
    check(new URL(page.url()).origin === config.origin && new URL(page.url()).pathname === path, 'rewrite browser URL stays at original alias');
    await page.getByRole('heading', { name: heading, exact: true }).waitFor({ state: 'visible' });
    pass(stage);
  }
  for (const [path, headers, name] of [
    ['/qualified/auth/login', {}, 'rewrite-missing-header-refused'],
    ['/qualified/auth/login', { 'x-patamaps-rewrite': 'wrong' }, 'rewrite-wrong-header-refused'],
    ['/qualified/auth/login?blocked=1', { 'x-patamaps-rewrite': 'enabled' }, 'rewrite-blocked-query-refused'],
    ['/wrong/qualified/auth/login', { 'x-patamaps-rewrite': 'enabled' }, 'rewrite-prefix-refused'],
    ['/qualified/auth/login/extra', { 'x-patamaps-rewrite': 'enabled' }, 'rewrite-extra-segment-refused'],
    ['/qualified/auth/admin', { 'x-patamaps-rewrite': 'enabled' }, 'rewrite-page-parameter-refused'],
  ]) {
    stage = name;
    const response = await ctx.request.get(path, { headers, maxRedirects: 0 });
    check(response.status() === 404, 'unmatched rewrite must return HTTP404 without redirect following');
    pass(stage);
  }
  stage = 'rewrite-session-query-positive';
  const directQuery = await ctx.request.get('/api/auth/session?view=session', { maxRedirects: 0 });
  check(directQuery.status() === 200, 'matched direct session query positive control');
  const response = await ctx.request.get('/qualified/session?view=session', { maxRedirects: 0 });
  report.lastRewriteObservation = {
    directQueryStatus: directQuery.status(), aliasStatus: response.status(),
    aliasBodyType: (response.headers()['content-type'] ?? '').includes('json') ? 'json' : 'other',
    aliasRedirect: Boolean(response.headers().location),
  };
  save();
  check(response.status() === 200, 'query-conditioned session rewrite response');
  const aliased = await response.json();
  check(isDeepStrictEqual(aliased.user, direct.user), 'session rewrite returns the same actual guest identity');
  pass(stage);
  for (const [path, headers, name] of [
    ['/qualified/session', {}, 'rewrite-session-query-missing-refused'],
    ['/qualified/session?view=wrong', {}, 'rewrite-session-query-wrong-refused'],
    ['/qualified/session?view=session', { 'x-patamaps-block': '1' }, 'rewrite-session-block-header-refused'],
  ]) {
    stage = name;
    const response = await ctx.request.get(path, { headers, maxRedirects: 0 });
    check(response.status() === 404, 'session rewrite condition must refuse HTTP404 without redirect following');
    pass(stage);
  }
  await page.close();
}


async function dynamicControls(ctxA, ctxB, ownerId) {
  const privateId = randomUUID();
  const publicId = randomUUID();
  const unseenId = randomUUID();
  const privateMessageId = randomUUID();
  const publicMessageId = randomUUID();
  const privateText = 'qualified-private-chat-' + randomBytes(12).toString('hex');
  const publicText = 'qualified-public-chat-' + randomBytes(12).toString('hex');
  dynamicEvidenceValues.push(privateId, publicId, unseenId, privateMessageId, publicMessageId, privateText, publicText);
  await sql`insert into "Chat" ("id","createdAt","title","userId","visibility") values (${privateId},current_timestamp,'Qualification private chat',${ownerId},'private')`;
  await sql`insert into "Chat" ("id","createdAt","title","userId","visibility") values (${publicId},current_timestamp,'Qualification public chat',${ownerId},'public')`;
  for (const [id, chatId, text] of [[privateMessageId, privateId, privateText], [publicMessageId, publicId, publicText]]) {
    await sql`insert into "Message_v2" ("id","chatId","role","parts","attachments","createdAt") values (${id},${chatId},'assistant',${sql.json([{ type:'text', text }])},${sql.json([])},current_timestamp)`;
  }
  async function snapshot() {
    const chats = await sql`select "id","createdAt","title","userId","visibility" from "Chat" where "id"=${privateId} or "id"=${publicId} order by "id"`;
    const messages = await sql`select "id","chatId","createdAt","role","parts","attachments" from "Message_v2" where "chatId"=${privateId} or "chatId"=${publicId} order by "id"`;
    check(chats.length === 2 && messages.length === 2, 'two owned dynamic fixtures');
    return JSON.parse(JSON.stringify({ chats, messages }));
  }
  const before = await snapshot();
  report.dynamicRouteWitness = {
    profile:'patamaps-pinned-dynamic-runtime-1', pagePattern:'/chat/[id]',
    dataEndpoint:'/api/messages', fixturesUnchanged:false, generationPostAttempts:0,
    rawFixtureValuesPublished:false, pageAuthorization:'client shell; data API enforces private visibility',
    streamBehavior:'constant204 stub; no resumable generation claim',
  };
  const witness = report.dynamicRouteWitness;
  async function openChat(ctx, id, status, page = null) {
    page ??= await ctx.newPage();
    page.setDefaultTimeout(20000);
    const pending = page.waitForResponse(response => {
      const url = new URL(response.url());
      return response.request().method() === 'GET' && url.origin === config.origin &&
        url.pathname === '/api/messages' && url.searchParams.get('chatId') === id;
    });
    const [navigation, data] = await Promise.all([page.goto('/chat/' + id, { waitUntil:'domcontentloaded' }), pending]);
    check(navigation?.status() === 200 && navigation.request().redirectedFrom() === null, 'dynamic page serves original URL');
    check(new URL(page.url()).origin === config.origin && new URL(page.url()).pathname === '/chat/' + id, 'exact dynamic browser path');
    check(data.status() === status && await data.finished() === null, 'id-bound dynamic data status');
    const raw = await data.text();
    check(Buffer.byteLength(raw) <= 65536, 'bounded dynamic JSON response');
    return { page, body:JSON.parse(raw) };
  }
  async function visible(page, text) {
    await page.getByTestId('message-content').filter({ hasText:text }).waitFor({ state:'visible' });
  }
  function exactData(body, text, readonly, visibility) {
    check(body.isReadonly === readonly && body.visibility === visibility && body.userId === ownerId, 'actual dynamic owner and visibility');
    check(Array.isArray(body.messages) && body.messages.length === 1 && body.messages[0].role === 'assistant', 'exact seeded message');
    check(body.messages[0].parts.length === 1 && body.messages[0].parts[0].type === 'text' && body.messages[0].parts[0].text === text, 'exact seeded parts');
  }

  stage = 'dynamic-owner-private-page-and-id-bound-data';
  const ownPrivate = await openChat(ctxA, privateId, 200);
  exactData(ownPrivate.body, privateText, false, 'private');
  await visible(ownPrivate.page, privateText);
  await ownPrivate.page.getByTestId('multimodal-input').waitFor({ state:'visible' });
  witness.ownerPathAndQueryIdMatched = true; witness.ownerPrivateMessageRendered = true;
  pass(stage);

  stage = 'dynamic-owner-second-id-replaces-visible-data';
  const ownPublic = await openChat(ctxA, publicId, 200, ownPrivate.page);
  exactData(ownPublic.body, publicText, false, 'public');
  await visible(ownPublic.page, publicText);
  check(await ownPublic.page.getByTestId('message-content').filter({ hasText:privateText }).count() === 0, 'second dynamic ID cannot show first message');
  witness.distinctSecondIdRendered = true;
  pass(stage);

  stage = 'dynamic-cross-user-public-page-readonly';
  const shared = await openChat(ctxB, publicId, 200);
  exactData(shared.body, publicText, true, 'public');
  await visible(shared.page, publicText);
  check(await shared.page.getByTestId('multimodal-input').count() === 0, 'public nonowner has no composer');
  witness.crossUserPublicReadonly = true;
  pass(stage);

  stage = 'dynamic-cross-user-private-data-refusal';
  const forbidden = await openChat(ctxB, privateId, 403);
  check(isDeepStrictEqual(forbidden.body, { error:'forbidden' }), 'cross-user private API returns only refusal');
  check(await forbidden.page.getByTestId('message-content').filter({ hasText:privateText }).count() === 0, 'cross-user private message stays absent');
  witness.crossUserPrivateStatus = 403;
  pass(stage);

  const guestContext = await context();
  const guestLogin = await pageFor(guestContext, '/login');
  const guestValue = await session(guestContext);
  check(guestValue.user?.type === 'guest' && typeof guestValue.user.id === 'string', 'actual dynamic guest session');
  await guestLogin.close();
  stage = 'dynamic-guest-public-page-readonly';
  const guestPublic = await openChat(guestContext, publicId, 200);
  exactData(guestPublic.body, publicText, true, 'public');
  await visible(guestPublic.page, publicText);
  check(await guestPublic.page.getByTestId('multimodal-input').count() === 0, 'guest public reader has no composer');
  witness.guestPublicReadonly = true;
  pass(stage);

  stage = 'dynamic-guest-private-data-refusal';
  const guestPrivate = await openChat(guestContext, privateId, 403);
  check(isDeepStrictEqual(guestPrivate.body, { error:'forbidden' }), 'guest private API returns only refusal');
  check(await guestPrivate.page.getByTestId('message-content').filter({ hasText:privateText }).count() === 0, 'guest private message stays absent');
  witness.guestPrivateStatus = 403;
  pass(stage);

  stage = 'dynamic-unseen-id-empty-response';
  const unseen = await ctxA.request.get('/api/messages?chatId=' + unseenId, { maxRedirects:0 });
  check(unseen.status() === 200 && isDeepStrictEqual(await unseen.json(), { isReadonly:false,messages:[],userId:null,visibility:'private' }), 'owner-defined empty unseen chat');
  const persisted = await sql`select count(*)::int as count from "Chat" where id=${unseenId}`;
  check(persisted[0].count === 0, 'unseen GET cannot persist a chat');
  witness.unseenIdEmptyAndNotPersisted = true;
  pass(stage);

  stage = 'dynamic-missing-chat-id-query-refusal';
  const missing = await ctxA.request.get('/api/messages', { maxRedirects:0 });
  check(missing.status() === 400 && isDeepStrictEqual(await missing.json(), { error:'chatId required' }), 'missing required query refuses');
  witness.missingQueryStatus = 400;
  pass(stage);

  stage = 'dynamic-extra-page-segment-refusal';
  const extra = await ctxA.request.get('/chat/' + privateId + '/extra', { maxRedirects:0 });
  check(extra.status() === 404, 'dynamic page extra segment refuses');
  witness.extraPageSegmentStatus = 404;
  pass(stage);

  stage = 'dynamic-stream-route-204';
  const stream = await ctxA.request.get('/api/chat/' + privateId + '/stream', { maxRedirects:0 });
  check(stream.status() === 204 && (await stream.body()).length === 0, 'original dynamic stream stub');
  witness.streamGetStatus = 204;
  pass(stage);

  stage = 'dynamic-stream-post-method-refusal';
  const post = await ctxA.request.post('/api/chat/' + privateId + '/stream', { data:{},maxRedirects:0 });
  check(post.status() === 405, 'unimplemented stream POST refuses');
  witness.streamPostStatus = 405;
  pass(stage);

  stage = 'dynamic-stream-extra-segment-refusal';
  const extraStream = await ctxA.request.get('/api/chat/' + privateId + '/stream/extra', { maxRedirects:0 });
  check(extraStream.status() === 404, 'dynamic stream extra segment refuses');
  witness.extraStreamSegmentStatus = 404;
  pass(stage);

  stage = 'dynamic-fixtures-unchanged-and-no-generation';
  check(isDeepStrictEqual(await snapshot(), before), 'all seeded chat and message rows preserved');
  check(generationPostAttempts === 0, 'no generation POST attempted');
  witness.fixturesUnchanged = true;
  witness.fixtureDigest = 'sha256:' + createHash('sha256').update(JSON.stringify(before)).digest('hex');
  witness.generationPostAttempts = generationPostAttempts;
  pass(stage);
}

async function main() {
  save();
  try {
    await new Promise((resolve, reject) => { proxy.once('error', reject); proxy.listen(config.tlsPort, '127.0.0.1', resolve); });
    stage = 'upstream-production-page-tests';
    await upstreamPages();
    browser = await chromium.launch({ headless: true });
    report.browserVersion = browser.version();
    if (config.rewriteControls) await rewriteControls();
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
    const beforeSessionCookies = (await originContext.cookies()).filter(cookie => cookie.name.startsWith('__Secure-authjs.session-token')).map(cookie => cookie.value).join('|');
    const allowed = await originContext.request.post('/register', { headers: { ...headers, origin: config.origin }, data: payload, maxRedirects: 0 });
    const afterSessionCookies = (await originContext.cookies()).filter(cookie => cookie.name.startsWith('__Secure-authjs.session-token')).map(cookie => cookie.value).join('|');
    report.originPositiveCookieObservation = {
      serverIssuedSessionCookie: (await allowed.headersArray()).some(header => header.name.toLowerCase() === 'set-cookie' && /^__Secure-authjs\.session-token(?:\.\d+)?=/.test(header.value)),
      sessionCookieChanged: beforeSessionCookies !== afterSessionCookies,
    };
    save();
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
    const expectedOwnerDocuments = await own.json();
    check(own.status() === 200 && expectedOwnerDocuments.length === 1 && expectedOwnerDocuments[0]?.content === content && expectedOwnerDocuments[0]?.userId === idA, 'owner private document read');
    pass(stage);
    stage = 'cross-user-private-document-read-refusal';
    const forbidden = await ctxB.request.get(endpoint);
    check(forbidden.status() === 403 && !(await forbidden.text()).includes(content), 'cross-user private content refused');
    pass(stage);
    stage = 'cross-user-private-document-write-refusal';
    const mutation = await ctxB.request.post(endpoint, { data: { title: 'Unauthorized', content: 'overwrite', kind: 'text', isManualEdit: true } });
    check(mutation.status() === 403, 'cross-user private write refused');
    const preserved = await ctxA.request.get(endpoint);
    check(preserved.status() === 200 && isDeepStrictEqual(await preserved.json(), expectedOwnerDocuments), 'refused write preserves every owner document version');
    pass(stage);
    stage = 'guest-private-document-read-refusal';
    const deniedGuest = await duplicate.request.get(endpoint);
    check(deniedGuest.status() === 403 && !(await deniedGuest.text()).includes(content), 'guest private content refused');
    pass(stage);
    if (config.dynamicRoutes) await dynamicControls(ctxA, ctxB, idA);
    stage = 'credential-and-cookie-evidence-barrier';
    const secretValues = [password, emailA, emailB, emailOrigin, ...dynamicEvidenceValues];
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
