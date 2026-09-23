const { chromium } = require('playwright');
const jwt = require('jsonwebtoken');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on('console', msg => console.log('BROWSER LOG:', msg.text()));
  page.on('pageerror', err => console.log('BROWSER ERR:', err));

  // Generate token for user 2
  const token = jwt.sign({ sub: 'viille26', user_id: 2 }, 'kalshi_secure_1234', { expiresIn: '7d' });

  // Navigate to login just to set origin
  await page.goto('http://127.0.0.1:8056/login.html');
  await page.evaluate((t) => {
      localStorage.setItem('saas_token', t);
  }, token);

  // Navigate to saas dashboard
  await page.goto('http://127.0.0.1:8056/saas_dashboard.html');
  
  // Wait for 2 seconds to let it load
  await page.waitForTimeout(2000);
  
  // Check if tbody has trades
  const tbodyHTML = await page.evaluate(() => {
      const tb = document.getElementById('trades-body');
      return tb ? tb.innerHTML : 'TBODY NOT FOUND';
  });
  console.log("TBODY Length:", tbodyHTML.length);
  if (tbodyHTML.length < 200) {
      console.log("TBODY CONTENT:", tbodyHTML);
  }

  await browser.close();
})();
