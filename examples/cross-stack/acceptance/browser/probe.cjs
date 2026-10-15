const {chromium} = require('playwright');
(async () => {
  let browser;
  try {
    browser = await chromium.launch({headless: true, ...(process.argv[2] ? {executablePath: process.argv[2]} : {})});
    console.log(JSON.stringify({status: 'available', engine: 'chromium', version: browser.version()}));
  } catch (error) {
    console.log(JSON.stringify({status: 'unavailable', code: 'REQUIRED_BROWSER_RUNTIME_UNAVAILABLE', reason: String(error)}));
    process.exitCode = 69;
  } finally {
    if (browser) await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
