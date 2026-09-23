const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on('console', msg => console.log('BROWSER_LOG:', msg.text()));
  page.on('pageerror', err => console.log('BROWSER_ERR:', err));
  
  // We need to login first or inject the token!
  // saas_token is stored in localStorage.
  
  // Actually, we don't have the token easily available.
  // But we can check if it fails before even authenticating.
  
  await browser.close();
})();
