import sys
import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    c = f.read()

# Normalize line endings just in case for exact match
c_norm = c.replace('\r\n', '\n')

# 1. Expand saveKalshiSettings()
saveKalshi_stub = """    async function saveKalshiSettings() {
      showAppToast("Settings Saved", "Trade parameters applied successfully", "success");
    }"""

saveKalshi_impl = """    async function saveKalshiSettings() {
      try {
        const triggerWindow = document.getElementById("settingTriggerWindow")?.value || "standard";
        const predMode = document.getElementById("settingPredictionMode")?.checked || false;
        const trendGuard = document.getElementById("settingTrendGuard")?.checked || false;
        const autoTp = document.getElementById("settingAutoTakeProfit")?.checked || false;
        
        const settings = {
          tradingMode: kalshiTradingMode,
          convictionFilter: typeof kalshiConvictionFilter !== 'undefined' ? kalshiConvictionFilter : 'APLUS',
          contractsCount: kalshiCurrentContracts,
          audioEnabled: btcAudioEnabled,
          triggerWindow,
          predMode,
          trendGuard,
          autoTp
        };
        
        localStorage.setItem("kalshiGeneralSettings", JSON.stringify(settings));
        
        // Push backend toggles if needed (e.g. prediction mode)
        const apiBase = getKalshiApiBase();
        await fetch(`${apiBase}/api/btc/trade/prediction_mode?enabled=${predMode}`, { method: "POST" }).catch(()=>{});
        
        showAppToast("Settings Saved", "Trade parameters applied successfully", "success");
      } catch(e) {
        showAppToast("Save Error", String(e), "error");
      }
    }

    async function loadKalshiSettingsFromStorage() {
      try {
        const saved = localStorage.getItem("kalshiGeneralSettings");
        if (!saved) return;
        const settings = JSON.parse(saved);
        
        if (settings.tradingMode && settings.tradingMode !== kalshiTradingMode) {
          toggleKalshiTradingMode(); // will flip it
        }
        
        if (settings.convictionFilter) {
          setConvictionFilter(settings.convictionFilter);
        }
        
        if (settings.contractsCount) {
          kalshiCurrentContracts = settings.contractsCount;
          const input = document.getElementById("kalshiContractSizeInput");
          if (input) input.value = (kalshiCurrentContracts * kalshiCurrentPriceEst).toFixed(2);
        }
        
        if (typeof settings.audioEnabled === 'boolean') {
          if (settings.audioEnabled !== btcAudioEnabled) toggleBtcAudio();
        }
        
        const winSelect = document.getElementById("settingTriggerWindow");
        if (winSelect && settings.triggerWindow) winSelect.value = settings.triggerWindow;
        
        const predCb = document.getElementById("settingPredictionMode");
        if (predCb && typeof settings.predMode === 'boolean') {
           predCb.checked = settings.predMode;
        }
        
        const tgCb = document.getElementById("settingTrendGuard");
        if (tgCb && typeof settings.trendGuard === 'boolean') tgCb.checked = settings.trendGuard;
        
        const autoTpCb = document.getElementById("settingAutoTakeProfit");
        if (autoTpCb && typeof settings.autoTp === 'boolean') autoTpCb.checked = settings.autoTp;
        
      } catch(e) {
        console.warn("Failed to load general settings from storage:", e);
      }
    }"""

if saveKalshi_stub in c_norm:
    c_norm = c_norm.replace(saveKalshi_stub, saveKalshi_impl)
else:
    print("Warning: saveKalshi_stub not found.")

# 2. saveScalpSettings
scalp_save_search = """        showAppToast("Scalper Saved", "Scalp parameters updated successfully", "success");
        loadScalpConfigUI();"""

scalp_save_replace = """        localStorage.setItem("scalpSettings", JSON.stringify(patchBody));
        showAppToast("Scalper Saved", "Scalp parameters updated successfully", "success");
        loadScalpConfigUI();"""

if scalp_save_search in c_norm:
    c_norm = c_norm.replace(scalp_save_search, scalp_save_replace)

