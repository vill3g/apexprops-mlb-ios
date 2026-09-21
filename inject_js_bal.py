with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

replacement = '''const balEl = document.getElementById("kalshiLiveBalance");
        const settingsBalEl = document.getElementById("kalshiSettingsPaperBalance");
        const tradeLogBalEl = document.getElementById("tradeLogPaperBalance");
        const topBarBalEl = document.getElementById("topBarAccountBalanceText");
        if (data.balance_dollars !== undefined) {
          const formatted = $$\;
          if (balEl) balEl.innerText = formatted;
          if (settingsBalEl) settingsBalEl.innerText = formatted;
          if (tradeLogBalEl) tradeLogBalEl.innerText = formatted;
          if (topBarBalEl) topBarBalEl.innerText = formatted;
        }'''

import re
text = re.sub(r'const balEl = document\.getElementById\("kalshiLiveBalance"\);\n        const settingsBalEl = document\.getElementById\("kalshiSettingsPaperBalance"\);\n        const tradeLogBalEl = document\.getElementById\("tradeLogPaperBalance"\);\n        if \(data\.balance_dollars !== undefined\) \{\n          const formatted = \$\$\{parseFloat\(data\.balance_dollars\)\.toFixed\(2\)\};\n          if \(balEl\) balEl\.innerText = formatted;\n          if \(settingsBalEl\) settingsBalEl\.innerText = formatted;\n          if \(tradeLogBalEl\) tradeLogBalEl\.innerText = formatted;\n        \}', replacement, text)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(text)
print("Injected JS update logic!")
