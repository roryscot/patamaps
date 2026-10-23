// Browser controls for the actual immutable Miniserve image; no fixture application.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const [base, destination, document] = process.argv.slice(2);
(async () => {
  const expected = fs.readFileSync(document, 'utf8');
  const browser = await chromium.launch({headless: true});
  const context = await browser.newContext();
  const errors = [], offOrigin = [], requests = [], controls = [];
  await context.tracing.start({screenshots: true, snapshots: true, sources: false});
  await context.route('**/*', async route => {
    const url = route.request().url();
    if (new URL(url).origin !== new URL(base).origin) {
      offOrigin.push(url);
      await route.abort();
    } else {
      requests.push({method: route.request().method(), url});
      await route.continue();
    }
  });
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  page.setDefaultNavigationTimeout(15000);
  page.on('pageerror', error => errors.push(String(error)));
  try {
    assert.equal((await page.goto(base + '/qualified/', {waitUntil: 'networkidle'})).status(), 200);
    const link = page.getByRole('link', {name: 'status.txt', exact: true});
    await link.waitFor();
    assert.equal(new URL(await link.getAttribute('href'), page.url()).pathname, '/qualified/status.txt');
    controls.push('rendered-real-directory-listing');
    await page.screenshot({path: path.join(destination, 'listing.png'), fullPage: true});
    await Promise.all([page.waitForURL(base + '/qualified/status.txt'), link.click()]);
    assert.equal((await page.locator('body').innerText()).trimEnd(), expected.trimEnd());
    controls.push('actual-file-link-navigation-and-exact-text');
    await page.goBack({waitUntil: 'domcontentloaded'});
    assert.equal(new URL(page.url()).pathname, '/qualified/');
    await page.getByRole('link', {name: 'status.txt', exact: true}).waitFor();
    controls.push('browser-history-return-navigation');
    assert.equal((await page.goto(base + '/qualified/not-present.txt')).status(), 404);
    assert(!(await page.locator('body').innerText()).includes(expected.trim()));
    controls.push('missing-document-browser-refusal');
    assert.equal((await page.goto(base + '/status.txt')).status(), 404);
    controls.push('out-of-prefix-browser-refusal');
    assert.deepEqual(errors, []);
    assert.deepEqual(offOrigin, []);
    controls.push('no-script-errors-or-off-origin-requests');
    fs.writeFileSync(path.join(destination, 'receipt.json'), JSON.stringify({
      status: 'passed', engine: 'chromium', version: browser.version(), controls,
      actualFileLinkNavigation: true, actualBrowserHistoryNavigation: true,
      pageErrors: errors, offOriginRequests: offOrigin, requests
    }, null, 2) + '\n');
  } catch (error) {
    fs.writeFileSync(path.join(destination, 'failure.json'), JSON.stringify({
      error: String(error), url: page.url(), body: await page.locator('body').innerText(),
      pageErrors: errors, offOriginRequests: offOrigin, requests, controls
    }, null, 2) + '\n');
    await page.screenshot({path: path.join(destination, 'failure.png'), fullPage: true});
    throw error;
  } finally {
    await context.tracing.stop({path: path.join(destination, 'trace.zip')});
    await context.close();
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
