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
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(String(error)));
  try {
    assert.equal((await page.goto(base)).status(), 200);
    await page.getByLabel('Item name', {exact: true}).fill('Widget');
    await page.getByRole('button', {name: 'Create item', exact: true}).click();
    await page.getByRole('status').filter({hasText: 'item:widget'}).waitFor();
    assert.deepEqual(JSON.parse(await page.getByRole('status').textContent()), {id: 'item:widget', name: 'Widget'});
    await page.screenshot({path: path.join(destination, 'created-item.png'), fullPage: true});
    await page.getByLabel('Item name', {exact: true}).fill('fail');
    await page.getByRole('button', {name: 'Create item', exact: true}).click();
    await page.getByRole('status').filter({hasText: 'backend-failure'}).waitFor();
    assert.deepEqual(JSON.parse(await page.getByRole('status').textContent()), {error: 'backend-failure'});
    assert.equal((await page.goto(base + '/items/item:widget')).status(), 200);
    assert.match(await page.locator('body').innerText(), /item:widget/);
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(destination, 'browser-receipt.json'), JSON.stringify({
      status: 'passed', engine: 'chromium', version: browser.version(),
      actualFormInteraction: true, hydratedClientNextLinuxRoundTrip: true,
      deliberateBackendFailure: true, dynamicPageNavigation: true, pageErrors: errors
    }, null, 2) + '\n');
  } finally {
    await context.tracing.stop({path: path.join(destination, 'browser-trace.zip')});
    await context.close();
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
