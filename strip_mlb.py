import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Remove deepDiveModal HTML
text = re.sub(r'<!-- Deep Dive Modal for MLB Batter/Pitcher Props -->.*?</div>\s*</div>\s*</div>', '', text, flags=re.DOTALL)

# 2. Remove loadMLBData function
text = re.sub(r'async function loadMLBData\(\) \{.*?\n      \}', '', text, flags=re.DOTALL)

# 3. Remove loadPitcherKs function
text = re.sub(r'async function loadPitcherKs\(\) \{.*?\n      \}', '', text, flags=re.DOTALL)

# 4. Remove openModal function
text = re.sub(r'function openModal\(id\) \{.*?\n      \}', '', text, flags=re.DOTALL)

# 5. Remove openPitcherModal function
text = re.sub(r'function openPitcherModal\(id\) \{.*?\n      \}', '', text, flags=re.DOTALL)

# 6. Remove renderGameLog function
text = re.sub(r'function renderGameLog\(p, isPitcher\) \{.*?\n      \}', '', text, flags=re.DOTALL)

# 7. Remove getDemoPlayerProps
text = re.sub(r'function getDemoPlayerProps\(\) \{.*?\n      \}', '', text, flags=re.DOTALL)

# 8. Clean up switchMode
new_switchMode = '''      function switchMode(mode) {
        activeMode = 'btc_analyzer';
        document.getElementById('btcAnalyzerSection').classList.remove('hidden');
        triggerBtcAnalysis();
      }'''
text = re.sub(r'function switchMode\(mode\) \{.*?triggerBtcAnalysis\(\);\n          \}\n        \}\n      \}', new_switchMode, text, flags=re.DOTALL)

# 9. Clean up keydown refresh event
new_keydown = '''      window.addEventListener('keydown', (e) => {
        if (e.key === 'r' || e.key === 'R') {
          if (activeMode === 'btc_analyzer') {
            triggerBtcAnalysis();
          }
        }
      });'''
text = re.sub(r'window\.addEventListener\(\'keydown\', \(e\) => \{.*?\n      \}\);', new_keydown, text, flags=re.DOTALL)

# 10. Clean up refreshData pull-to-refresh
new_refresh = '''      async function refreshData() {
        if (isRefreshing) return;
        isRefreshing = true;
        const spinner = document.getElementById('pullSpinner');
        if (spinner) spinner.classList.add('animate-spin');
        
        try {
          if (activeMode === 'btc_analyzer') {
            await triggerBtcAnalysis();
          }
        } finally {
          setTimeout(() => {
            if (spinner) spinner.classList.remove('animate-spin');
            isRefreshing = false;
          }, 500);
        }
      }'''
text = re.sub(r'async function refreshData\(\) \{.*?\n      \}', new_refresh, text, flags=re.DOTALL)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("MLB code stripped")
