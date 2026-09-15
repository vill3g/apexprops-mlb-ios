import os

def fix():
    file_path = 'static/index.html'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''      window.cachedBtcPredictedOutcome = tb.predicted_outcome || "";
      
      const nowSec = Math.floor(Date.now() / 1000);
      const elapsed = nowSec % 900;'''

    injection = '''      window.cachedBtcPredictedOutcome = tb.predicted_outcome || "";
      
      const nowSec = Math.floor(Date.now() / 1000);
      const intervalId = Math.floor(nowSec / 900) * 900;
      const elapsed = nowSec % 900;

      // Force sync with locked prediction if available to prevent UI desyncs from real-time polling
      if (elapsed >= 30 && window.lockedContractForecast && window.lockedContractForecast.intervalId === intervalId) {
          tb.predicted_outcome = window.lockedContractForecast.outcome;
          tb.probability_percent = window.lockedContractForecast.probability_percent;
          tb.predicted_outcome_probability = window.lockedContractForecast.probability_percent;
      }'''

    content = content.replace(target, injection)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    fix()
    print("Patched renderBtcPredictor to sync with locked forecast!")
