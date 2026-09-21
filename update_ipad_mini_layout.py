import sys

html_path = 'static/index.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update iPad detection to also recognize iPad Mini 7 in queries or resolution
old_detect = '''      const isIpadMini7 = isIpad && window.devicePixelRatio === 2 && navigator.maxTouchPoints > 0 && ((w === 744 && h === 1133) || (w === 1133 && h === 744));'''
new_detect = '''      const isManualIpadMini7 = queryParam.includes("ipadmini") || queryParam.includes("ipad-mini-7") || queryParam.includes("mini7");
      const isIpadMini7 = isManualIpadMini7 || (isIpad && (
        (window.devicePixelRatio === 2 && ((w === 744 && h === 1133) || (w === 1133 && h === 744))) ||
        ((w >= 740 && w <= 760 && h >= 1120 && h <= 1140) || (w >= 1120 && w <= 1140 && h >= 740 && h <= 760))
      ));'''

if old_detect in content:
    content = content.replace(old_detect, new_detect)
    print("1. Updated detectAndAdaptDevice for iPad Mini 7")
else:
    print("Warning: old_detect not found!")

# 2. Update renderPreviousDaysAccuracy to safely guard when element is removed or hidden
old_fn = '''    function renderPreviousDaysAccuracy(daily) {
      const valueEl = document.getElementById("btcPreviousDaysAccuracyValue");
      const panelEl = document.getElementById("btcPreviousDaysAccuracy");
      const titleEl = panelEl ? panelEl.querySelector("span:first-child") : null;
      if (!valueEl) return;

      const isIpadMini7 = document.body.classList.contains("is-ipad-mini-7");
      
      if (isIpadMini7 && titleEl) {
        titleEl.innerText = "Previous Day";
      } else if (titleEl) {
        titleEl.innerText = "Previous days";
      }

      const today = accuracyDateKey(Math.floor(Date.now() / 1000));
      const previousDays = Object.entries(daily)
        .filter(([date, stats]) => date < today && stats && stats.total > 0)
        .sort(([a], [b]) => b.localeCompare(a))
        .slice(0, isIpadMini7 ? 1 : 3);'''

new_fn = '''    function renderPreviousDaysAccuracy(daily) {
      const valueEl = document.getElementById("btcPreviousDaysAccuracyValue");
      const panelEl = document.getElementById("btcPreviousDaysAccuracy");
      const titleEl = panelEl ? panelEl.querySelector("span:first-child") : null;
      if (!valueEl || !panelEl) return;

      const isIpadMini7 = document.body.classList.contains("is-ipad-mini-7");
      if (isIpadMini7) {
        panelEl.style.display = 'none';
        return;
      }
      
      if (titleEl) {
        titleEl.innerText = "Previous days";
      }

      const today = accuracyDateKey(Math.floor(Date.now() / 1000));
      const previousDays = Object.entries(daily)
        .filter(([date, stats]) => date < today && stats && stats.total > 0)
        .sort(([a], [b]) => b.localeCompare(a))
        .slice(0, 3);'''

if old_fn in content:
    content = content.replace(old_fn, new_fn)
    print("2. Updated renderPreviousDaysAccuracy safely")
else:
    print("Warning: old_fn not found!")

# 3. Completely hide #btcPreviousDaysAccuracy on iPad Mini 7 and allow remaining cards to expand & fit available space
# Also remove any empty space so chart and AI console start immediately below navigation bar!
old_ipad_css = '''    /* iPad Mini 7 Custom Adjustments */
    body.is-ipad-mini-7 #btcPreviousDaysAccuracy {
      min-width: 60px !important;
      padding-left: 0.25rem !important;
      padding-right: 0.25rem !important;
      margin-right: -0.15rem !important;
    }
    body.is-ipad-mini-7 #btcPreviousDaysAccuracy span:first-child {
      font-size: 6.5px !important;
    }
    body.is-ipad-mini-7 #btcPreviousDaysAccuracyValue {
      font-size: 9px !important;
    }
    body.is-ipad-mini-7 .sleek-glass-header {
      gap: 0.35rem !important;
    }'''

new_ipad_css = '''    /* iPad Mini 7 Dedicated Layout & Spacing Engine */
    body.is-ipad-mini-7 #btcPreviousDaysAccuracy,
    @media screen and (min-width: 740px) and (max-width: 760px) and (min-height: 1120px) and (max-height: 1150px) {
      #btcPreviousDaysAccuracy {
        display: none !important;
      }
    }
    body.is-ipad-mini-7 #btcPreviousDaysAccuracy {
      display: none !important;
    }

    /* Expand remaining top-bar cards to comfortably fill the freed space */
    body.is-ipad-mini-7 .sleek-glass-header {
      gap: 0.45rem !important;
      margin: 2px auto 2px auto !important;
      min-height: 52px !important;
      padding: 0.35rem 0.6rem !important;
    }
    body.is-ipad-mini-7 .sleek-glass-header .flex-1.flex.items-center.justify-center {
      justify-content: space-between !important;
      gap: 0.4rem !important;
      width: 100% !important;
    }
    body.is-ipad-mini-7 .sleek-glass-header .sleek-glass-card {
      flex: 1 1 auto !important;
      min-width: 115px !important;
      padding: 0.35rem 0.5rem !important;
    }

    /* Zero out all empty margins/paddings between navigation bar and chart / AI console */
    body.is-ipad-mini-7 .app-main-wrapper {
      padding-top: max(0.25rem, calc(env(safe-area-inset-top, 0px) + 0.15rem)) !important;
      padding-bottom: max(0.25rem, env(safe-area-inset-bottom, 0px)) !important;
      padding-left: 0.4rem !important;
      padding-right: 0.4rem !important;
      gap: 0.15rem !important;
    }
    body.is-ipad-mini-7 .app-main-wrapper > * + * {
      margin-top: 0.15rem !important;
    }
    body.is-ipad-mini-7 #view_btc_analyzer {
      margin-top: 0 !important;
      padding-top: 0 !important;
      gap: 0.2rem !important;
      height: calc(100% - 54px) !important;
      max-height: calc(100% - 54px) !important;
    }
    body.is-ipad-mini-7 #iphone17Hero {
      display: none !important;
    }
    body.is-ipad-mini-7 .btc-main-grid {
      margin-top: 0 !important;
      padding-top: 0 !important;
      gap: 0.3rem !important;
    }
    body.is-ipad-mini-7 .btc-chart-card {
      margin-top: 0 !important;
    }
    body.is-ipad-mini-7 .btc-right-panel {
      margin-top: 0 !important;
    }'''

if old_ipad_css in content:
    content = content.replace(old_ipad_css, new_ipad_css)
    print("3. Replaced iPad Mini 7 CSS rules with full layout adjustments")
else:
    print("Warning: old_ipad_css not found!")

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Saved updated static/index.html")
