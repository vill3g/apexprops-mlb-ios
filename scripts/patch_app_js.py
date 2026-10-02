import re
import os

filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\app.js"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Define the new initTradingViewChart function
new_func = """    function initTradingViewChart(tf = null) {
      window.initTradingViewChart = initTradingViewChart;
      if (!tf) {
        try {
          const saved = localStorage.getItem("btcChartConfig");
          if (saved) {
            const cfg = JSON.parse(saved);
            tf = cfg.timeframe || "1m";
          } else {
            tf = "1m";
          }
        } catch(e) { tf = "1m"; }
      }
      btcCurrentTimeframe = tf;
      const container = document.getElementById("tradingview_btc_chart");
      if (!container) return;
      
      const tfMap = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "1h": "1h",
        "4h": "1h", // backend only supports up to 1h in current implementation
        "1d": "1h"
      };
      const interval = tfMap[tf] || "15m";

      if (currentTvInterval === interval && currentTvAsset === window.currentAsset && window.lwChart) {
        return; // Already initialized for this timeframe and asset
      }
      currentTvInterval = interval;
      currentTvAsset = window.currentAsset;

      // Ensure LightweightCharts is loaded
      if (typeof LightweightCharts === "undefined") {
        container.innerHTML = `
          <div class="flex flex-col items-center justify-center h-full text-slate-400 space-y-2">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-400"></div>
            <div class="text-xs font-mono">Loading Institutional Chart Engine...</div>
          </div>
        `;
        setTimeout(() => initTradingViewChart(tf), 500);
        return;
      }
      
      container.innerHTML = "";
      
      try {
        window.lwChart = LightweightCharts.createChart(container, {
          layout: { background: { type: 'solid', color: '#000000' }, textColor: '#94a3b8', fontSize: 11, attributionLogo: false },
          grid: { vertLines: { color: '#1e293b22' }, horzLines: { color: '#1e293b22' } },
          timeScale: { timeVisible: true, secondsVisible: false, borderColor: '#1e293b', rightOffset: 4 },
          rightPriceScale: { borderColor: '#1e293b', scaleMargins: { top: 0.1, bottom: 0.22 } },
          crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
          width: container.clientWidth || container.offsetWidth,
          height: container.clientHeight || container.offsetHeight,
        });

        const isLine = window.currentChartType === 'line';

        window.candleSeries = window.lwChart.addCandlestickSeries({
          upColor: '#22c55e', downColor: '#ef4444', borderUpColor: '#22c55e', borderDownColor: '#ef4444',
          wickUpColor: '#22c55e80', wickDownColor: '#ef444480',
          visible: !isLine,
        });

        window.lineSeries = window.lwChart.addLineSeries({
          color: '#00e5ff',
          lineWidth: 2,
          crosshairMarkerVisible: true,
          crosshairMarkerRadius: 4,
          priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
          visible: isLine,
        });

        window.volumeSeries = window.lwChart.addHistogramSeries({
          priceFormat: { type: 'volume' }, priceScaleId: 'vol',
          color: '#0052ff40',
        });
        window.lwChart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });

        // Responsive resize
        const ro = new ResizeObserver(entries => {
          const r = entries[0]?.contentRect;
          if (r && r.width > 0 && r.height > 0) {
            window.lwChart.applyOptions({ width: r.width, height: r.height });
          }
        });
        ro.observe(container);

        // Fetch Data Function
        const fetchChartData = async () => {
          try {
            const asset = window.currentAsset || 'BTC';
            const res = await fetch(`/api/engine/${asset}/chart?timeframe=${interval}&limit=300`);
            if (!res.ok) return;
            const d = await res.json();
            
            if (d.candles?.length) {
                if (window.candleSeries) window.candleSeries.setData(d.candles);
                if (window.lineSeries) {
                    window.lineSeries.setData(d.candles.map(c => ({ time: c.time, value: c.close })));
                }
            }
            if (d.volume?.length && window.volumeSeries) {
                window.volumeSeries.setData(d.volume);
            }
          } catch (e) {
            console.warn("Chart data fetch failed:", e);
          }
        };

        fetchChartData();
        
        // Start live polling if not already started
        if (window.chartRefreshInterval) clearInterval(window.chartRefreshInterval);
        window.chartRefreshInterval = setInterval(fetchChartData, 1500);

      } catch (err) {
        console.error("Institutional chart init error:", err);
      }
    }"""

# Use regex to replace the old function.
pattern = re.compile(r"    function initTradingViewChart\(tf = null\) \{.*?(?=\n    function initBtcChartOnce\(\) \{)", re.DOTALL)
new_content = pattern.sub(new_func, content)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Updated initTradingViewChart in app.js successfully.")
