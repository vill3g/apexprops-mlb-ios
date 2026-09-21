import sys

with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

orig_len = len(text)
applied = []

# ── PATCH 1: Trading Style dropdown before Model Choice ──────────────────────
OLD1 = (
    '          <div class="flex items-center justify-between px-1.5 py-1 rounded-lg bg-slate-900 border border-slate-800">\n'
    '                      <span class="text-slate-300 cursor-help" title="Select which ML model to use for predictions (Logistic Regression, Random Forest, XGBoost)">Model Choice</span>'
)
NEW1 = (
    '          <div class="flex items-center justify-between px-1.5 py-1 rounded-lg bg-slate-900 border border-slate-800">\n'
    '                      <span class="text-slate-300 cursor-help" title="Select trading style">Trading Style</span>\n'
    '                      <select id="settingTradingStyle" class="bg-slate-950 border border-slate-700 rounded px-1 text-cyan-300 focus:outline-none cursor-pointer">\n'
    '                        <option value="AUTO" selected>\U0001f916 AUTO (Adaptive)</option>\n'
    '                        <option value="SNIPER">\U0001f3af Sniper (15m)</option>\n'
    '                        <option value="MACHINE_GUN">\U0001f52b Machine Gun (1m)</option>\n'
    '                        <option value="CHOP">\u2696\ufe0f Chop Engine (Low Vol)</option>\n'
    '                      </select>\n'
    '                    </div>\n'
    '                    <div class="flex items-center justify-between px-1.5 py-1 rounded-lg bg-slate-900 border border-slate-800">\n'
    '                      <span class="text-slate-300 cursor-help" title="Select which ML model to use for predictions (Logistic Regression, Random Forest, XGBoost)">Model Choice</span>'
)
if OLD1 in text:
    text = text.replace(OLD1, NEW1, 1)
    applied.append('PATCH 1: Trading Style dropdown')
else:
    print('WARN: PATCH 1 target not found', file=sys.stderr)

# ── PATCH 2: Spinning Bitcoin + Account Balance widget in nav bar ─────────────
OLD2 = (
    '          <span id="topBarLivePnlText" class="text-xs sm:text-sm lg:text-base font-black font-mono whitespace-nowrap text-slate-300">$0.00</span>\n'
    '        </div>'
)
NEW2 = OLD2 + (
    '\n\n'
    '        <!-- Account Balance and Spinning Bitcoin -->\n'
    '        <div class="sleek-glass-card flex flex-col items-end justify-center px-2.5 py-1 sm:px-3 sm:py-1.5 self-stretch shrink-0 min-w-[84px] leading-tight" title="Account Balance">\n'
    '          <div class="flex items-center gap-1.5">\n'
    '            <span class="inline-block animate-spin text-amber-400 text-sm font-black">\u20bf</span>\n'
    '            <span class="text-[7px] sm:text-[8px] font-mono font-bold uppercase tracking-wider text-slate-400 whitespace-nowrap">Balance</span>\n'
    '          </div>\n'
    '          <span id="topBarAccountBalanceText" class="text-xs sm:text-sm lg:text-base font-black font-mono whitespace-nowrap text-emerald-400">$--.--</span>\n'
    '        </div>'
)
if OLD2 in text:
    text = text.replace(OLD2, NEW2, 1)
    applied.append('PATCH 2: Spinning Bitcoin + Balance widget')
else:
    print('WARN: PATCH 2 target not found', file=sys.stderr)

# ── PATCH 3: Wire balance element to live polling JS ─────────────────────────
OLD3 = (
    '          if (tradeLogBalEl) tradeLogBalEl.innerText = formatted;\n'
    '        }'
)
NEW3 = (
    '          if (tradeLogBalEl) tradeLogBalEl.innerText = formatted;\n'
    '          const topBarBalEl = document.getElementById("topBarAccountBalanceText");\n'
    '          if (topBarBalEl) topBarBalEl.innerText = formatted;\n'
    '        }'
)
count3 = text.count(OLD3)
if count3 >= 1:
    text = text.replace(OLD3, NEW3, 1)
    applied.append('PATCH 3: Balance JS sync')
else:
    print('WARN: PATCH 3 target not found', file=sys.stderr)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(text)

print(f'Done. {orig_len} -> {len(text)} bytes')
for a in applied:
    print(f'  ok {a}')
if len(applied) < 3:
    sys.exit(1)
