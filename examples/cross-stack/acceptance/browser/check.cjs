const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const [base, destination] = process.argv.slice(2);
(async () => {
  const browser = await chromium.launch({headless: true});
  const context = await browser.newContext({recordHar: {path: path.join(destination, 'browser.har')}});
  await context.tracing.start({screenshots: true, snapshots: true, sources: true});
  const errors = [];
  const consoleMessages = [];
  const requests = [];
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(String(error)));
  page.on('console', event => consoleMessages.push({type: event.type(), text: event.text()}));
  page.on('request', request => {
    if (request.url().startsWith(base)) requests.push({method: request.method(), url: request.url(), body: request.postData()});
  });
  // Enlarge the real pre-hydration window. Interactions must wait on the
  // application's disabled controls, not on an arbitrary test readiness sleep.
  await page.route('**/_next/static/chunks/app/page-*.js', async route => {
    await new Promise(resolve => setTimeout(resolve, 250));
    await route.continue();
  });
  try {
    assert.equal((await page.goto(base, {waitUntil: 'domcontentloaded'})).status(), 200);
    await page.getByLabel('Item name', {exact: true}).fill('Widget');
    const createdResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/items' && response.request().method() === 'POST');
    await page.getByRole('button', {name: 'Create item', exact: true}).click();
    const created = await createdResponse;
    assert.equal(created.status(), 201);
    assert.deepEqual(await created.json(), {id: 'item:widget', name: 'Widget'});
    await page.getByRole('status').filter({hasText: 'item:widget'}).waitFor();
    assert.deepEqual(JSON.parse(await page.getByRole('status').textContent()), {id: 'item:widget', name: 'Widget'});
    await page.screenshot({path: path.join(destination, 'created-item.png'), fullPage: true});
    await page.getByLabel('Item name', {exact: true}).fill('fail');
    const failedResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/items' && response.request().method() === 'POST');
    await page.getByRole('button', {name: 'Create item', exact: true}).click();
    assert.equal((await failedResponse).status(), 500);
    await page.getByRole('status').filter({hasText: 'backend-failure'}).waitFor();
    assert.deepEqual(JSON.parse(await page.getByRole('status').textContent()), {error: 'backend-failure'});
    assert.equal((await page.goto(base + '/items/item:widget')).status(), 200);
    assert.match(await page.locator('body').innerText(), /item:widget/);
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(destination, 'browser-receipt.json'), JSON.stringify({
      status: 'passed', engine: 'chromium', version: browser.version(),
      actualFormInteraction: true, hydratedClientNextLinuxRoundTrip: true,
      preHydrationScriptDeliveryDelayMs: 250, observedCreateStatus: 201,
      deliberateBackendFailure: true, dynamicPageNavigation: true, pageErrors: errors
    }, null, 2) + '\n');
  } catch (error) {
    fs.writeFileSync(path.join(destination, 'browser-failure.json'), JSON.stringify({
      error: String(error), url: page.url(), body: await page.locator('body').innerText(),
      pageErrors: errors, consoleMessages, requests
    }, null, 2) + '\n');
    await page.screenshot({path: path.join(destination, 'browser-failure.png'), fullPage: true});
    throw error;
  } finally {
    await context.tracing.stop({path: path.join(destination, 'browser-trace.zip')});
    await context.close();
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
