with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''          const topBarBalEl = document.getElementById("topBarAccountBalanceText");
          if (topBarBalEl) topBarBalEl.innerText = formatted;
        }'''

sync_loop = target + '''

        // Dynamic Settings Sync from Backend
        if (data.ai_settings) {
          for (const [key, val] of Object.entries(data.ai_settings)) {
            const elId = "setting" + key.charAt(0).toUpperCase() + key.slice(1);
            const el = document.getElementById(elId);
            if (el && document.activeElement !== el) {
              if (el.type === 'checkbox') {
                if (key === 'oneShotAiStartTrade') {
                  const isOneShot = !!val;
                  if (el.checked !== isOneShot) {
                    el.checked = isOneShot;
                    if (!isOneShot && window._wasOneShotActive) {
                      showAppToast("1-Shot Trade Complete", "100% AI Prediction trade executed. Settings returned to normal.", "info");
                    }
                    window._wasOneShotActive = isOneShot;
                  }
                } else {
                  if (el.checked !== !!val) el.checked = !!val;
                }
              } else {
                if (el.value != val) {
                  el.value = val;
                  if (key === 'minConf') {
                    const span = document.getElementById('minConfVal');
                    if (span) span.innerText = val + '%';
                  } else if (key === 'trainWindow') {
                    const span = document.getElementById('trainWinVal');
                    if (span) span.innerText = val;
                  }
                }
              }
            }
          }
        }'''

text = text.replace(target, sync_loop, 1)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(text)
print("Injected dynamic settings sync loop!")
