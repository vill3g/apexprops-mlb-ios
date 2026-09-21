with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Remove deepDiveModal HTML
start = text.find('<!-- Deep Dive Modal for MLB Batter/Pitcher Props -->')
end = text.find('<!-- MLB Multi-Prop Parlay Builder Slip -->')
if start != -1 and end != -1:
    text = text[:start] + text[end:]

start = text.find('<!-- MLB Multi-Prop Parlay Builder Slip -->')
end = text.find('<!-- Confirmation Modal -->')
if start != -1 and end != -1:
    text = text[:start] + text[end:]

# 2. Remove functions
import re
text = re.sub(r'function getDemoPlayerProps\(\) \{.*?return \[.*?\];\n    \}', '', text, flags=re.DOTALL)
text = re.sub(r'function renderGameLog\(p, isPitcher\) \{.*?\}\n      \}\n    \}', '', text, flags=re.DOTALL)
text = re.sub(r'function openModal\(id\) \{.*?safeSet\(\'modalWeatherVenue\', \'innerText\', .*? Conditions\);\n    \}', '', text, flags=re.DOTALL)
text = re.sub(r'function openPitcherModal\(id\) \{.*?document\.getElementById\(\'deepDiveModal\'\)\?\.classList\.remove\(\'hidden\'\);\n    \}', '', text, flags=re.DOTALL)
text = re.sub(r'function closeModal\(\) \{.*?unlockBodyScroll\(\);\n    \}', '', text, flags=re.DOTALL)
text = re.sub(r'function toggleSlip\(id\) \{.*?updateSlipUI\(\);\n    \}', '', text, flags=re.DOTALL)
text = re.sub(r'function updateSlipUI\(\) \{.*?\}\n      \}\n    \}', '', text, flags=re.DOTALL)
text = re.sub(r'function getAnyProp\(id\) \{.*?return allPropsData\.find.*?;\n    \}', '', text, flags=re.DOTALL)
text = re.sub(r'async function buildParlaySlip\(\) \{.*?\}\n      \}\n    \}', '', text, flags=re.DOTALL)
text = re.sub(r'function handlePlayerHeadshotError.*?\}\n    \}', '', text, flags=re.DOTALL)

# 3. Clean up switchMode
new_switchMode = '''function switchMode(mode) {
      activeMode = 'btc_analyzer';
      const dd = document.getElementById('modeDropdown');
      if (dd) {
        dd.value = 'btc_analyzer';
        dd.blur();
      }
      const vBtc = document.getElementById('view_btc_analyzer');
      const btnBtc = document.getElementById('tabBtnBtc');
      const bottomSlipBar = document.getElementById('bottomSlipBar');
      if (vBtc) vBtc.classList.remove('hidden');
      if (bottomSlipBar) bottomSlipBar.classList.add('hidden');
      if (btnBtc) {
        btnBtc.className = "px-3 py-1.5 rounded-xl text-xs sm:text-sm font-black transition-all bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20 flex items-center gap-1.5";
      }
    }'''
text = re.sub(r'function switchMode\(mode\) \{.*?\}\n        \}\n      \}', new_switchMode, text, flags=re.DOTALL)

# 4. Clean up refreshAllData
new_refresh = '''async function refreshAllData() {
      updateLiveClock();
      try {
        await triggerBtcAnalysis();
        fetch('/api/live/poll').catch(() => {});
      } catch (err) {
        console.warn('PTR refresh error:', err);
      }
    }'''
text = re.sub(r'async function refreshAllData\(\) \{.*?\}\n      \}', new_refresh, text, flags=re.DOTALL)

# 5. Clean up variables
text = re.sub(r'let activeMode = \'mlb_hrrbi\';', 'let activeMode = \'btc_analyzer\';', text)
text = re.sub(r'let top5Picks = \[\];\n    let allPropsData = \[\];\n    let slip = \[\];\n    let currentModalPlayer = null;\n    let isRefreshing = false;\n    let allPitcherProps = \[\];\n    let top5Pitchers = \[\];', 'let isRefreshing = false;', text)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("Safe removal complete!")