load_scalp_stub = """    async function loadScalpConfigUI() {"""
load_scalp_impl = """    async function loadScalpSettingsFromStorage() {
      try {
        const saved = localStorage.getItem("scalpSettings");
        if (saved) {
          const cfg = JSON.parse(saved);
          if (cfg.price_move_threshold) document.getElementById("scalpPriceMoveThreshold").value = cfg.price_move_threshold;
          if (cfg.profit_target) document.getElementById("scalpProfitTarget").value = cfg.profit_target;
          if (cfg.loss_target) document.getElementById("scalpLossTarget").value = cfg.loss_target;
          if (cfg.minimum_conviction) document.getElementById("scalpMinConviction").value = cfg.minimum_conviction;
          if (cfg.max_contracts) document.getElementById("scalpMaxContracts").value = cfg.max_contracts;
          if (cfg.max_trades_per_interval) document.getElementById("scalpMaxTradesPerInterval").value = cfg.max_trades_per_interval;
        }
      } catch(e) {}
    }

    async function loadScalpConfigUI() {"""

if load_scalp_stub in c_norm:
    c_norm = c_norm.replace(load_scalp_stub, load_scalp_impl)

# 3. Chart Settings Persistence
chart_init_search = """    function initTradingViewChart(tf = "15m") {"""
chart_init_replace = """    function initTradingViewChart(tf = null) {
      if (!tf) {
        try {
          const saved = localStorage.getItem("btcChartConfig");
          if (saved) {
            const cfg = JSON.parse(saved);
            tf = cfg.timeframe || "15m";
          } else {
            tf = "15m";
          }
        } catch(e) { tf = "15m"; }
      }
      btcCurrentTimeframe = tf;"""

if chart_init_search in c_norm:
    c_norm = c_norm.replace(chart_init_search, chart_init_replace)
else:
    print("Warning: chart_init_search not found.")

chart_save_search = """      initTradingViewChart(tf);
      triggerBtcAnalysis();"""
chart_save_replace = """      try { localStorage.setItem("btcChartConfig", JSON.stringify({ timeframe: tf })); } catch(e){}
      initTradingViewChart(tf);
      triggerBtcAnalysis();"""
      
if chart_save_search in c_norm:
    c_norm = c_norm.replace(chart_save_search, chart_save_replace)


# 4. Exact 1-Minute Prediction Refresh
clock_search = """      const barEl = document.getElementById("btcCountdownBar");
      if (barEl) {
        const pct = ((900 - secondsLeft) / 900) * 100;
        barEl.style.width = `${pct.toFixed(1)}%`;
      }"""

clock_replace = """      const barEl = document.getElementById("btcCountdownBar");
      if (barEl) {
        const pct = ((900 - secondsLeft) / 900) * 100;
        barEl.style.width = `${pct.toFixed(1)}%`;
      }

      // Exact 1-minute post-rollover refresh logic
      if (secondsLeft === 840) {
        const currentBucket = Math.floor(Date.now() / (15 * 60 * 1000));
        if (window._last1MinuteRefreshBucket !== currentBucket) {
           window._last1MinuteRefreshBucket = currentBucket;
           console.log("Exactly 1 minute after contract start. Triggering mandatory prediction refresh.");
           fetchBtcKlinesDirect();
           setTimeout(triggerBtcAnalysis, 1000);
        }
      }"""

if clock_search in c_norm:
    c_norm = c_norm.replace(clock_search, clock_replace)

# 5. initSettings call on start + Auto Refresh Interval
dom_content_loaded_search = """    window.addEventListener("DOMContentLoaded", detectAndAdaptDevice);"""
dom_content_loaded_replace = """    window.addEventListener("DOMContentLoaded", () => {
      detectAndAdaptDevice();
      loadKalshiSettingsFromStorage();
      loadScalpSettingsFromStorage();
    });
    
    // Auto Refresh 60s
    setInterval(() => {
        triggerBtcAnalysis();
    }, 60000);"""

if dom_content_loaded_search in c_norm:
    c_norm = c_norm.replace(dom_content_loaded_search, dom_content_loaded_replace)
else:
    print("Warning: dom_content_loaded_search not found.")


with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(c_norm)

print("Applied persistence and exact 1m refresh!")
