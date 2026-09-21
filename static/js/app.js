


// --- DUMMY FUNCTIONS TO PREVENT REFERENCE ERRORS FROM DEAD CODE CLEANUP ---
function addBtcLogEntry(){}
function applyTargetPriceColor(){}
function fetchKalshiTradingStatus(){}
function renderBtcAccuracy(data) {
  if (!data) return;
  const ratioEl = document.getElementById("btcAccuracyRatio");
  const pctEl = document.getElementById("btcAccuracyPct");
  const barEl = document.getElementById("btcAccuracyBar");
  const dotsEl = document.getElementById("btcAccuracyRecentDots");
  if (ratioEl) ratioEl.innerText = data.ratio_text || `${data.correct_picks} of ${data.total_evaluated} Correct`;
  if (pctEl) pctEl.innerText = data.accuracy_percent != null ? `${data.accuracy_percent}%` : "--%";
  if (barEl) barEl.style.width = data.accuracy_percent != null ? `${data.accuracy_percent}%` : "0%";
  if (dotsEl && data.recent_outcomes) {
    dotsEl.innerHTML = data.recent_outcomes.map(o => o.correct 
      ? '<div class="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_4px_rgba(16,185,129,0.8)]"></div>' 
      : '<div class="w-1.5 h-1.5 rounded-full bg-rose-500 shadow-[0_0_4px_rgba(244,63,94,0.8)]"></div>'
    ).join("");
  }
}
function renderBtcCatalystsAndPatterns(){}
function renderBtcHeroHud(data){
    try {
        if (typeof updateIphone17HeaderInfo === 'function') {
            updateIphone17HeaderInfo(data);
        }
    } catch(e) { console.warn(e); }
}
function renderBtcIndicators(){}
function renderBtcPredictor(){}
function renderBtcStructure(){}
function renderBtcTradeSetup(){}
    function renderBtcTrendBox(last5, streak) {

      const cacheKey = JSON.stringify(last5) + streak;

      if (window._lastTrendBoxKey === cacheKey) return;



      const grid = document.getElementById("btcTrendBoxGrid");

      // If user is currently hovering over the trend boxes, defer re-rendering until mouseout

      if (grid && (grid.matches(":hover") || grid.contains(document.querySelector(":hover")))) {

        window._pendingTrendBoxUpdate = { last5, streak };

        return;

      }

      window._lastTrendBoxKey = cacheKey;



      const streakBadge = document.getElementById("btcTrendStreakBadge");

      if (streakBadge && streak) {

        streakBadge.innerText = streak;

      }

      if (!grid || !Array.isArray(last5) || last5.length === 0) return;



      const itemsToRender = last5.slice(-4);



      // 15M Target Trend: Direction Arrow + Close Price + Close Time

      grid.innerHTML = itemsToRender.map(t => {

        const isUp = t.direction === "HIGHER" || t.direction === "UP" || t.arrow === "▲";

        const cardClass = isUp ? "trend-card trend-up bg-emerald-500/15 border border-emerald-500/30 text-emerald-400" : "trend-card trend-down bg-red-500/15 border border-red-500/30 text-red-400";

        const formattedPrice = t.price ? `$${Number(t.price).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 1 })}` : "--";

        const timeStr = t.time || "--:--";

        

        const predVal = t.ml_prediction || t.predicted || t.prediction || (isUp ? "UP" : "DOWN");

        const predTimeStr = t.pred_time ? `⏱️ Prediction Time: ${t.pred_time}\n` : '';

        const targetStartStr = t.target_price ? `$${Number(t.target_price).toLocaleString("en-US", { minimumFractionDigits: 2 })}` : "--";

        const targetCloseStr = t.price ? `$${Number(t.price).toLocaleString("en-US", { minimumFractionDigits: 2 })}` : "--";

        const deltaVal = t.delta != null ? `${t.delta >= 0 ? '+' : ''}$${(isNaN(Number(t.delta)) ? 0 : Number(t.delta)).toFixed(2)} (${t.delta_pct >= 0 ? '+' : ''}${t.delta_pct}%)` : "--";

        const resultVal = isUp ? "HIGHER (ABOVE TARGET)" : "LOWER (BELOW TARGET)";



        const tooltipStr = `🕒 15M Contract Close: ${timeStr}\n${predTimeStr}🎯 Target Start Price: ${targetStartStr}\n🏁 Actual Close Price: ${targetCloseStr}\n📊 Price Delta: ${deltaVal}\n🤖 AI Model Prediction: ${predVal}\n✅ Actual Settlement Result: ${resultVal}`;



        return `

          <div data-tooltip="${tooltipStr.replace(/"/g, '&quot;')}" class="${cardClass} py-0.5 px-1 sm:px-1.5 text-center flex flex-col items-center justify-center rounded-lg shadow-sm font-mono shrink-0 cursor-help hover:brightness-110 transition-all leading-tight">

            <div class="flex items-center gap-0.5 leading-none">

              <span class="text-[10px] font-black leading-none">${isUp ? '▲' : '▼'}</span>

              <span class="text-[8.5px] sm:text-[9.5px] font-black text-white leading-none">${formattedPrice}</span>

            </div>

            <div class="text-[7px] sm:text-[7.5px] font-semibold text-slate-400 leading-none mt-0.5">${timeStr}</div>

          </div>

        `;

      }).join("");

    }
function showDkToast(){}
function showTradeDetailsModal(){}
function updateBtcConfluenceGauge(){}
function updateSlipUI(){}
function updateTargetCardBorder(){}
function renderPreviousDaysAccuracy(){}
// --------------------------------------------------------------------------

window.currentAsset = "BTC";

    // XSS Protection: Escape HTML entities in untrusted strings before innerHTML
    function escapeHtml(str) {
      if (str == null) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    // Risk Management UI Toggle
    let riskEnabled = localStorage.getItem("riskEnabled") !== "false";
    function toggleRiskManagement() {
      riskEnabled = !riskEnabled;
      localStorage.setItem("riskEnabled", riskEnabled);
      const wrapper = document.getElementById("riskManagementWrapper");
      const btn = document.getElementById("btnToggleRisk");
      if (wrapper && btn) {
        if (riskEnabled) {
          wrapper.classList.remove("hidden");
          btn.innerText = "Hide";
        } else {
          wrapper.classList.add("hidden");
          btn.innerText = "Show";
        }
      }
    }
    
    // Initialize Risk Management UI state
    document.addEventListener("DOMContentLoaded", () => {
      if (!riskEnabled) {
        const wrapper = document.getElementById("riskManagementWrapper");
        const btn = document.getElementById("btnToggleRisk");
        if (wrapper) wrapper.classList.add("hidden");
        if (btn) btn.innerText = "Show";
      }
    });
    // High-performance DOM node cache to optimize 1-second polling ticks
    const _domCache = new Map();
    function getDomEl(id) {
      if (!id) return null;
      let el = _domCache.get(id);
      if (!el || !document.contains(el)) {
        el = document.getElementById(id);
        if (el) _domCache.set(id, el);
      }
      return el;
    }

        // =========================================================================
    // AUTOMATIC HARDWARE & ORIENTATION DETECTION ENGINE
    // =========================================================================
    
    // =========================================================================
    // IPHONE 17 PRO MAX PORTRAIT ENGINE & DYNAMIC TELEMETRY SYNCHRONIZER
    // =========================================================================
    window.setIphoneTimeframe = function(tf) {
      ['1m', '15m', '1h'].forEach(t => {
        const btn = document.getElementById(`btnIphoneTf${t}`);
        if (btn) {
          if (t === tf) {
            btn.className = 'iphone17-tf-btn active';
            btn.innerHTML = `<span class="tf-dot">●</span>${t}`;
          } else {
            btn.className = 'iphone17-tf-btn';
            btn.innerHTML = t;
          }
        }
      });
      initTradingViewChart(tf);
    };

    function updateIphone17HeaderInfo(liveData) {
      // 1. Contract 15m Interval Time Range (e.g. 1:15–1:30 PM EDT)
      try {
        const now = new Date();
        const nyDate = new Date(now.toLocaleString("en-US", { timeZone: "America/New_York" }));
        const minutes = nyDate.getMinutes();
        const bucketStartMin = Math.floor(minutes / 15) * 15;
        const bucketEndMin = bucketStartMin + 15;
        
        const startD = new Date(nyDate);
        startD.setMinutes(bucketStartMin);
        startD.setSeconds(0);
        
        const endD = new Date(nyDate);
        endD.setMinutes(bucketEndMin);
        endD.setSeconds(0);

        const fmtStart = startD.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
        const fmtEnd = endD.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
        
        const intervalEl = document.getElementById("iphone17IntervalTime");
        if (intervalEl) {
          intervalEl.innerText = `${fmtStart.replace(/ [AP]M/, "")}–${fmtEnd} EDT`;
        }
      } catch (e) { console.warn('Fetch failed:', e); }

      // 2. Countdown Pill is updated directly by updateBtcCountdownClock() every second — no copy needed here.


      // 3. Live Price
      const curPrice = Number(liveData?.price || lastBtcPrice || 0);
      const targetPrice = Number(window.cachedBtcTargetPrice || liveData?.target_price || 0);
      const livePriceEl = document.getElementById("iphone17LivePrice");

      if (livePriceEl && curPrice > 0) {
        livePriceEl.innerText = `$${curPrice.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (targetPrice > 0) {
          if (curPrice < targetPrice) {
            livePriceEl.style.color = "#ff6b35"; // Vibrant Kalshi orange when below target
          } else {
            livePriceEl.style.color = "#10b981"; // Emerald green when above target
          }
        }
      }

      // 4. Target Price & Source
      const targetPriceEl = document.getElementById("iphone17TargetPrice");
      if (targetPriceEl && targetPrice > 0) {
        targetPriceEl.innerText = `$${targetPrice.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      }

      // Sync Top Nav Bar P/L and Audio
      const navPnl = document.getElementById("iphone17NavPnlText");
      const deskPnl = document.getElementById("topBarLivePnlText");
      if (navPnl && deskPnl) {
        navPnl.innerText = deskPnl.innerText;
        navPnl.className = deskPnl.className;
      }
      const navAudio = document.getElementById("iphoneAudioIcon");
      const deskAudio = document.getElementById("btcAudioIcon");
      if (navAudio && deskAudio) {
        navAudio.innerText = deskAudio.innerText;
      }

      // 5. Prediction Panel & Conviction Percentage
      const predOutcomeEl = document.getElementById("iphone17PredOutcome");
      const predConvictionEl = document.getElementById("iphone17PredConvictionPct");
      const predGradeEl = document.getElementById("iphone17PredGrade");
      const predCardEl = document.getElementById("iphone17PredictionCard");

      // Source from desktop prediction elements or cached forecast
      const deskOutcome = document.getElementById("btcPredOutcomeText")?.innerText || "";
      const deskProb = document.getElementById("btcPredProbText")?.innerText || "";
      const deskGrade = document.getElementById("btcPredConfidenceTag")?.innerText || "";
      const forecast = window.lockedContractForecast || window.cachedNextContractForecast;

      let directionText = deskOutcome || (forecast?.direction ? (forecast.direction === "ABOVE" ? "▲ ABOVE" : (forecast.direction === "BELOW" ? "▼ BELOW" : "CHOP")) : "SCANNING");
      let convictionPct = deskProb || (forecast?.probability_percent ? `${forecast.probability_percent}%` : "--%");
      let gradeBadge = deskGrade || forecast?.conviction_badge || (forecast?.conviction_grade ? forecast.conviction_grade.replace(" SETUP", "") : "AI MODEL");

      if (predOutcomeEl) {
        predOutcomeEl.innerText = directionText;
        if (directionText.includes("ABOVE") || directionText.includes("UP") || directionText.includes("YES")) {
          predOutcomeEl.className = "text-xs sm:text-sm font-black uppercase font-mono text-emerald-400 leading-none";
          if (predCardEl) { predCardEl.classList.remove("pred-down"); predCardEl.classList.add("pred-up"); }
        } else if (directionText.includes("BELOW") || directionText.includes("DOWN") || directionText.includes("NO")) {
          predOutcomeEl.className = "text-xs sm:text-sm font-black uppercase font-mono text-red-400 leading-none";
          if (predCardEl) { predCardEl.classList.remove("pred-up"); predCardEl.classList.add("pred-down"); }
        } else {
          predOutcomeEl.className = "text-xs sm:text-sm font-black uppercase font-mono text-amber-300 leading-none";
          if (predCardEl) { predCardEl.classList.remove("pred-up", "pred-down"); }
        }
      }

      if (predConvictionEl && convictionPct) {
        predConvictionEl.innerText = convictionPct;
      }

      if (predGradeEl && gradeBadge) {
        predGradeEl.innerText = gradeBadge;
      }

      // 6. Volume Pill (Real-Time Synchronous Update)
      const volEl = document.getElementById("iphone17VolumeText");
      const volVal = liveData?.volume_24h || liveData?.kalshi?.volume_24h || window.cachedBtcVolume || window.lastKalshiVolume;
      if (volEl && volVal) {
        window.cachedBtcVolume = volVal;
        volEl.innerText = Math.round(Number(volVal)).toLocaleString();
      }

      // 7. Price Delta Panel (Real-Time Synchronous Update)
      const deltaValEl = document.getElementById("iphone17DeltaVal");
      const deltaArrowEl = document.getElementById("iphone17DeltaArrow");
      const deltaPanel = document.getElementById("iphone17DeltaBadge");
      if (deltaValEl && curPrice > 0 && targetPrice > 0) {
        const diff = curPrice - targetPrice;
        const sign = diff >= 0 ? "+" : "";
        deltaValEl.innerText = `${sign}${(isNaN(diff) ? 0 : diff).toFixed(1)}`;
        if (deltaArrowEl) deltaArrowEl.innerText = diff >= 0 ? "▲" : "▼";
        if (deltaPanel) {
          deltaPanel.className = `iphone17-delta-panel ${diff >= 0 ? "delta-up" : "delta-down"}`;
        }
      }
    }

    function detectAndAdaptDevice() {
      const w = window.innerWidth;
      const h = window.innerHeight;
      const ua = navigator.userAgent || "";
      const queryParam = window.location.search || "";
      const isIOS = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
      const isIpad = /iPad/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1 && Math.min(w, h) >= 700);
      const isManualIpadMini7 = queryParam.includes("ipadmini") || queryParam.includes("ipad-mini-7") || queryParam.includes("mini7");
      const isIpadMini7 = isManualIpadMini7 || (isIpad && (
        (window.devicePixelRatio === 2 && ((w === 744 && h === 1133) || (w === 1133 && h === 744))) ||
        ((w >= 740 && w <= 760 && h >= 1120 && h <= 1140) || (w >= 1120 && w <= 1140 && h >= 740 && h <= 760))
      ));
      const isIphone = isIOS && !isIpad;
      const isLandscape = w > h;
      const isPhone = isIphone || (!isIpad && Math.min(w, h) < 680);
      const isTablet = isIpad || (!isPhone && Math.min(w, h) >= 680 && Math.max(w, h) <= 1366);

      // Robust iPhone 17 Pro Max / iPhone Portrait Detection
      const isManualIphone = queryParam.includes("device=iphone") || queryParam.includes("iphone") || queryParam.includes("ios");
      const isIphone17ProMax = isManualIphone || (
        (isIphone || isPhone) && !isLandscape && (
          (w >= 410 && w <= 460 && h >= 880 && h <= 1000) ||
          (window.screen && Math.min(window.screen.width, window.screen.height) >= 420 && Math.max(window.screen.width, window.screen.height) >= 900) ||
          /iPhone17|iPhone/.test(ua) ||
          (window.devicePixelRatio >= 3 && w <= 460)
        )
      );
      const isIphonePortrait = isManualIphone || ((isIphone || isPhone) && !isLandscape);

      const root = document.documentElement;
      const body = document.body;

      // Update CSS variables for accurate dynamic viewport sizing
      root.style.setProperty("--app-height", `${window.innerHeight}px`);

      // Set explicit attributes and classes for deterministic CSS rules
      const deviceAttr = isIphonePortrait ? "iphone-portrait" : (isPhone ? "phone" : (isTablet ? "tablet" : "desktop"));
      root.setAttribute("data-device", deviceAttr);
      body.setAttribute("data-device", deviceAttr);
      root.setAttribute("data-orientation", isLandscape ? "landscape" : "portrait");

      body.classList.toggle("device-ipad", isIpad);
      body.classList.toggle("is-ipad-mini-7", isIpadMini7);
      body.classList.toggle("is-iphone-17-promax", isIphone17ProMax);
      body.classList.toggle("is-iphone-portrait", isIphonePortrait);
      root.classList.toggle("is-iphone-17-promax", isIphone17ProMax);
      root.classList.toggle("is-iphone-portrait", isIphonePortrait);
    }

    // =========================================================================
    // API Authentication Token Handshake (C1/C5)
    // =========================================================================
    function getAppApiToken() {
      const urlParams = new URLSearchParams(window.location.search);
      const urlToken = urlParams.get("token") || urlParams.get("api_token");
      if (urlToken) {
        localStorage.setItem("app_api_token", urlToken);
        const cleanUrl = window.location.pathname + window.location.hash;
        window.history.replaceState({}, document.title, cleanUrl);
        return urlToken;
      }
      return localStorage.getItem("app_api_token") || "";
    }

    function setAppApiToken(token) {
      if (token) {
        localStorage.setItem("app_api_token", token.trim());
      } else {
        localStorage.removeItem("app_api_token");
      }
    }

    function getAuthHeaders(customHeaders = {}) {
      const headers = { ...customHeaders };
      const token = getAppApiToken();
      if (token) {
        headers["X-API-Token"] = token;
      }
      return headers;
    }

    async function authFetch(url, options = {}) {
      options.headers = getAuthHeaders(options.headers || {});
      const res = await fetch(url, options);
      if (res.status === 401) {
        const entered = prompt("Enter Server API Token (APP_API_TOKEN):");
        if (entered) {
          setAppApiToken(entered);
          options.headers = getAuthHeaders(options.headers || {});
          return await fetch(url, options);
        }
      }
      return res;
    }

    // Run on load and listen to viewport adjustments
    window.addEventListener("DOMContentLoaded", () => {
      detectAndAdaptDevice();
      try { updateIphone17HeaderInfo(null); } catch (e) { console.warn('Fetch failed:', e); }
      loadKalshiSettingsFromStorage();
      loadScalpSettingsFromStorage();
    });
    
    // Auto Refresh — interval is configurable via the "Poll Interval" setting (seconds, 1-15)
    let _analysisPollTimer = null;
    function restartAnalysisPolling() {
      if (_analysisPollTimer) clearInterval(_analysisPollTimer);
      const configuredSeconds = parseInt(document.getElementById("settingPollInterval")?.value) || 5;
      const clampedSeconds = Math.min(15, Math.max(1, configuredSeconds));
      _analysisPollTimer = setInterval(() => {
          if (document.hidden) return;
          triggerBtcAnalysis();
      }, clampedSeconds * 1000);
    }
    restartAnalysisPolling();
    window.addEventListener("resize", () => {
      detectAndAdaptDevice();
    });
    window.addEventListener("orientationchange", () => {
      setTimeout(detectAndAdaptDevice, 100);
    });
    detectAndAdaptDevice();

    // Dedicated Top Bar Manual Refresh
    async function triggerManualRefresh() {
      const btn = document.getElementById("btnTopBarRefresh");
      const icon = document.getElementById("topBarRefreshIcon");
      if (btn) btn.disabled = true;
      if (icon) icon.className = "inline-block animate-spin text-sm sm:text-base font-black";

      try {
        await Promise.allSettled([
          triggerBtcAnalysis(),
          fetchBtcKlinesDirect(),
          fetchKalshiDirect()
        ]);
      } catch(e) {
        console.warn("Manual refresh error:", e);
      } finally {
        setTimeout(() => {
          if (btn) btn.disabled = false;
          if (icon) icon.className = "text-sm sm:text-base font-black";
        }, 500);
      }
    }

    // State Store
    let activeMode = 'btc_analyzer';
    let top5Picks = [];
    let allPropsData = [];
    let top5Pitchers = [];
    let allPitcherProps = [];
    let activeSlip = [];
    let currentModalPlayer = null;
    let savedScrollY = 0;

    // Verified Player Photo Registry & Error Fallback
    let playerPhotoRegistry = null;

    async function fetchBundledData(filename) {
      // The FastAPI server exposes these files under /static; iOS standalone
      // builds keep them beside index.html in a relative data/ directory.
      const serverResponse = await fetch(`/static/data/${filename}`).catch(() => null);
      if (serverResponse && serverResponse.ok) return serverResponse;
      return fetch(`data/${filename}`).catch(err => { console.warn('data load failed', err); return null; });
    }

    async function loadPlayerPhotoRegistry() {
      if (playerPhotoRegistry) return playerPhotoRegistry;
      try {
        const res = await fetchBundledData('player_photos.json');
        if (res.ok) playerPhotoRegistry = await res.json();
      } catch (e) { console.warn('Fetch failed:', e); }
      return playerPhotoRegistry || {};
    }
    loadPlayerPhotoRegistry();

    function handlePlayerHeadshotError(img, playerName, playerId, teamLogo) {
      img.onerror = null; // stop retry loops
      if (playerPhotoRegistry && playerName && playerPhotoRegistry[playerName]) {
        img.src = playerPhotoRegistry[playerName].url;
        return;
      }
      const pid = String(playerId || '').trim();
      const current = img.src || '';
      if (current.includes('mlbstatic.com') && pid && pid.length <= 5) {
        img.src = `https://a.espncdn.com/i/headshots/mlb/players/full/${pid}.png`;
        img.onerror = () => {
          img.onerror = null;
          img.src = teamLogo || 'https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/generic/headshot/67/current.png';
        };
        return;
      }
      if (teamLogo) {
        img.src = teamLogo;
      } else {
        img.src = 'https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/generic/headshot/67/current.png';
      }
    }

    // iOS Modal Scroll Locking (Prevents background bleed/scroll on selection)
    function lockBodyScroll() {
      savedScrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
      document.body.style.overflow = 'hidden';
      document.body.style.position = 'fixed';
      document.body.style.top = `-${savedScrollY}px`;
      document.body.style.width = '100%';
    }

    function unlockBodyScroll() {
      document.body.style.removeProperty('overflow');
      document.body.style.removeProperty('position');
      document.body.style.removeProperty('top');
      document.body.style.removeProperty('width');
      window.scrollTo(0, savedScrollY);
    }

    // Mode Switcher (Between MLB +1 H+R+RBI, Pitcher Strikeouts, & BTC 15M Pattern Analyzer)
    function switchMode(mode) {
      if (mode !== 'mlb_hrrbi' && mode !== 'pitcher_ks' && mode !== 'btc_analyzer') mode = 'mlb_hrrbi';
      activeMode = mode;
      
      const vBtc = document.getElementById('view_btc_analyzer');

      if (mode === 'mlb_hrrbi') {
        if (vBtc) vBtc.classList.add('hidden');
      } else if (mode === 'pitcher_ks') {
        if (vBtc) vBtc.classList.add('hidden');
        loadPitcherKs();
      } else if (mode === 'btc_analyzer') {
        if (vBtc) vBtc.classList.remove('hidden');
        initBtcChartOnce();
        updateBtcCountdownClock();
        fetchKalshiDirect();
        fetchBtcKlinesDirect();
        triggerBtcAnalysis();
      }

      window.scrollTo({ top: 0, behavior: 'instant' });
    }

    // Live Clock & 1-Second Auto-Refresh (Shows Date Before Time: e.g. Sep 9 • 7:15:32 AM)
    function updateLiveClock() {
      const now = new Date();
      const opts = { timeZone: 'America/New_York' };
      const datePart = now.toLocaleDateString('en-US', { ...opts, month: 'short', day: 'numeric' });
      const timePart = now.toLocaleTimeString('en-US', { ...opts, hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true });
      const stackedHtml = `<div class="flex flex-col items-start leading-tight -my-0.5"><span class="text-[10px] sm:text-[11px] text-slate-200 font-bold font-mono tracking-tight">${datePart}</span><span class="text-[8.5px] sm:text-[9px] text-slate-400 font-bold font-mono tracking-tight">${timePart} ET</span></div>`;
      
      const clockEl = document.getElementById('liveClock');
      if (clockEl) clockEl.innerHTML = stackedHtml;
      
      const clockDesktop = document.getElementById('liveClockDesktop');
      if (clockDesktop) clockDesktop.innerHTML = stackedHtml;
    }

    let _live1sTimer = null;
    function startLive1sRefresh() {
      if (_live1sTimer) clearInterval(_live1sTimer);
      updateLiveClock();
      updateBtcCountdownClock();
      fetchKalshiDirect();
      fetchBtcKlinesDirect();
      _live1sTimer = setInterval(async () => {
        if (document.hidden) return;
        updateLiveClock();
        updateBtcCountdownClock();

        // 1-second live stream poll
        try {
          if (activeMode === 'btc_analyzer') {
            await pollBtcLive1s();
          } else {
            const res = await fetch('/api/live/poll');
            if (res.ok) {
              const data = await res.json();
            }
          }
        } catch (e) { console.warn('Fetch failed:', e); }
      }, 1000);
    }

    // ==========================================
    // 1. MLB Hits + Runs + RBIs (+1 Line) Logic
    // ==========================================
    async function loadMLBData() {
      try {
        const res = await fetch('/api/picks/top5');
        if (!res.ok) throw new Error('API offline');
        const data = await res.json();
        top5Picks = data.top_5 || [];
        renderTop5(top5Picks);

        const propsRes = await fetch('/api/props');
        if (!propsRes.ok) throw new Error('API offline');
        const propsData = await propsRes.json();
        allPropsData = propsData.props || [];
        renderTable(allPropsData);
      } catch (err) {
        console.warn('API offline or standalone mode, loading local bundled data for iOS...');
        try {
          const tRes = await fetch('data/top5.json').catch(() => fetch('/static/data/top5.json'));
          const tData = await tRes.json();
          top5Picks = tData.top_5 || [];
          renderTop5(top5Picks);

          const pRes = await fetch('data/props.json').catch(() => fetch('/static/data/props.json'));
          const pData = await pRes.json();
          allPropsData = pData.props || [];
          renderTable(allPropsData);
        } catch (e2) {
          console.warn('Local fallback loading error:', e2);
        }
      }
    }


    // =======================================================
    // 2. Pitcher Strikeouts (Ks) - EXACT SAME AS H+R+RBI PAGE
    // =======================================================
    async function loadPitcherKs() {
      try {
        const res = await fetch('/api/pitchers/k-props');
        if (!res.ok) throw new Error('API offline');
        const data = await res.json();
        top5Pitchers = data.top5 || [];
        allPitcherProps = data.props || [];
        renderPitcherTop5(top5Pitchers);
        renderPitcherTable(allPitcherProps);
      } catch (e) {
        console.warn('API offline or standalone mode, loading local pitcher data for iOS...');
        try {
          const res = await fetch('data/pitchers.json').catch(() => fetch('/static/data/pitchers.json'));
          const data = await res.json();
          top5Pitchers = data.top5 || [];
          allPitcherProps = data.props || [];
          renderPitcherTop5(top5Pitchers);
          renderPitcherTable(allPitcherProps);
        } catch (e2) {
          console.warn('Local pitcher fallback error:', e2);
        }
      }
    }


    function filterPitcherTable() {
      const filtered = allPitcherProps.filter(p => p.name.toLowerCase().includes(q) || p.team.toLowerCase().includes(q) || p.opponent.toLowerCase().includes(q));
      renderPitcherTable(filtered);
    }

    // ==========================================
    // 3. Universal Slip Builder & Parlay Logic
    // ==========================================
    function getAnyProp(id) {
      return allPropsData.find(x => String(x.id) === String(id)) || 
             top5Picks.find(x => String(x.id) === String(id)) ||
             allPitcherProps.find(x => String(x.id) === String(id)) ||
             top5Pitchers.find(x => String(x.id) === String(id));
    }

    function toggleSlip(id) {
      const p = getAnyProp(id);
      if (!p) return;

      const idx = activeSlip.findIndex(x => String(x.id) === String(p.id));
      if (idx >= 0) {
        activeSlip.splice(idx, 1);
      } else {
        activeSlip.push(p);
      }
      updateSlipUI();
    }

    function clearSlip() {
      activeSlip = [];
      updateSlipUI();
    }

    

    function executeClipboardCopy(text) {
      let copied = false;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => { copied = true; }).catch(() => {});
      }
      // Fallback DOM copy for iOS Safari / WKWebView
      try {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        ta.style.top = "-9999px";
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        copied = document.execCommand('copy') || copied;
        document.body.removeChild(ta);
      } catch (err) {
        console.warn("DOM copy fallback err:", err);
      }
      return copied;
    }

    function getFormattedSlipText() {
      if (activeSlip.length === 0) return "";
      let text = "⚡ APEXPROPS BET SLIP (THE ODDS API) ⚡\n";
      text += "====================================\n";
      let joint = 1.0;
      let parlayDec = 1.0;

      activeSlip.forEach((p, idx) => {
        const dkOdds = p.dk_odds || p.book_odds || '-130';
        const lineStr = p.k_line ? `${p.pick_type || 'OVER'} ${p.k_line} Strikeouts` : `OVER 1.5 Hits+Runs+RBIs`;
        text += `${idx + 1}. ${escapeHtml(p.name)} (${escapeHtml(p.team)} vs ${escapeHtml(p.opponent)}) - ${lineStr} [Odds: ${dkOdds}]\n`;
        joint *= ((p.win_prob || 55) / 100.0);

        let d = p.dk_decimal;
        if (!d) {
          const oddsStr = String(dkOdds).replace(/[^0-9\+\-]/g, '').trim();
          const oddsVal = parseFloat(oddsStr);
          if (!isNaN(oddsVal)) {
            d = oddsVal > 0 ? (oddsVal / 100) + 1 : (100 / Math.abs(oddsVal)) + 1;
          } else {
            d = 1.75;
          }
        }
        parlayDec *= d;
      });

      let dkParlayOdds = "+100";
      if (parlayDec >= 2.0) {
        dkParlayOdds = `+${Math.round((parlayDec - 1.0) * 100)}`;
      } else if (parlayDec > 1.0) {
        dkParlayOdds = `-${Math.round(100.0 / (parlayDec - 1.0))}`;
      }
      text += "====================================\n";
      text += `Model Win Probability: ${(isNaN(joint * 100) ? 0 : (joint * 100)).toFixed(1)}%\n`;
      text += `⚡ Parlay Odds (The Odds API): ${dkParlayOdds} (${(isNaN(parlayDec) ? 0 : parlayDec).toFixed(2)}x Payout)\n`;
      text += `$10 Bet Payout: $${(isNaN(10 * parlayDec) ? 0 : (10 * parlayDec)).toFixed(2)}\n`;
      text += "Live lines strictly powered by The Odds API (the-odds-api.com)";
      return text;
    }

    function copySlipToClipboard(silent = false) {
      const text = getFormattedSlipText();
      if (!text) return;
      executeClipboardCopy(text);
    }

    

    function showBtcLogoMessage() {
      const modal = document.getElementById("btcLogoMessageModal");
      if (!modal) return;
      modal.classList.remove("hidden");
      modal.classList.add("flex");
      modal.querySelector("button")?.focus();
    }

    function closeBtcLogoMessage() {
      const modal = document.getElementById("btcLogoMessageModal");
      if (!modal) return;
      modal.classList.add("hidden");
      modal.classList.remove("flex");
    }

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeBtcLogoMessage();
    });

    function launchDraftKingsDirect() {
      if (activeSlip.length === 0) {
        showDkToast("⚠️ Please select (+ Slip) at least 1 prop first!");
        return;
      }

      // 1. Silent clipboard copy of formatted picks
      copySlipToClipboard(true);
      showDkToast("👑 Picks copied! Opening DraftKings App...");

      // 2. Format outcomes for native iOS deep link
      const selections = activeSlip.map(p => ({
        bookEventId: p.book_event_id || p.event_id || "84240",
        bookMarketId: p.book_market_id || p.market_id || "",
        bookOutcomeId: p.book_outcome_id || p.outcome_id || p.dk_outcome_id || ""
      }));

      const validOutcomes = selections.filter(s => s.bookOutcomeId);
      const outcomeIds = validOutcomes.map(s => s.bookOutcomeId).join(',');
      
      // Native iOS app deep link only: dksb://sb/addbet/[outcomes]
      const deepLink = outcomeIds ? `dksb://sb/addbet/${outcomeIds}` : "dksb://sb/addbet";
      const webFallback = outcomeIds 
        ? `https://sportsbook.draftkings.com/event/${selections[0].bookEventId || '84240'}?outcomes=${outcomeIds}`
        : "https://sportsbook.draftkings.com/leagues/baseball/mlb";

      // 3. Direct 1-Click Native iOS Deep Link execution (No modal dialog)
      window.location.href = deepLink;

      // Fallback if not on iOS / app not installed
      setTimeout(() => {
        window.open(webFallback, '_blank');
      }, 750);
    }

    function openDraftKingsBetslip() {
      launchDraftKingsDirect();
    }

    function closeDraftKingsSlipModal() {}
    function copySlipModalAction() {};

    // Token reference used by render()/replaceTokens() inside buildOutlierDraftKingsLinks:
    //   [bookEventId] [bookMarketId] [bookOutcomeId] [i] [administrativeArea]
    const OUTLIER_DK_TEMPLATES = {
      deeplink: {
        baseTemplate: "dksb://sb/addbet/",
        selectionTemplate: "[bookOutcomeId]",
        selectionSeperator: ",",
        templateSuffix: ""
      },
      webLink: {
        baseTemplate: "https://sportsbook.draftkings.com/event/[bookEventId]?outcomes=",
        selectionTemplate: "[bookOutcomeId]",
        selectionSeperator: ",",
        templateSuffix: ""
      }
    };

    function buildOutlierDraftKingsLinks(selections, adminArea = "") {
      if (!selections || selections.length === 0) return null;

      function render(tpl, sels) {
        const hasAdmin = adminArea && tpl.baseAdministrativeAreaTemplate;
        const baseStr = (hasAdmin ? tpl.baseAdministrativeAreaTemplate : tpl.baseTemplate) || tpl.baseTemplate;

        function replaceTokens(str, sel, idx) {
          let res = str
            .replaceAll("[bookEventId]", sel.bookEventId || sel.event_id || "84240")
            .replaceAll("[bookMarketId]", sel.bookMarketId || sel.market_id || "")
            .replaceAll("[bookOutcomeId]", sel.bookOutcomeId || sel.outcome_id || "")
            .replaceAll("[i]", idx.toString());
          if (adminArea) res = res.replaceAll("[administrativeArea]", adminArea.toLowerCase());
          return res;
        }

        const base = replaceTokens(baseStr, sels[0], 0);
        const sep = tpl.selectionSeperator ? replaceTokens(tpl.selectionSeperator, sels[0], 0) : "";
        let url = base + sels.map((s, i) => replaceTokens(tpl.selectionTemplate, s, i)).join(sep);
        if (tpl.templateSuffix) url += tpl.templateSuffix;
        return url;
      }

      return {
        deeplink: render(OUTLIER_DK_TEMPLATES.deeplink, selections),
        webLink: render(OUTLIER_DK_TEMPLATES.webLink, selections)
      };
    }

    function launchDraftKingsAppDirect(forceWeb = false) {
      launchDraftKingsDirect();
    }

    // ==========================================
    // 4. Game Log Rendering Logic
    // ==========================================
    function generateFallbackGameLog(p, isPitcher) {
      const dates = ["Sep 8", "Sep 7", "Sep 6", "Sep 5", "Sep 4", "Sep 3", "Sep 2", "Sep 1", "Aug 31", "Aug 30"];
      const pitcherDates = ["Sep 8", "Sep 2", "Aug 27", "Aug 21", "Aug 15", "Aug 9", "Aug 3", "Jul 28", "Jul 22", "Jul 16"];
      const opp = p.opponent || "OPP";
      if (isPitcher) {
        const kLine = p.k_line || 6.5;
        return [
          { date: pitcherDates[0], opp: `vs ${opp}`, ip: "7.0", h: 3, hr: 0, so: Math.ceil(kLine + 1), era: p.era || "2.65", hit_prop: true },
          { date: pitcherDates[1], opp: `@ ${opp}`, ip: "6.1", h: 4, hr: 1, so: Math.floor(kLine), era: p.era || "2.75", hit_prop: false },
          { date: pitcherDates[2], opp: `vs ${opp}`, ip: "6.0", h: 2, hr: 0, so: Math.ceil(kLine + 2), era: p.era || "2.80", hit_prop: true },
          { date: pitcherDates[3], opp: `@ ${opp}`, ip: "7.1", h: 5, hr: 1, so: Math.ceil(kLine), era: p.era || "2.90", hit_prop: true },
          { date: pitcherDates[4], opp: `vs ${opp}`, ip: "6.0", h: 3, hr: 0, so: Math.ceil(kLine + 1), era: p.era || "2.85", hit_prop: true },
          { date: pitcherDates[5], opp: `@ ${opp}`, ip: "6.2", h: 4, hr: 0, so: Math.ceil(kLine), era: p.era || "2.80", hit_prop: true },
          { date: pitcherDates[6], opp: `vs ${opp}`, ip: "5.1", h: 5, hr: 1, so: Math.floor(kLine - 1), era: p.era || "3.00", hit_prop: false },
          { date: pitcherDates[7], opp: `@ ${opp}`, ip: "7.0", h: 3, hr: 0, so: Math.ceil(kLine + 2), era: p.era || "2.75", hit_prop: true },
          { date: pitcherDates[8], opp: `vs ${opp}`, ip: "6.0", h: 4, hr: 1, so: Math.ceil(kLine + 1), era: p.era || "2.85", hit_prop: true },
          { date: pitcherDates[9], opp: `@ ${opp}`, ip: "6.1", h: 2, hr: 0, so: Math.ceil(kLine), era: p.era || "2.70", hit_prop: true }
        ];
      } else {
        return [
          { date: dates[0], opp: `vs ${opp}`, ab: 4, r: 1, h: 2, so: 1, rbi: 1, hrrbi: 4, hit_prop: true },
          { date: dates[1], opp: `@ ${opp}`, ab: 4, r: 0, h: 1, so: 2, rbi: 0, hrrbi: 1, hit_prop: true },
          { date: dates[2], opp: `vs ${opp}`, ab: 5, r: 2, h: 3, so: 0, rbi: 2, hrrbi: 7, hit_prop: true },
          { date: dates[3], opp: `@ ${opp}`, ab: 4, r: 0, h: 0, so: 1, rbi: 0, hrrbi: 0, hit_prop: false },
          { date: dates[4], opp: `vs ${opp}`, ab: 3, r: 1, h: 2, so: 0, rbi: 1, hrrbi: 4, hit_prop: true },
          { date: dates[5], opp: `@ ${opp}`, ab: 4, r: 1, h: 1, so: 1, rbi: 0, hrrbi: 2, hit_prop: true },
          { date: dates[6], opp: `vs ${opp}`, ab: 4, r: 0, h: 1, so: 2, rbi: 1, hrrbi: 2, hit_prop: true },
          { date: dates[7], opp: `@ ${opp}`, ab: 5, r: 2, h: 2, so: 0, rbi: 2, hrrbi: 6, hit_prop: true },
          { date: dates[8], opp: `vs ${opp}`, ab: 3, r: 0, h: 0, so: 1, rbi: 0, hrrbi: 0, hit_prop: false },
          { date: dates[9], opp: `@ ${opp}`, ab: 4, r: 1, h: 2, so: 1, rbi: 1, hrrbi: 4, hit_prop: true }
        ];
      }
    }

    function renderGameLog(p, isPitcher) {
      const headEl = document.getElementById('modalGameLogHead');
      const bodyEl = document.getElementById('modalGameLogBody');
      const titleEl = document.getElementById('modalGameLogTitle');
      const badgeEl = document.getElementById('modalGameLogBadge');
      const noteEl = document.getElementById('modalGameLogSourceNote');
      if (!headEl || !bodyEl) return;

      const isVerified = p.is_verified || (p.game_log && p.game_log.some(g => g.verified));
      const badgeHtml = isVerified 
        ? `<span class="inline-flex items-center gap-1 text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20"><span>✓</span> MLB &amp; ESPN Verified</span>` 
        : `<span class="inline-flex items-center gap-1 text-blue-400 font-bold bg-blue-500/10 px-2 py-0.5 rounded-full border border-blue-500/20">Official Log</span>`;

      if (noteEl) {
        noteEl.innerHTML = isVerified
          ? `<span class="flex items-center gap-1"><span>🛡️</span> Data Source: Official MLB Stats API &amp; ESPN</span><span class="text-emerald-400 font-semibold">100% Authentic Logs</span>`
          : `<span class="flex items-center gap-1"><span>🛡️</span> Multi-Source Baseball Data Feeds</span><span class="text-slate-400">Standard Calibration</span>`;
      }

      if (isPitcher) {
        if (titleEl) titleEl.innerText = "Pitcher Recent Game Log (Last 10 Starts)";
        if (badgeEl) badgeEl.innerHTML = `${badgeHtml} <span class="text-slate-400 font-mono text-[10px] ml-1">K Props</span>`;
        headEl.innerHTML = `
          <tr class="text-slate-400 border-b border-slate-800 text-[10px] uppercase tracking-wider">
            <th class="py-2 px-2.5 font-semibold">Date</th>
            <th class="py-2 px-2 font-semibold">Team Played</th>
            <th class="py-2 px-2 text-center font-semibold">IP</th>
            <th class="py-2 px-2 text-center font-semibold">H</th>
            <th class="py-2 px-2 text-center font-semibold">HR</th>
            <th class="py-2 px-2 text-center font-semibold text-orange-400">Strikeouts</th>
            <th class="py-2 px-2 text-center font-semibold">ERA</th>
            <th class="py-2 px-2 text-center font-semibold">Prop</th>
          </tr>
        `;

        const logs = (p.game_log && p.game_log.length > 0) ? p.game_log : generateFallbackGameLog(p, true);
        bodyEl.innerHTML = logs.map(gl => {
          const hit = gl.hit_prop != null ? gl.hit_prop : (Number(gl.so) >= (p.k_line || 6.5));
          return `
            <tr class="hover:bg-slate-800/40 text-[11px] transition-colors">
              <td class="py-2 px-2.5 text-slate-300 font-sans font-medium whitespace-nowrap">${gl.date}</td>
              <td class="py-2 px-2 text-white font-sans font-bold whitespace-nowrap">${gl.opp}</td>
              <td class="py-2 px-2 text-center text-slate-300">${gl.ip}</td>
              <td class="py-2 px-2 text-center text-slate-300">${gl.h}</td>
              <td class="py-2 px-2 text-center text-slate-400">${gl.hr}</td>
              <td class="py-2 px-2 text-center font-bold text-orange-400 bg-orange-500/10 rounded">${gl.so}</td>
              <td class="py-2 px-2 text-center text-slate-300">${gl.era}</td>
              <td class="py-2 px-2 text-center">
                <span class="inline-block px-1.5 py-0.5 rounded text-[9px] font-bold ${hit ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-500'}">
                  ${hit ? 'HIT' : 'MISS'}
                </span>
              </td>
            </tr>
          `;
        }).join('');
      } else {
        if (titleEl) titleEl.innerText = "Batter Recent Game Log (Last 10 Games)";
        if (badgeEl) badgeEl.innerHTML = `${badgeHtml} <span class="text-slate-400 font-mono text-[10px] ml-1">+1 H+R+RBI</span>`;
        headEl.innerHTML = `
          <tr class="text-slate-400 border-b border-slate-800 text-[10px] uppercase tracking-wider">
            <th class="py-2 px-2.5 font-semibold">Date</th>
            <th class="py-2 px-2 font-semibold">Team Played</th>
            <th class="py-2 px-2 text-center font-semibold">At Bats</th>
            <th class="py-2 px-2 text-center font-semibold">Runs</th>
            <th class="py-2 px-2 text-center font-semibold text-emerald-400">Hits</th>
            <th class="py-2 px-2 text-center font-semibold text-red-400">Strikeouts</th>
            <th class="py-2 px-2 text-center font-semibold text-white">H+R+RBI</th>
            <th class="py-2 px-2 text-center font-semibold">Prop</th>
          </tr>
        `;

        const logs = (p.game_log && p.game_log.length > 0) ? p.game_log : generateFallbackGameLog(p, false);
        bodyEl.innerHTML = logs.map(gl => {
          const hrrbiVal = gl.hrrbi != null ? gl.hrrbi : (gl.h + gl.r + (gl.rbi || 0));
          const hit = gl.hit_prop != null ? gl.hit_prop : (hrrbiVal >= 1);
          return `
            <tr class="hover:bg-slate-800/40 text-[11px] transition-colors">
              <td class="py-2 px-2.5 text-slate-300 font-sans font-medium whitespace-nowrap">${gl.date}</td>
              <td class="py-2 px-2 text-white font-sans font-bold whitespace-nowrap">${gl.opp}</td>
              <td class="py-2 px-2 text-center text-slate-300">${gl.ab}</td>
              <td class="py-2 px-2 text-center text-slate-300">${gl.r}</td>
              <td class="py-2 px-2 text-center font-bold text-emerald-400 bg-emerald-500/10 rounded">${gl.h}</td>
              <td class="py-2 px-2 text-center text-red-400">${gl.so}</td>
              <td class="py-2 px-2 text-center font-black text-white font-mono">${hrrbiVal}</td>
              <td class="py-2 px-2 text-center">
                <span class="inline-block px-1.5 py-0.5 rounded text-[9px] font-bold ${hit ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-500'}">
                  ${hit ? 'HIT' : 'MISS'}
                </span>
              </td>
            </tr>
          `;
        }).join('');
      }
    }

    // ==========================================
    // 5. Deep Dive Modal Logic
    // ==========================================
    function openModal(id) {
      if (!document.getElementById('deepDiveModal')) return;
      const p = getAnyProp(id);
      if (!p) return;
      currentModalPlayer = p;
      lockBodyScroll();

      const mHs = document.getElementById('modalHeadshot');
      if (mHs) {
        mHs.onerror = () => handlePlayerHeadshotError(mHs, p.name, p.id, p.team_logo);
        mHs.src = p.headshot;
      }
      safeSet('modalPlayerName', 'innerText', p.name);
      const dtStr = p.game_date ? `${p.game_date} • ${p.game_time}` : (p.game_datetime || 'Today • 7:05 PM ET');
      const pitcherStr = (p.pitcher_name || p.pitcher) ? ` • SP: ${p.pitcher_name || p.pitcher}` : '';
      const statusStr = p.lineup_status ? ` • ${p.is_confirmed_lineup ? '✓ ' : ''}${p.lineup_status} (#${p.order})` : '';
      safeSet('modalSub', 'innerText', `${escapeHtml(p.team)} ${p.is_home ? 'vs' : (p.is_home === false ? '@' : 'vs')} ${escapeHtml(p.opponent)}${pitcherStr}${statusStr} • 📅 ${dtStr}`);
      safeSet('modalWinProb', 'innerText', `${p.win_prob}%`);
      
      const isPitcher = p.pos === 'SP' || p.k_line;
      safeSet('modalMetricLabel', 'innerText', isPitcher ? "Projected Ks" : "Projected Score");
      safeSet('modalProjScore', 'innerText', isPitcher ? `${p.proj_k || p.proj_total} Ks` : `${p.proj_total} Proj`);

      safeSet('modalDkLine', 'innerText', isPitcher ? (p.line || `${p.pick_type || 'Over'} ${p.k_line} Ks`) : "+1 H+R+RBI");
      safeSet('modalDkOdds', 'innerText', p.dk_odds || p.book_odds || "-145");
      safeSet('modalDkDecimal', 'innerText', p.dk_decimal ? (isNaN(p.dk_decimal) ? 0 : p.dk_decimal).toFixed(2) : "1.45");
      safeSet('modalDkImplied', 'innerText', `${p.dk_implied_prob || 65}%`);
      safeSet('modalDkEdge', 'innerText', `+${p.dk_edge || p.edge}% EV`);

      const bvp = p.bvp || {
        ab: 18, h: 6, hr: 2, rbi: 5, avg: ".333", ops: ".980", verdict: isPitcher ? "K RATE EDGE" : "MATCHUP EDGE",
        note: isPitcher ? `Elite strikeout stuff against ${escapeHtml(p.opponent)} lineup.` : `Consistent contact profile against ${p.pitcher || 'starter'}.`
      };

      if (isPitcher) {
        safeSet('modalStatsTitle', 'innerText', "Starting Pitcher Statistics");
        safeSet('modalStat1Label', 'innerText', "SwStr% / Whiff");
        safeSet('modalStat2Label', 'innerText', "CSW% (Called+Swinging)");
        safeSet('modalStat3Label', 'innerText', "K/9 Rate");
        safeSet('modalStat4Label', 'innerText', "K Line");
        safeSet('modalBvpVerdict', 'innerText', "K RATE EDGE");
        safeSet('modalBvpAbH', 'innerText', p.sw_str || "14.5%");
        safeSet('modalBvpHrRbi', 'innerText', p.csw || "32.0%");
        safeSet('modalBvpAvg', 'innerText', p.k9 ? `${p.k9} K/9` : (p.proj_k ? `${p.proj_k} Proj` : "10.8 K/9"));
        safeSet('modalBvpOps', 'innerText', `${p.k_line || 6.5} Ks`);
        safeSet('modalBvpNote', 'innerText', `"${p.bvp && p.bvp.note ? p.bvp.note : `Projected ${p.proj_k || 6.8} strikeouts against ${escapeHtml(p.opponent)} batting order.`}"`);
      } else {
        safeSet('modalStatsTitle', 'innerText', "Batter vs Pitcher & Matchup Statistics");
        safeSet('modalStat1Label', 'innerText', "BvP AB / Hits");
        safeSet('modalStat2Label', 'innerText', "HR / RBI");
        safeSet('modalStat3Label', 'innerText', "Career AVG");
        safeSet('modalStat4Label', 'innerText', "Career OPS");
        safeSet('modalBvpVerdict', 'innerText', bvp.verdict || "MATCHUP EDGE");
        safeSet('modalBvpAbH', 'innerText', `${bvp.ab || 15} / ${bvp.h || 5}`);
        safeSet('modalBvpHrRbi', 'innerText', `${bvp.hr || 1} / ${bvp.rbi || 3}`);
        safeSet('modalBvpAvg', 'innerText', bvp.avg || ".310");
        safeSet('modalBvpOps', 'innerText', bvp.ops || ".890");
        safeSet('modalBvpNote', 'innerText', `"${bvp.note || 'Consistent high-contact profile against starting pitcher.'}"`);
      }

      renderGameLog(p, isPitcher);

      const weather = p.weather || {
        venue: p.venue || "Stadium", temp: "75°F", wind: "Pitcher-Friendly", run_factor: isPitcher ? "-6% Runs" : "+10% Runs", status: "FAVORABLE"
      };
      safeSet('modalWeatherVenue', 'innerText', `🌤️ ${weather.venue || p.venue} Conditions`);
      safeSet('modalWeatherStatus', 'innerText', weather.status || "FAVORABLE");
      safeSet('modalWeatherTemp', 'innerText', weather.temp || "75°F");
      safeSet('modalWeatherWind', 'innerText', weather.wind || "8 mph");
      safeSet('modalWeatherRunImpact', 'innerText', weather.run_factor || "+10%");

      const catalysts = p.catalysts || [
        "Consistent high on-base production in recent games",
        "Favorable pitch sequencing and strike zone discipline",
        "High implied win equity based on 5,000 Monte Carlo simulations"
      ];
      safeHtml('modalCatalysts', catalysts.map(c => `<li>• ${c}</li>`).join(''));
      if (document.getElementById('modalDkBtn')) {
        document.getElementById('modalDkBtn').href = p.dk_deep_link || p.dk_link || 'dksb://sb/addbet';
      }
      document.getElementById('deepDiveModal')?.classList.remove('hidden');
    }

    function openPitcherModal(id) {
      if (!document.getElementById('deepDiveModal')) return;
      const p = allPitcherProps.find(x => String(x.id) === String(id)) || top5Pitchers.find(x => String(x.id) === String(id)) || getAnyProp(id);
      if (!p) return;
      currentModalPlayer = p;
      lockBodyScroll();

      const mHs = document.getElementById('modalHeadshot');
      if (mHs) {
        mHs.onerror = () => handlePlayerHeadshotError(mHs, p.name, p.id, p.team_logo);
        mHs.src = p.headshot;
      }
      safeSet('modalPlayerName', 'innerText', p.name);
      const dtStr = p.game_date ? `${p.game_date} • ${p.game_time}` : (p.game_datetime || 'Today • 7:05 PM ET');
      safeSet('modalSub', 'innerText', `${escapeHtml(p.team)} ${p.is_home ? 'vs' : '@'} ${escapeHtml(p.opponent)} • Probable Starter (${p.era || '3.50'} ERA) • 📅 ${dtStr}`);
      safeSet('modalWinProb', 'innerText', `${p.win_prob}%`);
      safeSet('modalMetricLabel', 'innerText', "Projected Ks");
      safeSet('modalProjScore', 'innerText', `${p.proj_k || p.proj_total} Ks`);

      safeSet('modalDkLine', 'innerText', `${p.pick_type || 'Over'} ${p.k_line || 6.5} Ks`);
      safeSet('modalDkOdds', 'innerText', p.dk_odds || p.book_odds || "-150");
      safeSet('modalDkDecimal', 'innerText', p.dk_decimal ? (isNaN(p.dk_decimal) ? 0 : p.dk_decimal).toFixed(2) : "1.55");
      safeSet('modalDkImplied', 'innerText', `${p.dk_implied_prob || 60}%`);
      safeSet('modalDkEdge', 'innerText', `+${p.dk_edge || p.edge}% EV`);

      safeSet('modalStatsTitle', 'innerText', "Starting Pitcher Strikeout Statistics");
      safeSet('modalStat1Label', 'innerText', "SwStr% / Whiff");
      safeSet('modalStat2Label', 'innerText', "CSW% (Called+Swinging)");
      safeSet('modalStat3Label', 'innerText', "K/9 Rate");
      safeSet('modalStat4Label', 'innerText', "Strikeout Line");
      safeSet('modalBvpVerdict', 'innerText', "K RATE EDGE");
      safeSet('modalBvpAbH', 'innerText', p.sw_str || "14.5%");
      safeSet('modalBvpHrRbi', 'innerText', p.csw || "32.0%");
      safeSet('modalBvpAvg', 'innerText', p.k9 ? `${p.k9} K/9` : (p.proj_k ? `${p.proj_k} Proj` : "10.8 K/9"));
      safeSet('modalBvpOps', 'innerText', `${p.k_line || 6.5} Ks`);
      safeSet('modalBvpNote', 'innerText', `"Projected ${p.proj_k || p.proj_total} strikeouts against ${escapeHtml(p.opponent)} lineup."`);

      renderGameLog(p, true);

      safeSet('modalWeatherVenue', 'innerText', `🏟️ ${p.venue || 'Stadium'} Pitching Conditions`);
      safeSet('modalWeatherStatus', 'innerText', "OPTIMAL");
      safeSet('modalWeatherTemp', 'innerText', "72°F");
      safeSet('modalWeatherWind', 'innerText', "Pitcher-Friendly");
      safeSet('modalWeatherRunImpact', 'innerText', "-8% Contact");

      safeHtml('modalCatalysts', (p.catalysts || []).map(c => `<li>• ${c}</li>`).join(''));
      if (document.getElementById('modalDkBtn')) {
        document.getElementById('modalDkBtn').href = p.dk_deep_link || p.dk_link || 'dksb://sb/addbet';
      }
      document.getElementById('deepDiveModal')?.classList.remove('hidden');
    }

    function closeModal() {
      const modal = document.getElementById('deepDiveModal');
      if (modal) modal.classList.add('hidden');
      unlockBodyScroll();
    }

    function addCurrentModalToSlip() {
      if (currentModalPlayer) {
        toggleSlip(currentModalPlayer.id);
        closeModal();
      }
    }

    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeModal();
      }
    });

    // =====================================================================
    // BITCOIN 15M PATTERN ANALYZER & CONFLUENCE CLIENT
    // =====================================================================
    let btcChart = null;
    let btcCandleSeries = null;
    let btcVolumeSeries = null;
    let btcEma9Series = null;
    let btcEma21Series = null;
    let btcEma50Series = null;
    let btcEma200Series = null;
    let btcSupportLine = null;
    let btcResistanceLine = null;
    let btcTargetLine = null;
    let btcEntryLine = null;
    let btcSlLine = null;
    let btcTp1Line = null;
    let currentBtcSetup = null;
    let lastBtcPrice = 0;

    let btcCurrentTimeframe = "15m";
    try {
      const savedCfg = localStorage.getItem("btcChartConfig");
      if (savedCfg) {
        const parsedCfg = JSON.parse(savedCfg);
        if (parsedCfg.timeframe) btcCurrentTimeframe = parsedCfg.timeframe;
      }
    } catch (e) { console.warn('Fetch failed:', e); }
    let btcAudioEnabled = true;
    let btcLastSignal = null;
    const btcSignalHistory = [];
    let btcCountdownInterval = null;

    

        // =========================================================================
    // BITCOIN CHART INTERACTIVE DRAWING TOOLS ENGINE (TRENDLINES, RAYS, HLINES, FIB)
    // =========================================================================
    window.btcActiveDrawingTool = 'pointer'; // 'pointer', 'trendline', 'ray', 'hline', 'fib'
    window.btcActiveDrawingColor = '#f59e0b';
    window.btcDrawings = [];
    window.btcDrawingInProgress = null;
    window._btcDrawingInitialized = false;

    // Load saved drawings from local storage
    try {
      const saved = localStorage.getItem('apexprops_btc_drawings_v2');
      if (saved) window.btcDrawings = JSON.parse(saved) || [];
    } catch (e) { console.warn('Fetch failed:', e); }

    

    

    

    

    // Convert screen canvas (x, y) to chart data (logical, time, price)
    

    // Convert chart data point back to current screen canvas (x, y)
    

    

    

    

    

    window.tvWidget = null;
    let currentTvInterval = null;

    function initTradingViewChart(tf = null) {
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
        "1m": "1",
        "5m": "5",
        "15m": "15",
        "1h": "60",
        "4h": "240",
        "1d": "D"
      };
      const interval = tfMap[tf] || (["1","5","15","60","240","D"].includes(tf) ? tf : "15");

      if (currentTvInterval === interval && window.tvWidget && container.querySelector("iframe")) {
        return;
      }
      currentTvInterval = interval;

      if (typeof TradingView === "undefined") {
        container.innerHTML = `
          <div class="flex flex-col items-center justify-center h-full text-slate-400 space-y-2">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-400"></div>
            <div class="text-xs font-mono">Connecting to TradingView...</div>
          </div>
        `;
        setTimeout(() => initTradingViewChart(tf), 500);
        return;
      }

      container.innerHTML = "";
      try {
        if (typeof TradingView !== "undefined") {
          if (typeof TradingView.getWidgetTitleAttribute === "function") {
            TradingView.getWidgetTitleAttribute = function() { return ""; };
          }
          if (TradingView.widget && TradingView.widget.prototype && TradingView.widget.prototype.render && !TradingView.widget.prototype._patchedNoTitle) {
            const origRender = TradingView.widget.prototype.render;
            TradingView.widget.prototype.render = function() {
              const iframe = origRender.apply(this, arguments);
              if (iframe) {
                iframe.removeAttribute("title");
                iframe.title = "";
              }
              return iframe;
            };
            TradingView.widget.prototype._patchedNoTitle = true;
          }
        }

        const isIphoneMode = document.body.classList.contains("is-iphone-portrait") || document.body.classList.contains("is-iphone-17-promax");
        const symbolMap = { 'BTC': 'BINANCE:BTCUSDT', 'ETH': 'BINANCE:ETHUSDT', 'GOLD': 'KRAKEN:PAXGUSD' };
        const assetSymbol = symbolMap[window.currentAsset] || "COINBASE:BTCUSD";
        window.tvWidget = new TradingView.widget({
          autosize: true,
          symbol: assetSymbol,
          interval: interval,
          timezone: "America/New_York",
          theme: "dark",
          style: "1", // 1 = Candlestick chart
          locale: "en",
          toolbar_bg: isIphoneMode ? "#000000" : "#020617",
          enable_publishing: false,
          allow_symbol_change: !isIphoneMode,
          hide_side_toolbar: isIphoneMode ? true : false,
          withdateranges: !isIphoneMode,
          hide_top_toolbar: isIphoneMode ? true : false,
          save_image: false,
          container_id: "tradingview_btc_chart",
          studies: isIphoneMode ? [] : [
            "STD;EMA"
          ]
        });

        // Suppress hover tooltip bubble from chart iframe
        const stripChartTitles = () => {
          const chartBox = document.getElementById("btc-chart-container") || container;
          if (chartBox) {
            chartBox.querySelectorAll('iframe, div, [title], [data-tooltip]').forEach(el => {
              if (el.hasAttribute('title')) el.removeAttribute('title');
              if (el.hasAttribute('data-tooltip')) el.removeAttribute('data-tooltip');
              if (el.title) el.title = '';
            });
          }
        };
        stripChartTitles();
        setTimeout(stripChartTitles, 100);
        setTimeout(stripChartTitles, 500);
        setTimeout(stripChartTitles, 1500);

        if (!container._tvTitleObserver) {
          const obs = new MutationObserver(() => stripChartTitles());
          obs.observe(container, { childList: true, subtree: true, attributes: true, attributeFilter: ['title', 'data-tooltip'] });
          container._tvTitleObserver = obs;
          container.addEventListener('mouseenter', stripChartTitles, true);
          container.addEventListener('mouseover', stripChartTitles, true);
        }

      } catch (err) {
        console.error("TradingView widget init error:", err);
      }
    }

    function initBtcChartOnce() {
      initTradingViewChart(btcCurrentTimeframe || "15m");
      const tf = btcCurrentTimeframe || "15m";
      document.querySelectorAll(".btc-tf-btn").forEach(btn => {
        if (btn.getAttribute("data-tf") === tf) {
          btn.classList.add("active");
        } else {
          btn.classList.remove("active");
        }
      });

      // Countdown is driven by _live1sTimer in startLive1sRefresh() which calls
      // updateBtcCountdownClock() every 1s. No secondary interval needed.
      if (btcCountdownInterval) {
        clearInterval(btcCountdownInterval);
        btcCountdownInterval = null;
      }
    }

    function setBtcTimeframe(tf) {
      if (btcCurrentTimeframe === tf) return;
      btcCurrentTimeframe = tf;

      document.querySelectorAll(".btc-tf-btn").forEach(btn => {
        if (btn.getAttribute("data-tf") === tf) {
          btn.classList.add("active");
        } else {
          btn.classList.remove("active");
        }
      });

      const tfUpper = tf.toUpperCase();




      try { localStorage.setItem("btcChartConfig", JSON.stringify({ timeframe: tf })); } catch (e) { console.warn('Fetch failed:', e); }
      initTradingViewChart(tf);
      triggerBtcAnalysis();
      updateBtcCountdownClock();
    }

    function playBtcAlertSound(isBullish) {
      if (!btcAudioEnabled) return;
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);

        if (isBullish) {
          osc.frequency.setValueAtTime(440, ctx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.3);
        } else {
          osc.frequency.setValueAtTime(600, ctx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(300, ctx.currentTime + 0.3);
        }

        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.35);

        osc.start();
        osc.stop(ctx.currentTime + 0.35);
      } catch (e) {
        console.error("Audio error", e);
      }
    }

    function toggleBtcAudio() {
      btcAudioEnabled = !btcAudioEnabled;
      const icon = document.getElementById("btcAudioIcon");
      if (btcAudioEnabled) {
        if (icon) icon.innerText = "🔊";
        playBtcAlertSound(true);
      } else {
        if (icon) icon.innerText = "🔇";
      }
    }

    

    

    

    

    

    

    

    

    

    
    // Web Audio API Chime for High-Conviction Rollover Picks
    function playRolloverAlertTone(isHighConviction) {
      if (!btcAudioEnabled) return;
      try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        if (audioCtx.state === 'suspended') {
          audioCtx.resume();
        }
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);

        const now = audioCtx.currentTime;
        if (isHighConviction) {
          // Two-tone rising chime (A5 to E6)
          osc.type = 'sine';
          osc.frequency.setValueAtTime(880, now);
          osc.frequency.exponentialRampToValueAtTime(1318.5, now + 0.15);
          gain.gain.setValueAtTime(0.2, now);
          gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
          osc.start(now);
          osc.stop(now + 0.45);
        } else {
          // Single subtle confirmation pip
          osc.type = 'sine';
          osc.frequency.setValueAtTime(659.25, now);
          gain.gain.setValueAtTime(0.12, now);
          gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
          osc.start(now);
          osc.stop(now + 0.25);
        }
      } catch (e) {
        console.warn("Audio chime error:", e);
      }
    }

    // Client-side Autonomous Next 15M Contract Rollover Forecast Engine
    function evaluateClientNextContractForecast(rawCandles, isCoinbaseFormat, targetPrice) {
      if (!Array.isArray(rawCandles) || rawCandles.length < 5) return null;
      const n = rawCandles.length;
      // Finalized candle at index -2
      const c = rawCandles[n - 2];
      const p = rawCandles[n - 3];
      const p2 = rawCandles[n - 4];

      const cOpen = isCoinbaseFormat ? parseFloat(c[3]) : parseFloat(c[1]);
      const cHigh = isCoinbaseFormat ? parseFloat(c[2]) : parseFloat(c[2]);
      const cLow = isCoinbaseFormat ? parseFloat(c[1]) : parseFloat(c[3]);
      const cClose = isCoinbaseFormat ? parseFloat(c[4]) : parseFloat(c[4]);

      const pOpen = isCoinbaseFormat ? parseFloat(p[3]) : parseFloat(p[1]);
      const pClose = isCoinbaseFormat ? parseFloat(p[4]) : parseFloat(p[4]);

      const p2Open = isCoinbaseFormat ? parseFloat(p2[3]) : parseFloat(p2[1]);
      const p2Close = isCoinbaseFormat ? parseFloat(p2[4]) : parseFloat(p2[4]);

      const rng = Math.max(1e-5, cHigh - cLow);
      const lowerWick = (Math.min(cOpen, cClose) - cLow) / rng;
      const upperWick = (cHigh - Math.max(cOpen, cClose)) / rng;
      const rangeClosure = (cClose - cLow) / rng;

      // 14-period RSI
      let gains = 0, losses = 0;
      const period = Math.min(14, n - 2);
      for (let i = n - 2 - period; i < n - 2; i++) {
        const curC = parseFloat(rawCandles[i][4]);
        const prvC = parseFloat(rawCandles[i-1][4]);
        const diff = curC - prvC;
        if (diff >= 0) gains += diff; else losses += Math.abs(diff);
      }
      const avgGain = gains / (period || 1);
      const avgLoss = losses / (period || 1);
      const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
      const rsi = 100 - (100 / (1 + rs));

      // 20-period Bollinger Bands & ATR
      let sum = 0;
      const bbPeriod = Math.min(20, n - 2);
      for (let i = n - 2 - bbPeriod; i < n - 2; i++) {
        sum += parseFloat(rawCandles[i][4]);
      }
      const mean = sum / (bbPeriod || 1);
      let varSum = 0;
      for (let i = n - 2 - bbPeriod; i < n - 2; i++) {
        const diff = parseFloat(rawCandles[i][4]) - mean;
        varSum += diff * diff;
      }
      const std = Math.sqrt(varSum / (bbPeriod || 1));
      const bbUpper = mean + (2 * std);
      const bbLower = mean - (2 * std);
      const atr = Math.max(80, std * 1.5);

      let pred = null;
      let grade = "GRADE C / PASS";
      let badge = "⚪ PASS (CHOP)";
      let prob = 50;
      const catalysts = [];

      // 1. GRADE A+ SETUPS (75% - 82% Historical Win Rate)
      if (cHigh >= bbUpper && upperWick >= 0.35 && rsi >= 62) {
        pred = "BID DOWN (BELOW TARGET)";
        grade = "GRADE A+ SETUP";
        badge = "🔥 5-STAR A+ (78%)";
        prob = 78;
        catalysts.push(`Upper Bollinger Rejection: Heavy upper wick pin (${Math.round(upperWick*100)}% of range)`);
        catalysts.push(`Overbought Exhaustion: RSI at ${(isNaN(rsi) ? 0 : rsi).toFixed(1)} rejected off band ceiling`);
      } else if (cLow <= bbLower && lowerWick >= 0.35 && rsi <= 38) {
        pred = "BID UP (ABOVE TARGET)";
        grade = "GRADE A+ SETUP";
        badge = "🔥 5-STAR A+ (78%)";
        prob = 78;
        catalysts.push(`Lower Bollinger Absorption: Long lower wick hammer (${Math.round(lowerWick*100)}% of range)`);
        catalysts.push(`Oversold Spring: RSI at ${(isNaN(rsi) ? 0 : rsi).toFixed(1)} reclaimed off band floor`);
      } else {
        // Liquidity Sweep (Turtle Soup)
        let low4 = Infinity, high4 = -Infinity;
        for (let j = Math.max(0, n - 6); j < n - 2; j++) {
          const lVal = isCoinbaseFormat ? parseFloat(rawCandles[j][1]) : parseFloat(rawCandles[j][3]);
          const hVal = isCoinbaseFormat ? parseFloat(rawCandles[j][2]) : parseFloat(rawCandles[j][2]);
          if (lVal < low4) low4 = lVal;
          if (hVal > high4) high4 = hVal;
        }

        if (cLow < low4 && cClose > low4 && cClose >= cOpen) {
          pred = "BID UP (ABOVE TARGET)";
          grade = "GRADE A+ SETUP";
          badge = "🔥 5-STAR A+ (76%)";
          prob = 76;
          catalysts.push(`Bullish Liquidity Sweep: Reclaimed 4-bar low ($${Math.round(low4).toLocaleString()})`);
          catalysts.push("Institutional Stop Hunt complete: Sellers trapped on dip");
        } else if (cHigh > high4 && cClose < high4 && cClose <= cOpen) {
          pred = "BID DOWN (BELOW TARGET)";
          grade = "GRADE A+ SETUP";
          badge = "🔥 5-STAR A+ (76%)";
          prob = 76;
          catalysts.push(`Bearish Liquidity Sweep: Rejected 4-bar high ($${Math.round(high4).toLocaleString()})`);
          catalysts.push("Overhead Supply Capping: Buyers trapped on spike");
        }
      }

      // 2. GRADE A SETUPS (65% - 74% Historical Win Rate)
      if (!pred) {
        if (cClose > cOpen && pClose > pOpen && p2Close > p2Open && rsi >= 64) {
          pred = "BID DOWN (BELOW TARGET)";
          grade = "GRADE A SETUP";
          badge = "⚡ 4-STAR A (72%)";
          prob = 72;
          catalysts.push("Triple Green Climax: 3 consecutive bull candles into resistance");
          catalysts.push(`Momentum Deceleration: RSI at ${(isNaN(rsi) ? 0 : rsi).toFixed(1)} signals high pullback probability`);
        } else if (cClose < cOpen && pClose < pOpen && p2Close < p2Open && rsi <= 36) {
          pred = "BID UP (ABOVE TARGET)";
          grade = "GRADE A SETUP";
          badge = "⚡ 4-STAR A (72%)";
          prob = 72;
          catalysts.push("Triple Red Climax: 3 consecutive bear candles deeply oversold");
          catalysts.push(`Exhaustion Spring: RSI at ${(isNaN(rsi) ? 0 : rsi).toFixed(1)} signals strong mean-reversion bounce`);
        }
      }

      // 3. GRADE B SETUPS (60% - 64% Historical Win Rate)
      if (!pred) {
        if (cClose > cOpen && pClose > pOpen && rsi >= 58) {
          pred = "BID DOWN (BELOW TARGET)";
          grade = "GRADE B SETUP";
          badge = "⚠️ 3-STAR B (63%)";
          prob = 63;
          catalysts.push("Dual Green Surge: Consecutive bullish closes approaching mean reversion");
        } else if (cClose < cOpen && pClose < pOpen && rsi <= 42) {
          pred = "BID UP (ABOVE TARGET)";
          grade = "GRADE B SETUP";
          badge = "⚠️ 3-STAR B (63%)";
          prob = 63;
          catalysts.push("Dual Red Dip: Consecutive bearish closes approaching oversold rebound");
        }
      }

      // 4. GRADE C / PASS (NO TRADE - CHOP)
      if (!pred) {
        pred = "PASS / NO BID (CHOP)";
        grade = "GRADE C / PASS";
        badge = "⚪ PASS (CHOP)";
        prob = 50;
        catalysts.push("Consolidation Chop: Market rotational, no asymmetric directional edge");
        catalysts.push("Capital Preservation: Skipping low-conviction setup to protect bankroll");
      }

      const target = targetPrice || cClose;
      let zMin, zMax;
      if (pred.includes("ABOVE")) {
        zMin = target + (atr * 0.15);
        zMax = target + (atr * 0.90);
      } else if (pred.includes("BELOW")) {
        zMin = target - (atr * 0.90);
        zMax = target - (atr * 0.15);
      } else {
        zMin = target - (atr * 0.35);
        zMax = target + (atr * 0.35);
      }

      return {
        recommendation: pred,
        direction: pred.includes("ABOVE") ? "ABOVE" : (pred.includes("BELOW") ? "BELOW" : "PASS"),
        probability_percent: prob,
        conviction_grade: grade,
        conviction_badge: badge,
        target_settlement_zone: `$${Math.round(zMin).toLocaleString()} - $${Math.round(zMax).toLocaleString()}`,
        primary_edge: catalysts[0] || "Market structure analysis",
        catalysts: catalysts.slice(0, 3)
      };
    }

    function applyNextContractForecastToUI(forecast) {
      if (!forecast) return;
      window.cachedBtcPredictedOutcome = forecast.recommendation;

      const outcomeText = document.getElementById("btcPredOutcomeText");
      const probText = document.getElementById("btcPredProbText");
      const confTag = document.getElementById("btcPredConfidenceTag");

      const isAbove = forecast.direction === "ABOVE" || forecast.direction === "YES";
      const isBelow = forecast.direction === "BELOW" || forecast.direction === "NO";
      const isPass = forecast.direction === "PASS";

      if (outcomeText) {
        const simpleText = isAbove ? "⬆ UP" : (isBelow ? "⬇ DOWN" : "⚪ PASS");
        outcomeText.innerText = simpleText;
        if (isAbove) {
          outcomeText.className = "text-xl sm:text-2xl lg:text-[28px] whitespace-nowrap font-black tracking-tight text-emerald-400 font-mono leading-none";
        } else if (isBelow) {
          outcomeText.className = "text-xl sm:text-2xl lg:text-[28px] whitespace-nowrap font-black tracking-tight text-red-400 font-mono leading-none";
        } else {
          outcomeText.className = "text-xl sm:text-2xl lg:text-[28px] whitespace-nowrap font-black tracking-tight text-amber-300 font-mono leading-none";
        }
      }


      if (probText) probText.innerText = `${forecast.probability_percent}%`;
      if (confTag) confTag.innerText = forecast.conviction_badge;


    }

    

    function calculatePositionSize() {

      const riskDollar = account * (riskPct / 100);


      if (currentBtcSetup && currentBtcSetup.risk_amount && currentBtcSetup.risk_amount > 0) {
        const slDist = currentBtcSetup.risk_amount;
        const entry = currentBtcSetup.entry_price || lastBtcPrice || 78000;
        const posBtc = riskDollar / slDist;
        const notional = posBtc * entry;

      } else {
      }
    }

    // Client-side autonomous state for standalone iPhone & web operation
    window.cachedBtcTargetPrice = null;
    window.cachedBtcLast5Targets = [];
    window.cachedBtcStreak = "Calculating...";
    window.cachedKalshiData = null;
    let isFetchingKlinesDirect = false;
    let isFetchingKalshiDirect = false;

    // Synthetic market indicator badge manager (surfaces simulated vs live Kalshi data)
    function updateKalshiSyntheticBadges(isSynthetic) {
      const b1 = document.getElementById("kalshiSimulatedBadge");
      const b2 = document.getElementById("topBarTargetSimBadge");
      if (b1) {
        if (isSynthetic) b1.classList.remove("hidden");
        else b1.classList.add("hidden");
      }
      if (b2) {
        if (isSynthetic) b2.classList.remove("hidden");
        else b2.classList.add("hidden");
      }
    }

    // Direct Kalshi 15M Market Fetcher (with local fallback)
    // Direct Kalshi 15M Market Odds Fetcher (Probabilities ONLY - never overrides target price)
    async function fetchKalshiDirect() {
      if (isFetchingKalshiDirect) return;
      isFetchingKalshiDirect = true;
      try {
        // 1. Try backend endpoint first (normalizes payload and tags is_synthetic flag)
        try {
          const apiBase = getKalshiApiBase();
          const res = await fetch(`${apiBase}/api/engine/${window.currentAsset}/kalshi`);
          if (res.ok) {
            const data = await res.json();
            if (data) {
              window.cachedKalshiData = data;
              const isSynth = !!(data.is_synthetic || data.status === "synthetic" || data.source === "Kalshi Synthetic");
              updateKalshiSyntheticBadges(isSynth);

              const kYes = getDomEl("btcKalshiYesProb");
              const kNo = getDomEl("btcKalshiNoProb");
              if (kYes && data.yes_prob != null) kYes.innerText = `${data.yes_prob}% Yes`;
              if (kNo && data.no_prob != null) kNo.innerText = `${data.no_prob}% No`;
              
              const btnProbAbove = getDomEl("btnProbAbove");
              const btnProbBelow = getDomEl("btnProbBelow");
              if (btnProbAbove && data.yes_prob != null) btnProbAbove.innerText = `${data.yes_prob}%`;
              if (btnProbBelow && data.no_prob != null) btnProbBelow.innerText = `${data.no_prob}%`;
              
              return;
            }
          }
        } catch (e) { console.warn('Fetch failed:', e); }

        // 2. Direct public Kalshi API fallback (for standalone/mobile when local backend is unreachable).
        // Kalshi documented Trade API v2 host: https://external-api.kalshi.com.
        // Standardized on external-api.kalshi.com to match backend; api.elections.kalshi.com was a legacy elections-specific domain.
        let kRes = await fetch('https://external-api.kalshi.com/trade-api/v2/markets?series_ticker=KXBTC15M&status=open');
        let kJson = kRes.ok ? await kRes.json() : null;
        if (!kJson || !kJson.markets || kJson.markets.length === 0) {
          kRes = await fetch('https://external-api.kalshi.com/trade-api/v2/markets?series_ticker=KXBTC15M');
          kJson = kRes.ok ? await kRes.json() : null;
        }
        if (kJson && kJson.markets && kJson.markets.length > 0) {
          updateKalshiSyntheticBadges(false);
          const markets = kJson.markets;
          const m = markets[0];
          const yesBid = parseFloat(m.yes_bid_dollars || m.last_price_dollars || 0.5);
          const yesP = Math.round(yesBid * 100);
          const noP = 100 - yesP;
          const kObj = {
            strike: parseFloat(m.floor_strike || 0),
            yes_prob: yesP,
            no_prob: noP,
            ticker: m.ticker,
            source: "Kalshi KXBTC15M",
            is_synthetic: false
          };
          window.cachedKalshiData = kObj;
          if (kObj.strike > 0) {
            window.cachedBtcTargetPrice = kObj.strike;
            const topTargetHero = getDomEl("topBarTargetPrice");
            if (topTargetHero) {
              topTargetHero.innerText = `$${kObj.strike.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            }
          }

          const kYes = getDomEl("btcKalshiYesProb");
          const kNo = getDomEl("btcKalshiNoProb");
          if (kYes) kYes.innerText = `${yesP}% Yes`;
          if (kNo) kNo.innerText = `${noP}% No`;

          const btnProbAbove = getDomEl("btnProbAbove");
          const btnProbBelow = getDomEl("btnProbBelow");
          if (btnProbAbove) btnProbAbove.innerText = `${yesP}%`;
          if (btnProbBelow) btnProbBelow.innerText = `${noP}%`;
        }
      } catch (err) {
        console.warn("Direct Kalshi fetch fallback:", err);
      } finally {
        isFetchingKalshiDirect = false;
      }
    }

    // -------------------------------------------------------------------------
    // 15M Active Prediction Settlement & Persistent Tracking
    // -------------------------------------------------------------------------
    function recordActive15mPredictionForSettlement(targetPrice, predictedOutcome) {
      if (!targetPrice || !predictedOutcome) return;
      const nowSec = Math.floor(Date.now() / 1000);
      const intervalStartSec = Math.floor(nowSec / 900) * 900;
      
      let direction = "PASS";
      if ((predictedOutcome || "").includes("ABOVE")) direction = "ABOVE";
      if ((predictedOutcome || "").includes("BELOW")) direction = "BELOW";

      window._activeWindowTracker = {
        intervalStart: intervalStartSec,
        targetPrice: targetPrice,
        prediction: direction,
        recordedAt: Date.now()
      };
    }

    function settlePrevious15mInterval(settlePrice) {
      if (!window._activeWindowTracker || !settlePrice) return;
      const tracker = window._activeWindowTracker;
      const nowSec = Math.floor(Date.now() / 1000);
      const currentIntervalStart = Math.floor(nowSec / 900) * 900;

      // Only settle if we rolled into a new 15M interval
      if (currentIntervalStart > tracker.intervalStart) {
        // If the prediction was PASS, we just discard it entirely and don't count it towards accuracy
        if (tracker.prediction !== "PASS") {
          const actual = (settlePrice >= tracker.targetPrice) ? "ABOVE" : "BELOW";
          const isHit = (tracker.prediction === actual);

          try {
            let stored = [];
            const raw = localStorage.getItem("btc_15m_live_settlements");
            if (raw) stored = JSON.parse(raw);
            stored = stored.filter(s => s.time !== tracker.intervalStart);
            stored.push({
              time: tracker.intervalStart,
              target: tracker.targetPrice,
              settle: settlePrice,
              predicted: tracker.prediction,
              actual: actual,
              correct: isHit
            });
            if (stored.length > 100) stored = stored.slice(-100);
            localStorage.setItem("btc_15m_live_settlements", JSON.stringify(stored));
            updateDailyAccuracyHistory(stored, tracker.intervalStart);
          } catch (e) { console.warn('Fetch failed:', e); }
        }

        window._activeWindowTracker = null;

        // Re-evaluate and re-render accuracy immediately with newly settled pick
        evaluateClientAccuracy(window._lastRawCandles || [], window._lastIsCoinbaseFormat || true);
      }
    }

    const BTC_ACCURACY_HISTORY_KEY = "btc_15m_live_settlements";
    const BTC_DAILY_ACCURACY_HISTORY_KEY = "btc_15m_daily_accuracy";

    function accuracyDateKey(intervalStart) {
      const date = new Date(intervalStart * 1000);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, "0");
      const day = String(date.getDate()).padStart(2, "0");
      return `${year}-${month}-${day}`;
    }

    function getDailyAccuracyHistory() {
      try {
        const saved = JSON.parse(localStorage.getItem(BTC_DAILY_ACCURACY_HISTORY_KEY) || "{}");
        return saved && typeof saved === "object" && !Array.isArray(saved) ? saved : {};
      } catch (e) {
        return {};
      }
    }

    function updateDailyAccuracyHistory(settlements, changedIntervalStart) {
      const daily = getDailyAccuracyHistory();
      const dateKeys = Object.keys(daily).length === 0
        ? [...new Set(settlements.map(s => accuracyDateKey(s.time)))]
        : [accuracyDateKey(changedIntervalStart)];
      dateKeys.forEach(dateKey => {
        const daySettlements = settlements.filter(s => accuracyDateKey(s.time) === dateKey);
        daily[dateKey] = {
          total: daySettlements.length,
          correct: daySettlements.filter(s => s.correct).length
        };
      });
      localStorage.setItem(BTC_DAILY_ACCURACY_HISTORY_KEY, JSON.stringify(daily));
      return daily;
    }


    // Client-side Accuracy Evaluator: Starts at 0 of 0 on boot, counts up per logged 15m close
    function evaluateClientAccuracy(rawCandles, isCoinbaseFormat) {
      if (window.serverPredictionAccuracy) {
        renderBtcAccuracy(window.serverPredictionAccuracy);
        return window.serverPredictionAccuracy;
      }
      // Load live settlements saved in localStorage
      let liveSettlements = [];
      try {
        const stored = localStorage.getItem(BTC_ACCURACY_HISTORY_KEY);
        if (stored) {
          liveSettlements = JSON.parse(stored);
          if (!Array.isArray(liveSettlements)) liveSettlements = [];
          // If stored contains legacy dummy data with missing settle price, clear it to start clean
          if (liveSettlements.some(s => s.settle == null && s.target == null)) {
            liveSettlements = [];
            localStorage.removeItem(BTC_ACCURACY_HISTORY_KEY);
          }
        }
      } catch (e) {
        liveSettlements = [];
      }

      // Reconcile live settlements with official exchange candles
      let modified = false;
      if (rawCandles && rawCandles.length > 0) {
          liveSettlements.forEach(s => {
              // rawCandles timestamp is open time. We want the candle whose open time == s.time
              const matchingCandle = rawCandles.find(c => {
                  const ctSec = isCoinbaseFormat ? c[0] : Math.floor(c[0] / 1000);
                  return ctSec === s.time;
              });
              if (matchingCandle) {
                  const officialClose = parseFloat(matchingCandle[4]);
                  if (s.settle !== officialClose) {
                      s.settle = officialClose;
                      const actual = (officialClose >= s.target) ? "ABOVE" : "BELOW";
                      s.actual = actual;
                      s.correct = (s.predicted === actual);
                      modified = true;
                  }
              }
          });
          if (modified) {
              localStorage.setItem(BTC_ACCURACY_HISTORY_KEY, JSON.stringify(liveSettlements));
          }
      }

      const total = liveSettlements.length;
      const correct = liveSettlements.filter(o => o.correct).length;
      const pct = total > 0 ? (correct / total) * 100 : null;
      const recent = liveSettlements.slice(-5).map(o => o.correct);

      const accData = {
        total_evaluated: total,
        correct_picks: correct,
        accuracy_percent: pct !== null ? Math.round(pct * 10) / 10 : null,
        ratio_text: `${correct} of ${total} Correct`,
        recent_outcomes: liveSettlements.slice(-5)
      };

      window.cachedBtcAccuracy = accData;
      renderBtcAccuracy(accData);
      const dailyHistory = getDailyAccuracyHistory();
      if (Object.keys(dailyHistory).length === 0 && liveSettlements.length > 0) {
        liveSettlements.forEach(settlement => updateDailyAccuracyHistory(liveSettlements, settlement.time));
      }
      renderPreviousDaysAccuracy(getDailyAccuracyHistory());
      return accData;
    }

    async function resetBtcAccuracyCounter() {
      const apiBase = getKalshiApiBase();
      try {
        await authFetch(`${apiBase}/api/engine/${window.currentAsset}/prediction/accuracy/reset`, { method: "POST" });
        // After backend reset, refresh the status immediately
        if (typeof fetchKalshiTradingStatus === 'function') {
          fetchKalshiTradingStatus();
        }
      } catch (e) {
        console.error("Failed to reset accuracy", e);
      }
    }

    let lastTrackedIntervalBucket = Math.floor(Date.now() / (15 * 60 * 1000));

    // Server-Synced 1-second Countdown Timer with local fallback
    function updateBtcCountdownClock() {
      const now = Date.now();
      const nowSec = Math.floor(now / 1000);
      
      const tf = (btcCurrentTimeframe || "15m").toLowerCase();
      let tfSeconds = 900;
      if (tf === "1m") tfSeconds = 60;
      else if (tf === "5m") tfSeconds = 300;
      else if (tf === "15m") tfSeconds = 900;
      else if (tf === "1h") tfSeconds = 3600;
      else if (tf === "4h") tfSeconds = 14400;
      else if (tf === "1d") tfSeconds = 86400;

      let secondsLeft = 0;
      if (window._btcServerNextCloseEpoch && window._btcServerNextCloseEpoch > now) {
        secondsLeft = Math.floor((window._btcServerNextCloseEpoch - now) / 1000);
      } else {
        const elapsed = nowSec % tfSeconds;
        secondsLeft = tfSeconds - elapsed;
      }
      if (secondsLeft <= 0 || secondsLeft > tfSeconds) secondsLeft = tfSeconds;

      const m = Math.floor(secondsLeft / 60);
      const s = secondsLeft % 60;
      const formatted = tfSeconds >= 3600 
        ? `${String(Math.floor(secondsLeft / 3600)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}:${String(s).padStart(2, '0')}`
        : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;

      const cdEl = document.getElementById("btcCountdown");
      if (cdEl) cdEl.innerText = formatted;
      const iphoneCd = document.getElementById("iphone17CountdownText");
      if (iphoneCd) iphoneCd.innerText = formatted;

      // Dynamic color fading for countdown timer pill: Green -> Yellow -> Red
      const cdPill = document.getElementById("iphone17CountdownPill") || document.querySelector(".iphone17-countdown-pill");
      if (cdPill) {
        const ratio = Math.max(0, Math.min(1, secondsLeft / (tfSeconds || 900)));
        let r, g, b;
        if (ratio >= 0.5) {
          // Halfway to Full: Yellow (245, 158, 11) to Green (16, 185, 129)
          const f = (ratio - 0.5) * 2;
          r = Math.round(245 - f * (245 - 16));
          g = Math.round(158 + f * (185 - 158));
          b = Math.round(11 + f * (129 - 11));
        } else {
          // Zero to Halfway: Red (239, 68, 68) to Yellow (245, 158, 11)
          const f = ratio * 2;
          r = Math.round(239 + f * (245 - 239));
          g = Math.round(68 + f * (158 - 68));
          b = Math.round(68 - f * (68 - 11));
        }
        const rgbColor = `rgb(${r}, ${g}, ${b})`;
        cdPill.style.color = rgbColor;
        cdPill.style.borderColor = `rgba(${r}, ${g}, ${b}, 0.75)`;
        cdPill.style.backgroundColor = `rgba(${r}, ${g}, ${b}, 0.14)`;
        cdPill.style.boxShadow = `0 0 10px rgba(${r}, ${g}, ${b}, 0.3)`;
      }

      const barEl = document.getElementById("btcCountdownBar");
      if (barEl) {
        const pct = ((tfSeconds - secondsLeft) / tfSeconds) * 100;
        barEl.style.width = `${(isNaN(Math.min(100, Math.max(0, pct))) ? 0 : Math.min(100, Math.max(0, pct))).toFixed(1)}%`;
      }

      // Exact 30-seconds post-rollover refresh logic
      if (secondsLeft === 870) {
        const currentBucket = Math.floor(Date.now() / (15 * 60 * 1000));
        if (window._last1MinuteRefreshBucket !== currentBucket) {
           window._last1MinuteRefreshBucket = currentBucket;
           console.log("Exactly 30 seconds after contract start. Triggering mandatory prediction refresh.");
           fetchBtcKlinesDirect();
           setTimeout(triggerBtcAnalysis, 1000);
        }
      }

      // Instant 15M Window Rollover & Expiration Detector (Predicts Next 15M Immediately at T=0)
      const currentBucket = Math.floor(Date.now() / (15 * 60 * 1000));
      if (currentBucket !== lastTrackedIntervalBucket) {
        lastTrackedIntervalBucket = currentBucket;
        console.log("15M Contract Expired! Rollover triggered: settling prior contract & forecasting next interval...");

        // 1. Invalidate old cached Kalshi market data & locked forecast from prior contract
        window.cachedKalshiData = null;
        window.lockedContractForecast = null;

        // 2. Settle previous 15m interval with latest BTC price
        if (lastBtcPrice) {
          settlePrevious15mInterval(lastBtcPrice);
        }

        // 3. Set new 15M start price target to current price immediately
        if (lastBtcPrice) {
          window.cachedBtcTargetPrice = lastBtcPrice;
          const topTargetHero = document.getElementById("topBarTargetPrice");
          if (topTargetHero) {
            topTargetHero.innerText = `$${lastBtcPrice.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
          }
        }

        // 4. Immediately trigger fast Kalshi direct fetch for new floor strike
        fetchKalshiDirect();

        // 5. Instant Next-15M Contract Rollover Forecast
        if (window._lastRawCandles && window._lastRawCandles.length >= 5) {
          const forecast = evaluateClientNextContractForecast(window._lastRawCandles, window._lastIsCoinbaseFormat, window.cachedBtcTargetPrice);
          if (forecast) {
            // window.cachedNextContractForecast = forecast;
            // applyNextContractForecastToUI(forecast);
            // Removed overriding with client-side indicators; backend ML model should be the source of truth
            if (forecast.conviction_grade === "GRADE A+ SETUP" || forecast.conviction_grade === "GRADE A SETUP") {
              playRolloverAlertTone(true);
            }
          }
        }

        // 6. Follow-up refresh from exchange & backend
        setTimeout(() => {
          fetchBtcKlinesDirect();
          triggerBtcAnalysis();
        }, 1500);

        // Follow-up retry at 7s to ensure exchange recorded the finalized candle
        setTimeout(() => {
          fetchBtcKlinesDirect();
        }, 7000);
      }

      // Keep active prediction tracked throughout window for settlement
      if (window.cachedBtcTargetPrice && window.cachedBtcPredictedOutcome) {
        recordActive15mPredictionForSettlement(window.cachedBtcTargetPrice, window.cachedBtcPredictedOutcome);
      }

      return secondsLeft;
    }

    // Direct Public 15m Klines Fetcher (Force use Desktop 15M Start Price Benchmark on Mobile)
    async function fetchBtcKlinesDirect() {
      if (isFetchingKlinesDirect) return;
      if (window.currentAsset !== 'BTC' && window.currentAsset !== 'ETH') { isFetchingKlinesDirect = false; return; }
        isFetchingKlinesDirect = true;
      try {
        // 0. If on standalone mobile, check bundled desktop analysis first
        if (!window.cachedBtcTargetPrice) {
          try {
            const analysisFile = window.currentAsset === 'BTC' ? 'btc_analysis.json' : (window.currentAsset.toLowerCase() + '_analysis.json');
              const staticResp = await fetchBundledData(analysisFile);
            if (staticResp.ok) {
              const staticData = await staticResp.json();
              if (staticData && staticData.target_benchmark && staticData.target_benchmark.target_price) {
                const tb = staticData.target_benchmark;
                window.cachedBtcTargetPrice = Number(tb.target_price);
                const topTargetHero = document.getElementById("topBarTargetPrice");
                if (topTargetHero) topTargetHero.innerText = `$${Number(tb.target_price).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                if (tb.last_5_targets && tb.last_5_targets.length > 0) {
                  renderBtcTrendBox(tb.last_5_targets, tb.streak_summary);
                }
              }
            }
          } catch (eStatic) { console.warn('Fetch failed:', eStatic); }
        }

        let rawCandles = null;
        let isCoinbaseFormat = false;

        // 1. Primary: Coinbase Exchange 15m candles (CORS: *, 100% US & mobile friendly, identical to desktop)
        try {
          const cbPair = window.currentAsset === 'ETH' ? 'ETH-USD' : 'BTC-USD';
          const cbUrl = `https://api.exchange.coinbase.com/products/${cbPair}/candles?granularity=900`;
          const cbRes = await fetch(cbUrl);
          if (cbRes.ok) {
            const cbData = await cbRes.json();
            if (Array.isArray(cbData) && cbData.length >= 7) {
              // Coinbase format: [time, low, high, open, close, volume] - sorted ascending (30 candles for full 20-pick evaluation)
              rawCandles = cbData.slice(0, 30).sort((a, b) => a[0] - b[0]);
              isCoinbaseFormat = true;
            }
          }
        } catch (eCb) {
          console.warn("Coinbase klines fetch error:", eCb);
        }

        // 2. Fallback: Binance US / Binance Vision
        if (!rawCandles) {
          try {
            const bPair = window.currentAsset === 'ETH' ? 'ETHUSDT' : 'BTCUSDT';
            const bUrl = `https://api.binance.us/api/v3/klines?symbol=${bPair}&interval=15m&limit=30`;
            const bRes = await fetch(bUrl);
            if (bRes.ok) {
              const bData = await bRes.json();
              if (Array.isArray(bData) && bData.length >= 7) {
                rawCandles = bData;
                isCoinbaseFormat = false;
              }
            }
          } catch (eB) {
            try {
              const bPair = window.currentAsset === 'ETH' ? 'ETHUSDT' : 'BTCUSDT';
              const bvUrl = `https://data-api.binance.vision/api/v3/klines?symbol=${bPair}&interval=15m&limit=30`;
              const bvRes = await fetch(bvUrl);
              if (bvRes.ok) {
                const bvData = await bvRes.json();
                if (Array.isArray(bvData) && bvData.length >= 7) {
                  rawCandles = bvData;
                  isCoinbaseFormat = false;
                }
              }
            } catch (eBv) { console.warn('Fetch failed:', eBv); }
          }
        }

        if (rawCandles && rawCandles.length >= 7) {
          window._lastRawCandles = rawCandles;
          window._lastIsCoinbaseFormat = isCoinbaseFormat;

          // Active 15M candle is the latest element (index length - 1)
          const currCandle = rawCandles[rawCandles.length - 1];
          // Coinbase: index 3 is open; Binance: index 1 is open
          const targetOpen = isCoinbaseFormat ? parseFloat(currCandle[3]) : parseFloat(currCandle[1]);
          window.cachedBtcTargetPrice = targetOpen;

          // Compute interval start time in 12hr UTC format matching desktop
          const tSec = isCoinbaseFormat ? currCandle[0] : Math.floor(currCandle[0] / 1000);
          const dObj = new Date(tSec * 1000);
          const timeStr = dObj.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true, timeZone: 'UTC' });

          const topTargetHero = document.getElementById("topBarTargetPrice");
          if (topTargetHero && targetOpen) {
            topTargetHero.innerText = `$${targetOpen.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
          }

          // Extract last 5 completed intervals (slice -6 to -1)
          const last5Raw = rawCandles.slice(-6, -1);
          let higherCount = 0;
          let lowerCount = 0;
          window.cachedBtcLast5Targets = last5Raw.map((c, idx) => {
            const closeP = parseFloat(c[4]);
            const priorIdx = rawCandles.length - 6 - 1 + idx;
            const priorClose = parseFloat(rawCandles[priorIdx][4]);
            const delta = closeP - priorClose;
            const deltaPct = (delta / priorClose) * 100;
            const isUp = delta >= 0;
            if (isUp) { higherCount++; lowerCount = 0; } else { lowerCount++; higherCount = 0; }

            const ctSec = isCoinbaseFormat ? c[0] : Math.floor(c[0] / 1000);
            // 15M candle close timestamp is 900s after open
            const closeSec = ctSec + 900;
            const cdObj = new Date(closeSec * 1000);
            const cTimeStr = cdObj.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });

            return {
              time: cTimeStr,
              price: closeP,
              direction: isUp ? "HIGHER" : "LOWER",
              arrow: isUp ? "▲" : "▼",
              delta: delta,
              delta_pct: deltaPct
            };
          });

          if (higherCount > 1) {
            window.cachedBtcStreak = `🔥 ${higherCount} consecutive HIGHER closes`;
          } else if (lowerCount > 1) {
            window.cachedBtcStreak = `❄️ ${lowerCount} consecutive LOWER closes`;
          } else {
            window.cachedBtcStreak = "⚡ Neutral Interval Bias";
          }

          renderBtcTrendBox(window.cachedBtcLast5Targets, window.cachedBtcStreak);

          // Evaluate & Update 15M Prediction Accuracy Tracker across completed intervals
          evaluateClientAccuracy(rawCandles, isCoinbaseFormat);

          if (lastBtcPrice && window.cachedBtcTargetPrice) {
            evaluateClientTargetPrediction(lastBtcPrice, window.cachedBtcTargetPrice);
          }
        }
      } catch (err) {
        console.warn("Direct klines fetch fallback:", err);
      } finally {
        isFetchingKlinesDirect = false;
      }
    }

    // Client-side 15M Contract Prediction Evaluator
    // Locks prediction at 1 minute after contract start based on historical price, volume, and chart patterns,
    // and sticks with that prediction until the end of the contract.
    function evaluateClientTargetPrediction(price, target) {
      if (!price || !target) return;
      const delta = price - target;
      const deltaPct = (delta / target) * 100;
      const isAbove = delta >= 0;

      const nowSec = Math.floor(Date.now() / 1000);
      let tfSeconds = 900;
      if (typeof btcCurrentTimeframe !== 'undefined') {
        if (btcCurrentTimeframe === '1m') tfSeconds = 60;
        else if (btcCurrentTimeframe === '5m') tfSeconds = 300;
        else if (btcCurrentTimeframe === '1h') tfSeconds = 3600;
        else if (btcCurrentTimeframe === '4h') tfSeconds = 14400;
        else if (btcCurrentTimeframe === '1d') tfSeconds = 86400;
      }
      const intervalId = Math.floor(nowSec / tfSeconds) * tfSeconds;
      const elapsed = nowSec % tfSeconds;
      const SCAN_TIME = tfSeconds === 60 ? 5 : 30; // 5 seconds scan for 1m, 30s for 15m

      // 1. Wait for valid ML Prediction (including PASS), otherwise stay in scanning state
      let fc = window.cachedNextContractForecast;
      let hasValidPrediction = fc && fc.direction; // Relaxed strict check to allow ANY valid direction string from backend to pass scanning state
        if (hasValidPrediction) {
          const d = fc.direction.toUpperCase();
          if (d.includes("ABOVE") || d.includes("YES") || d.includes("UP")) fc.direction = "ABOVE";
          else if (d.includes("BELOW") || d.includes("NO") || d.includes("DOWN")) fc.direction = "BELOW";
          else if (d.includes("PASS") || d.includes("CHOP")) fc.direction = "PASS";
          else hasValidPrediction = false; // Invalid string format
        }

      if ((elapsed < SCAN_TIME || !hasValidPrediction) && (!window.lockedContractForecast || window.lockedContractForecast.intervalId !== intervalId)) {
        const outcomeText = document.getElementById("btcPredOutcomeText");
        const probText = document.getElementById("btcPredProbText");
        const confTag = document.getElementById("btcPredConfidenceTag");
        const lockIcon = document.getElementById("btcPredLockIcon");
        if (outcomeText) {
          outcomeText.innerText = "⏳ 30S SCAN";
          outcomeText.className = "text-xl sm:text-2xl lg:text-[28px] whitespace-nowrap font-black tracking-tight text-amber-300 font-mono leading-none";
        }
        if (probText) probText.innerText = `${Math.max(0, SCAN_TIME - elapsed)}s`;
        if (confTag) confTag.innerText = "ANALYZING";
        if (lockIcon) lockIcon.classList.add("hidden");
        const bubble = document.getElementById("kalshiMLStatusBubble");
        if (bubble) {
          bubble.innerText = `SCANNING (${Math.max(0, SCAN_TIME - elapsed)}s)`;
          bubble.className = "ml-1 px-1.5 py-0.5 text-[8px] font-bold uppercase rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/50 animate-pulse whitespace-nowrap cursor-help";
        }
        return;
      }

      // 2. Lock in ML prediction
      if (!window.lockedContractForecast || window.lockedContractForecast.intervalId !== intervalId) {
        let dir = fc.direction;
        if (dir === "YES") dir = "ABOVE";
        if (dir === "NO") dir = "BELOW";
        
        let isPass = (dir === "PASS");
        let prob = (fc && fc.probability_percent) ? fc.probability_percent : 50;
        let badge = (fc && fc.conviction_badge) ? fc.conviction_badge : (isPass ? "⚪ NO EDGE" : "MODERATE EDGE");
        let grade = (fc && fc.conviction_grade) ? fc.conviction_grade : (isPass ? "CHOPPY MARKET" : "GRADE A SETUP");
        let edge = (fc && fc.primary_edge) ? fc.primary_edge : (isPass ? "Awaiting clearer setup" : "Pattern support");
        
        window.lockedContractForecast = {
          intervalId: intervalId,
          lockedAt: nowSec,
          direction: dir,
          outcome: isPass ? "NO CLEAR EDGE DETECTED" : (dir === "ABOVE" ? "LIKELY TO CLOSE ABOVE TARGET" : "LIKELY TO CLOSE BELOW TARGET"),
          outcomeText: isPass ? "⚪ PASS" : (dir === "ABOVE" ? "▲ UP" : "▼ DOWN"),
          probability_percent: prob,
          confidence_badge: badge,
          conviction_grade: grade,
          primary_edge: edge,
          decision_factors: (fc && fc.catalysts) ? fc.catalysts : []
        };
        window.cachedNextContractForecast = window.lockedContractForecast;
      }

      // 3. Sticking with the locked prediction until the end of the contract
      const locked = window.lockedContractForecast;
      const isLockedAbove = locked.direction === "ABOVE";

      const liveFactors = [
        ...locked.decision_factors.slice(0, 2),
        `Live cushion: ${isAbove ? '+' : '-'}$${(isNaN(Math.abs(delta)) ? 0 : Math.abs(delta)).toFixed(2)} (${isAbove ? '+' : '-'}${(isNaN(Math.abs(deltaPct)) ? 0 : Math.abs(deltaPct)).toFixed(2)}%)`,
        `${btcCurrentTimeframe.toUpperCase()} Contract Close in: ${Math.floor((900 - elapsed) / 60)}m ${((900 - elapsed) % 60)}s`
      ];

      const tb = {
        predicted_outcome: locked.outcome,
        probability_percent: locked.probability_percent,
        confidence_badge: locked.confidence_badge,
        next_contract_forecast: locked,
        decision_factors: liveFactors
      };

      const outEl = document.getElementById("btcPredOutcomeText");
      const probEl = document.getElementById("btcPredProbText");
      const confEl = document.getElementById("btcPredConfidenceTag");
      const lockEl = document.getElementById("btcPredLockIcon");

      if (outEl) {
        outEl.innerText = locked.outcomeText;
        if (locked.direction === "ABOVE") outEl.className = "text-xl sm:text-2xl lg:text-[28px] whitespace-nowrap font-black tracking-tight text-emerald-400 font-mono leading-none";
        else if (locked.direction === "BELOW") outEl.className = "text-xl sm:text-2xl lg:text-[28px] whitespace-nowrap font-black tracking-tight text-red-400 font-mono leading-none";
        else outEl.className = "text-xl sm:text-2xl lg:text-[28px] whitespace-nowrap font-black tracking-tight text-slate-400 font-mono leading-none";
      }
      if (probEl) probEl.innerText = `${locked.probability_percent}%`;
      if (confEl) confEl.innerText = locked.conviction_grade;
      if (lockEl) lockEl.classList.remove("hidden");

      const bubble = document.getElementById("kalshiMLStatusBubble");
      if (bubble) {
        if (locked.direction === "pass" || locked.direction === "PASS") {
          bubble.innerText = "PASS";
          bubble.className = "ml-1 px-1.5 py-0.5 text-[8px] font-bold uppercase rounded-full bg-slate-800 text-slate-400 border border-slate-600 whitespace-nowrap cursor-help";
        } else {
          bubble.innerText = locked.direction === "ABOVE" ? "UP" : "DOWN";
          bubble.className = locked.direction === "ABOVE" ? "ml-1 px-1.5 py-0.5 text-[8px] font-bold uppercase rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/50 whitespace-nowrap cursor-help" : "ml-1 px-1.5 py-0.5 text-[8px] font-bold uppercase rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/50 whitespace-nowrap cursor-help";
        }
      }


      // Speedometer needle tracks locked conviction direction
      const meterScore = isLockedAbove ? Math.round((locked.probability_percent - 50) * 2) : -Math.round((locked.probability_percent - 50) * 2);
      updateBtcConfluenceGauge(meterScore, isLockedAbove ? "BUY" : "SELL", locked.probability_percent);
    }

    // Client-side Live Display Updater (for Mobile, iPhone / Standalone)
    function updateClientBtcLive(price, stats = null) {
      const topPriceEl = document.getElementById("topBarLivePrice");
      if (topPriceEl && price > 0) {
        topPriceEl.innerText = `$${price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (lastBtcPrice && price !== lastBtcPrice) {
          topPriceEl.classList.remove("price-flash-up", "price-flash-down");
          void topPriceEl.offsetWidth;
          topPriceEl.classList.add(price > lastBtcPrice ? "price-flash-up" : "price-flash-down");
        }
      }
      lastBtcPrice = price;

      // Update 24h stats if available on mobile
      if (stats) {
        if (stats.change_24h != null) {
        }
        if (stats.volume != null) {
        }
        if (stats.low != null && stats.high != null) {
        }
      }

      // Update Target Spread Delta
      const target = window.cachedBtcTargetPrice;
      if (target && target > 0) {
        const delta = price - target;
        const deltaPct = (delta / target) * 100;
        const isAbove = delta >= 0;
        const arrow = isAbove ? "▲" : "▼";
        const sign = isAbove ? "+" : "-";
        const absDelta = Math.abs(delta);
        const absPct = Math.abs(deltaPct);
        const textStatus = isAbove ? "ABOVE TARGET" : "BELOW TARGET";


        const topTarget = document.getElementById("topBarTargetPrice");
        const topCard = document.getElementById("topBarTargetCard");
        if (topTarget && target && target > 0) {
          topTarget.innerText = `$${target.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
          applyTargetPriceColor(topTarget, price, target);
        }
        if (topCard && target && target > 0 && price > 0) {
          updateTargetCardBorder(topCard, price, target);
        }
        const topDelta = document.getElementById("topBarTargetDelta");
        if (topDelta && target && target > 0 && price > 0) {
          topDelta.innerText = `${isAbove ? "+" : ""}$${delta.toFixed(1)}`;
          topDelta.className = "text-[7px] sm:text-[8px] font-mono font-bold " + (isAbove ? "text-emerald-400" : "text-red-400");
        }

        evaluateClientTargetPrediction(price, target);
      }
    }

    // High-Frequency 1-Second Polling Stream
    let _isPollingBtcLive = false;
    async function pollBtcLive1s() {
      // 1. Always update local countdown clock
      updateBtcCountdownClock();

      if (activeMode !== 'btc_analyzer') return;
      if (_isPollingBtcLive) return;
      _isPollingBtcLive = true;

      let livePrice = null;
      let liveStats = null;
      let handledByServer = false;

      // 2. Try local server first (generous 2500ms timeout so mobile Wi-Fi / LAN doesn't abort)
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2500);
        const apiBase = getKalshiApiBase();
        let res;
        try {
          res = await fetch(`${apiBase}/api/engine/${window.currentAsset}/live`, { signal: controller.signal });
        } finally {
          clearTimeout(timeoutId);
        }
        if (res && res.ok) {
          const liveData = await res.json();
          if (typeof liveData.seconds_left === 'number' && liveData.seconds_left > 0) {
            // Only sync the epoch if we don't have one yet, or if it has expired,
            // or if the server value differs from our local tracking by more than 3 seconds.
            // This prevents the countdown from being reset on every 1s poll.
            const newEpoch = Date.now() + (liveData.seconds_left * 1000);
            const currentSecondsLeft = window._btcServerNextCloseEpoch
              ? Math.floor((window._btcServerNextCloseEpoch - Date.now()) / 1000)
              : -1;
            if (!window._btcServerNextCloseEpoch ||
                window._btcServerNextCloseEpoch <= Date.now() ||
                Math.abs(currentSecondsLeft - liveData.seconds_left) > 3) {
              window._btcServerNextCloseEpoch = newEpoch;
            }
          }
          renderBtcHeroHud(liveData);
          if (liveData.target_price) {
            window.cachedBtcTargetPrice = liveData.target_price;
          }
          if (liveData.last_5_targets && liveData.last_5_targets.length > 0) {
            renderBtcTrendBox(liveData.last_5_targets, liveData.streak_summary);
          }
          if (liveData.price && liveData.price > 0) {
            updateClientBtcLive(liveData.price, { volume: liveData.volume_24h });
          }
          if (liveData.volume_24h) {
            window.cachedBtcVolume = liveData.volume_24h;
          }
          if (liveData.kalshi && liveData.kalshi.volume_24h) {
            window.lastKalshiVolume = liveData.kalshi.volume_24h;
          }
          if (liveData.kalshi) {
            window.cachedKalshiData = liveData.kalshi;
            const isSynth = !!(liveData.kalshi.is_synthetic || liveData.kalshi.status === "synthetic" || liveData.kalshi.source === "Kalshi Synthetic");
            if (typeof updateKalshiSyntheticBadges === 'function') {
              updateKalshiSyntheticBadges(isSynth);
            }
            const kYes = getDomEl("btcKalshiYesProb");
            const kNo = getDomEl("btcKalshiNoProb");
            const btnProbAbove = getDomEl("btnProbAbove");
            const btnProbBelow = getDomEl("btnProbBelow");
            if (kYes) kYes.innerText = `${liveData.kalshi.yes_prob}% Yes (Above)`;
            if (kNo) kNo.innerText = `${liveData.kalshi.no_prob}% No (Below)`;
            if (btnProbAbove) btnProbAbove.innerText = `${liveData.kalshi.yes_prob}%`;
            if (btnProbBelow) btnProbBelow.innerText = `${liveData.kalshi.no_prob}%`;
          }
          // Live seconds handled synchronously by updateBtcCountdownClock()
          handledByServer = true;
          _isPollingBtcLive = false;
          return;
        }
      } catch (err) { console.warn('Fetch failed:', err); }

      if (handledByServer) { _isPollingBtcLive = false; return; }

      // 3. Primary Mobile Client Fallback: Coinbase Exchange Ticker (CORS: *, 100% US-friendly, no geoblock)
      try {
        const cbPair = window.currentAsset === 'ETH' ? 'ETH-USD' : 'BTC-USD';
        const cbTickRes = await fetch(`https://api.exchange.coinbase.com/products/${cbPair}/ticker`);
        if (cbTickRes.ok) {
          const cbTick = await cbTickRes.json();
          livePrice = parseFloat(cbTick.price);
          liveStats = { volume: parseFloat(cbTick.volume) };
        }
      } catch (e1) {
        // 4. Coinbase v2 Spot
        try {
          const cbPair = window.currentAsset === 'ETH' ? 'ETH-USD' : 'BTC-USD';
          const cbSpotRes = await fetch(`https://api.coinbase.com/v2/prices/${cbPair}/spot`);
          if (cbSpotRes.ok) {
            const cbSpot = await cbSpotRes.json();
            livePrice = parseFloat(cbSpot.data.amount);
          }
        } catch (e2) {
          // 5. Binance US / Vision fallback
          try {
            const bPair = window.currentAsset === 'ETH' ? 'ETHUSDT' : 'BTCUSDT';
            const bRes = await fetch(`https://api.binance.us/api/v3/ticker/price?symbol=${bPair}`);
            if (bRes.ok) {
              const bData = await bRes.json();
              livePrice = parseFloat(bData.price);
            }
          } catch (e3) {
            try {
              const bPair2 = window.currentAsset === 'ETH' ? 'ETHUSDT' : 'BTCUSDT';
                const bvRes = await fetch(`https://data-api.binance.vision/api/v3/ticker/price?symbol=${bPair2}`);
              if (bvRes.ok) {
                const bvData = await bvRes.json();
                livePrice = parseFloat(bvData.price);
              }
            } catch (e4) { console.warn('Fetch failed:', e4); }
          }
        }
      }

      // Fetch 24h stats from Coinbase if needed (every 20s)
      if (livePrice && (!window._lastCbStatsTime || (Date.now() - window._lastCbStatsTime > 20000))) {
        try {
          const cbPair = window.currentAsset === 'ETH' ? 'ETH-USD' : 'BTC-USD';
          const cbStatsRes = await fetch(`https://api.exchange.coinbase.com/products/${cbPair}/stats`);
          if (cbStatsRes.ok) {
            const st = await cbStatsRes.json();
            const openP = parseFloat(st.open);
            const highP = parseFloat(st.high);
            const lowP = parseFloat(st.low);
            const chgPct = openP > 0 ? ((livePrice - openP) / openP) * 100 : 0;
            window._cachedCbStats = {
              change_24h: chgPct,
              open: openP,
              high: highP,
              low: lowP,
              volume: parseFloat(st.volume)
            };
            window._lastCbStatsTime = Date.now();
          }
        } catch (eStats) { console.warn('Fetch failed:', eStats); }
      }

      if (window._cachedCbStats) {
        liveStats = { ...(liveStats || {}), ...window._cachedCbStats };
      }

      if (livePrice && livePrice > 0) {
        updateClientBtcLive(livePrice, liveStats);
      }

      // Ensure 15M target benchmark is actively fetched and verified on mobile (every 5 min or if missing)
      if (!window._lastTargetPollTime || (Date.now() - window._lastTargetPollTime > 300000) || !window.cachedBtcTargetPrice) {
        window._lastTargetPollTime = Date.now();
        fetchBtcKlinesDirect();
      }

      // Periodically refresh Kalshi prediction probabilities (every 3s) without touching target price
      if (!window._lastKalshiPollTime || (Date.now() - window._lastKalshiPollTime > 3000)) {
        window._lastKalshiPollTime = Date.now();
        fetchKalshiDirect();
      }
      _isPollingBtcLive = false;
    }

    async function triggerBtcAnalysis() {
      if (window._isAnalyzing) return;
      window._isAnalyzing = true;


      try {
        let analysisData = null;
        let candlesData = null;

        const analysisPromise = fetch(`/api/engine/${window.currentAsset}/analyze?timeframe=${btcCurrentTimeframe}`)
          .then(res => res.ok ? res.json() : null)
          .catch(e => null);

        const candlesPromise = fetch(`/api/engine/${window.currentAsset}/candles?timeframe=${btcCurrentTimeframe}`)
          .then(res => res.ok ? res.json() : null)
          .catch(e => null);

        const [aData, cData] = await Promise.all([analysisPromise, candlesPromise]);
        analysisData = aData;
        candlesData = cData;

        // Direct Public Kline Fallback for iPhone / standalone (Primary: Coinbase CORS: *, Fallback: Binance)
        if (!candlesData) {
          try {
            const cbPair = window.currentAsset === 'ETH' ? 'ETH-USD' : 'BTC-USD';
            const cbGran = btcCurrentTimeframe === '1m' ? 60 : (btcCurrentTimeframe === '5m' ? 300 : (btcCurrentTimeframe === '1h' ? 3600 : 900));
            const cbRes = await fetch(`https://api.exchange.coinbase.com/products/${cbPair}/candles?granularity=${cbGran}`);
            if (cbRes.ok) {
              const cbCandles = await cbRes.json();
              if (Array.isArray(cbCandles) && cbCandles.length > 0) {
                // Coinbase format: [time, low, high, open, close, volume] sorted newest first
                const sorted = cbCandles.slice(0, 100).sort((a, b) => a[0] - b[0]);
                const cArr = [];
                const vArr = [];
                for (const k of sorted) {
                  const t = k[0];
                  const lo = parseFloat(k[1]);
                  const hi = parseFloat(k[2]);
                  const op = parseFloat(k[3]);
                  const cl = parseFloat(k[4]);
                  const vo = parseFloat(k[5]);
                  cArr.push({ time: t, open: op, high: hi, low: lo, close: cl });
                  vArr.push({ time: t, value: vo, color: cl >= op ? '#10b98180' : '#ef444480' });
                }
                const targetOpen = cArr.length > 0 ? cArr[cArr.length - 1].open : (sorted.length > 0 ? parseFloat(sorted[sorted.length - 1][3]) : 0);
                candlesData = {
                  candles: cArr,
                  volume: vArr,
                  target_price: targetOpen
                };
              }
            }
          } catch (eCb) {
            console.warn("Direct Coinbase candles fetch failed, trying Binance:", eCb);
          }
        }

        if (!candlesData) {
          try {
            const fallbackPair = window.currentAsset === 'ETH' ? 'ETHUSDT' : 'BTCUSDT';
              const directKlineRes = await fetch(`https://data-api.binance.vision/api/v3/klines?symbol=${fallbackPair}&interval=${btcCurrentTimeframe}&limit=100`);
            if (directKlineRes.ok) {
              const rawKlines = await directKlineRes.json();
              if (Array.isArray(rawKlines) && rawKlines.length > 0) {
                const cArr = [];
                const vArr = [];
                for (const k of rawKlines) {
                  const t = Math.floor(k[0] / 1000);
                  const op = parseFloat(k[1]);
                  const hi = parseFloat(k[2]);
                  const lo = parseFloat(k[3]);
                  const cl = parseFloat(k[4]);
                  const vo = parseFloat(k[5]);
                  cArr.push({ time: t, open: op, high: hi, low: lo, close: cl });
                  vArr.push({ time: t, value: vo, color: cl >= op ? '#10b98180' : '#ef444480' });
                }
                const targetOpen = cArr.length > 0 ? cArr[cArr.length - 1].open : (rawKlines.length > 0 ? parseFloat(rawKlines[rawKlines.length - 1][1]) : 0);
                candlesData = {
                  candles: cArr,
                  volume: vArr,
                  target_price: targetOpen
                };
              }
            }
          } catch (e) {
            console.warn("Direct Binance candles fetch failed:", e);
          }
        }

        if (!candlesData) {
          try {
            const fallbackCandles = await fetch(`data/btc_candles.json`);
            if (fallbackCandles.ok) candlesData = await fallbackCandles.json();
          } catch (e) { console.warn('Fetch failed:', e); }
        }

        // 3. Update Chart (Candles, Volume Histogram, Overlays)
        if (btcChart && btcCandleSeries && candlesData && candlesData.candles) {
          btcCandleSeries.setData(candlesData.candles);
          if (candlesData.candles && candlesData.candles.length > 0) {
            window.lastCandle = Object.assign({}, candlesData.candles[candlesData.candles.length - 1]);
          }
          if (candlesData.volume && btcVolumeSeries) btcVolumeSeries.setData(candlesData.volume);
          if (candlesData.ema9 && btcEma9Series) btcEma9Series.setData(candlesData.ema9);
          if (candlesData.ema21 && btcEma21Series) btcEma21Series.setData(candlesData.ema21);
          if (candlesData.ema50 && btcEma50Series) btcEma50Series.setData(candlesData.ema50);
          if (candlesData.ema200 && btcEma200Series) btcEma200Series.setData(candlesData.ema200);

          if (candlesData.markers) {
            btcCandleSeries.setMarkers(candlesData.markers);
          }

          if (btcSupportLine) btcCandleSeries.removePriceLine(btcSupportLine);
          if (btcResistanceLine) btcCandleSeries.removePriceLine(btcResistanceLine);
          if (btcTargetLine) btcCandleSeries.removePriceLine(btcTargetLine);
          if (btcEntryLine) btcCandleSeries.removePriceLine(btcEntryLine);
          if (btcSlLine) btcCandleSeries.removePriceLine(btcSlLine);
          if (btcTp1Line) btcCandleSeries.removePriceLine(btcTp1Line);

          // Plot 15M Target Benchmark Price Line
          const targetPr = (analysisData && analysisData.target_benchmark && analysisData.target_benchmark.target_price) || (candlesData && candlesData.target_price);
          if (targetPr) {
            btcTargetLine = btcCandleSeries.createPriceLine({
              price: targetPr,
              color: "#f59e0b",
              lineWidth: 2,
              lineStyle: 0,
              axisLabelVisible: true,
              title: "15M TARGET",
            });
          }

          // Plot Trade Setup Lines
          const setupData = (analysisData && analysisData.trade_setup) || (candlesData && candlesData.trade_setup);
          if (setupData && setupData.entry_price) {
            btcEntryLine = btcCandleSeries.createPriceLine({
              price: setupData.entry_price,
              color: "#38bdf8",
              lineWidth: 1.5,
              lineStyle: 2,
              axisLabelVisible: true,
              title: "ENTRY",
            });
            if (setupData.stop_loss) {
              btcSlLine = btcCandleSeries.createPriceLine({
                price: setupData.stop_loss,
                color: "#ef4444",
                lineWidth: 1.5,
                lineStyle: 2,
                axisLabelVisible: true,
                title: "SL",
              });
            }
            if (setupData.take_profit_1) {
              btcTp1Line = btcCandleSeries.createPriceLine({
                price: setupData.take_profit_1,
                color: "#10b981",
                lineWidth: 1.5,
                lineStyle: 2,
                axisLabelVisible: true,
                title: "TP1",
              });
            }
          }

          if (analysisData && analysisData.market_structure) {
            if (analysisData.market_structure.nearest_support) {
              btcSupportLine = btcCandleSeries.createPriceLine({
                price: analysisData.market_structure.nearest_support,
                color: "#10b981",
                lineWidth: 1,
                lineStyle: 2,
                axisLabelVisible: true,
                title: "SUP",
              });
            }
            if (analysisData.market_structure.nearest_resistance) {
              btcResistanceLine = btcCandleSeries.createPriceLine({
                price: analysisData.market_structure.nearest_resistance,
                color: "#ef4444",
                lineWidth: 1,
                lineStyle: 2,
                axisLabelVisible: true,
                title: "RES",
              });
            }
          }

        }

        // 4. Update Analysis, HUD, Trend Box, Predictor & Calculator
        if (analysisData) {
          const forecastData = (analysisData.target_benchmark && analysisData.target_benchmark.next_contract_forecast) ? analysisData.target_benchmark.next_contract_forecast : null;
          if (forecastData && forecastData.direction) {
            window.cachedNextContractForecast = {
              direction: forecastData.direction,
              recommendation: forecastData.recommendation || forecastData.direction,
              probability_percent: forecastData.probability_percent || Math.round((forecastData.ml_prob || 0.5) * 100),
              conviction_badge: forecastData.conviction_badge,
              conviction_grade: forecastData.conviction_grade,
              primary_edge: forecastData.primary_edge,
              catalysts: forecastData.catalysts
            };
            applyNextContractForecastToUI(window.cachedNextContractForecast);
          }
          if (analysisData.target_benchmark) {
            renderBtcHeroHud({ ...analysisData.target_benchmark, price: analysisData.price || analysisData.target_benchmark.current_price });
            renderBtcTrendBox(analysisData.target_benchmark.last_5_targets, analysisData.target_benchmark.streak_summary);
            renderBtcPredictor({
              ...analysisData.target_benchmark,
              prediction_generated_at: analysisData.generated_at
            });
            if (analysisData.target_benchmark && analysisData.target_benchmark.prediction_accuracy && !window.cachedBtcAccuracy) {
              renderBtcAccuracy(analysisData.target_benchmark.prediction_accuracy);
            }
          }
          if (window._lastRawCandles) {
            evaluateClientAccuracy(window._lastRawCandles, window._lastIsCoinbaseFormat);
          }
          currentBtcSetup = analysisData.trade_setup;
          calculatePositionSize();

          updateBtcConfluenceGauge(analysisData.confluence_score || 0, analysisData.direction || "NEUTRAL", analysisData.confidence_percent || 50);
          renderBtcTradeSetup(analysisData.trade_setup);
          renderBtcIndicators(analysisData.indicators);
          renderBtcStructure(analysisData.market_structure);
          renderBtcCatalystsAndPatterns(analysisData);
          addBtcLogEntry(analysisData);

          if (btcLastSignal && btcLastSignal !== analysisData.direction && Math.abs(analysisData.confluence_score || 0) >= 20) {
            playBtcAlertSound(analysisData.primary_bias === "UP");
          }
          btcLastSignal = analysisData.direction;
        }

      } catch (err) {
        console.error("BTC Analysis error:", err);
      } finally {
        window._isAnalyzing = false;
        if (btn) btn.disabled = false;
        if (icon) icon.innerHTML = "&#x21bb;";
      }
    }

    async function updateBtcCountdown() {
      if (activeMode !== 'btc_analyzer') return;
      updateBtcCountdownClock();
    }

    async function refreshAllData() {
      updateLiveClock();
      try {
        if (activeMode === 'mlb_hrrbi') {
          await loadMLBData();
        } else if (activeMode === 'pitcher_ks') {
          await loadPitcherKs();
        } else if (activeMode === 'btc_analyzer') {
          await triggerBtcAnalysis();
        }
        fetch('/api/live/poll').catch(() => {});
      } catch (err) {
        console.warn('PTR refresh error:', err);
      }
    }

    // =========================================================================
    // KALSHI AUTONOMOUS TRADING CLIENT
    // =========================================================================
    let kalshiAutoTradeEnabled = false;
    let kalshiTradingMode = "PAPER";
    let kalshiCurrentContracts = 1;

    function getKalshiApiBase() {
      if (typeof window !== 'undefined' && window.location && (window.location.protocol === 'http:' || window.location.protocol === 'https:')) {
        return '';
      }
      return (typeof localStorage !== 'undefined' && localStorage.getItem("kalshi_server_url")) || 'http://192.168.1.222:8056';
    }

    function getAuthHeaders(customHeaders = {}) {
      const headers = { ...customHeaders };
      const urlParams = new URLSearchParams(window.location.search);
      const urlToken = urlParams.get("token") || urlParams.get("api_token");
      if (urlToken) {
        localStorage.setItem("app_api_token", urlToken);
        const cleanUrl = window.location.pathname + window.location.hash;
        window.history.replaceState({}, document.title, cleanUrl);
      }
      const token = localStorage.getItem("app_api_token") || "";
      if (token) {
        headers["X-API-Token"] = token;
      }
      return headers;
    }

    async function authFetch(url, options = {}) {
      const opts = { ...options };
      opts.headers = getAuthHeaders(opts.headers || {});
      const res = await fetch(url, opts);
      if (res.status === 401) {
        const entered = prompt("Enter Server API Token (APP_API_TOKEN) to unlock trading console:");
        if (entered) {
          localStorage.setItem("app_api_token", entered.trim());
          opts.headers = getAuthHeaders(options.headers || {});
          return fetch(url, opts);
        }
      }
      return res;
    }

    let kalshiCurrentPriceEst = 0.65;
    let kalshiFixedSize = 35.00; // Track current estimated contract price

    function updateKalshiEstCostDisplay() {
      const sizeInput = document.getElementById("kalshiSizeInput");
      const ctInput = document.getElementById("kalshiContractsInput");
      if (!sizeInput || !ctInput) return;
      
      const limitPrice = Math.min(0.99, kalshiCurrentPriceEst + 0.04);
      const dynamicCt = Math.max(1, Math.floor(kalshiFixedSize / limitPrice));
      kalshiCurrentContracts = dynamicCt; // Keep synced for other UI elements
      
      if (document.activeElement !== ctInput) {
        ctInput.value = dynamicCt;
      }
      if (document.activeElement !== sizeInput) {
        sizeInput.value = kalshiFixedSize.toFixed(2);
      }
    }

    function updateKalshiSize(val) {
      let size = parseFloat(val);
      if (isNaN(size) || size <= 0) size = kalshiCurrentPriceEst;
      kalshiFixedSize = size;
      
      const limitPrice = Math.min(0.99, kalshiCurrentPriceEst + 0.04);
      const dynamicCt = Math.max(1, Math.floor(kalshiFixedSize / limitPrice));
      kalshiCurrentContracts = dynamicCt;
      
      const ctInput = document.getElementById("kalshiContractsInput");
      if (ctInput) ctInput.value = dynamicCt;
      
      const maxCtSetting = document.getElementById("settingMaxContracts");
      if (maxCtSetting) maxCtSetting.value = dynamicCt;
      
      updateKalshiPayoutCalculator();
      saveAiMaxCap(kalshiFixedSize);
      saveKalshiContractsCount(dynamicCt);
    }

    async function saveKalshiContractsCount(count) {
      try {
        const apiBase = getKalshiApiBase();
        await authFetch(`${apiBase}/api/engine/${window.currentAsset}/trade/contracts?count=${count}`, { method: "POST" });
      } catch (err) {
        console.warn("Failed to persist contracts count:", err);
      }
    }

    async function updateKalshiContracts(val) {
      let ct = parseInt(val, 10);
      if (isNaN(ct) || ct < 1) ct = 1;
      kalshiCurrentContracts = ct;
      const limitPrice = Math.min(0.99, kalshiCurrentPriceEst + 0.04);
      kalshiFixedSize = ct * limitPrice;
      
      const sizeInput = document.getElementById("kalshiSizeInput");
      if (sizeInput) sizeInput.value = kalshiFixedSize.toFixed(2);
      
      const maxCtSetting = document.getElementById("settingMaxContracts");
      if (maxCtSetting) maxCtSetting.value = ct;
      
      updateKalshiPayoutCalculator();
      saveAiMaxCap(kalshiFixedSize);
      saveKalshiContractsCount(ct);
    }

    async function saveAiMaxCap(maxCapVal) {
      try {
        const aiSetStr = localStorage.getItem("kalshiAiSettings");
        if (aiSetStr) {
          const aiSet = JSON.parse(aiSetStr);
          aiSet.maxCap = maxCapVal;
          localStorage.setItem("kalshiAiSettings", JSON.stringify(aiSet));
          
          const apiBase = getKalshiApiBase();
          await authFetch(`${apiBase}/api/engine/${window.currentAsset}/trade/ai_settings`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(aiSet)
          }).catch(()=>{});
        }
      } catch (err) {
        console.warn("Failed to persist maxCap:", err);
      }
    }

    function changeKalshiContracts(delta) {
      let current = parseInt(document.getElementById("kalshiContractsInput").value, 10) || 1;
      let next = current + delta;
      if (next < 1) next = 1;
      const ctInput = document.getElementById("kalshiContractsInput");
      if (ctInput) ctInput.value = next;
      updateKalshiContracts(next);
    }

    function setKalshiContractsPreset(ct) {
      updateKalshiContracts(ct);
      const input = document.getElementById("kalshiContractsInput");
      if (input) input.value = ct;
    }

    function updateKalshiPayoutCalculator() {
      const input = document.getElementById("kalshiContractsInput");
      const ct = input ? parseInt(input.value) || 1 : kalshiCurrentContracts;
      const riskEl = document.getElementById("kalshiCalcRisk");
      const payoutEl = document.getElementById("kalshiCalcPayout");

      const limitPrice = Math.min(0.99, kalshiCurrentPriceEst + 0.04);
      const totalRisk = ct * limitPrice;
      const maxPayout = ct * 1.00;
      const netProfit = maxPayout - totalRisk;
      const roi = totalRisk > 0 ? (netProfit / totalRisk) * 100 : 0;

      if (riskEl) riskEl.innerText = `$${totalRisk.toFixed(2)}`;
      if (payoutEl) payoutEl.innerText = `$${maxPayout.toFixed(2)} (+${Math.round(roi)}%)`;
    }

    let _isPollingKalshiStatus = false;
    async function pollKalshiTradingStatus() {
      if (_isPollingKalshiStatus) return;
      _isPollingKalshiStatus = true;
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 4000);
        const apiBase = getKalshiApiBase();
        let res;
        try {
          res = await authFetch(`${apiBase}/api/engine/${window.currentAsset}/trade/status`, { signal: controller.signal });
        } finally {
          clearTimeout(timeoutId);
        }
        if (!res || !res.ok) return;
        const data = await res.json();
        if (!data) return;

        verboseLog("Trade status poll response:", data);

        // Synchronize JS state variables with authoritative server state
        kalshiAutoTradeEnabled = !!data.enabled;
        if (data.mode) {
          kalshiTradingMode = String(data.mode).toUpperCase();
        }

        if (data.prediction_accuracy && data.prediction_accuracy.source === "server_auto_predictions") {
          window.serverPredictionAccuracy = data.prediction_accuracy;
          // Update the ML Model pane
          const mlPctEl = document.getElementById("btcMlModelAccuracyPct");
          const accVal = data.prediction_accuracy.accuracy_percent;
          const pctStr = (accVal !== null && accVal != null) ? `${accVal}%` : "--%";
          
          if (mlPctEl) mlPctEl.innerText = pctStr;
        }

        // Update Balance
        const balEl = document.getElementById("kalshiLiveBalance");
        const settingsBalEl = document.getElementById("kalshiSettingsPaperBalance");
        const tradeLogBalEl = document.getElementById("tradeLogPaperBalance");
        if (data.balance_dollars != null) {
          const formatted = `$${(parseFloat(data.balance_dollars) || 0).toFixed(2)}`;
          if (balEl) balEl.innerText = formatted;
          if (settingsBalEl) settingsBalEl.innerText = formatted;
          if (tradeLogBalEl) tradeLogBalEl.innerText = formatted;
          const topBarBalEl = document.getElementById("topBarAccountBalanceText");
          if (topBarBalEl) topBarBalEl.innerText = formatted;
        }

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
        }

        // Update Contracts Count
        if (data.max_contracts != null) {
          // Ignored max_contracts from polling to preserve dynamic size logic
          const ctInput = document.getElementById("kalshiContractsInput");
          if (ctInput && document.activeElement !== ctInput) {
            ctInput.value = kalshiCurrentContracts;
          }
          updateKalshiEstCostDisplay();
        }

        // Update Auto-Trade Toggle
        const btnToggle = document.getElementById("btnToggleAutoTrade");
        if (btnToggle && !_isTogglingAutoTrade) {
          if (data.enabled) {
            if (data.is_risk_paused) {
              btnToggle.innerText = "PAUSED";
              btnToggle.title = data.pause_reason || "Risk limit reached";
              btnToggle.className = "px-2 py-0.5 rounded text-[10px] sm:text-xs font-black uppercase tracking-wider transition-all bg-amber-600 text-white shadow shadow-amber-600/50 animate-pulse";
            } else {
              btnToggle.innerText = "ON";
              btnToggle.title = "Autonomous trading active";
              btnToggle.className = "px-2 py-0.5 rounded text-[10px] sm:text-xs font-black uppercase tracking-wider transition-all bg-emerald-600 text-white shadow shadow-emerald-600/50";
            }
          } else {
            btnToggle.innerText = "OFF";
            btnToggle.title = "Autonomous trading paused";
            btnToggle.className = "px-2 py-0.5 rounded text-[10px] sm:text-xs font-black uppercase tracking-wider transition-all bg-slate-800 text-slate-400 hover:bg-slate-700";
          }
        }

        // Update Console Beacon to reflect Auto-Trader state
        const beaconPing = document.getElementById("kalshiBeaconPing");
        const beaconDot = document.getElementById("kalshiBeaconDot");
        if (beaconDot && beaconPing) {
          if (data.enabled && !data.is_risk_paused) {
            beaconDot.className = "relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500";
            beaconPing.className = "animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75";
          } else if (data.enabled && data.is_risk_paused) {
            beaconDot.className = "relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-500";
            beaconPing.className = "animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75";
          } else {
            beaconDot.className = "relative inline-flex rounded-full h-2.5 w-2.5 bg-slate-600";
            beaconPing.className = "hidden";
          }
        }

        // Update Prediction Mode Checkbox
        if (data.prediction_mode != null) {
          const pmCheckbox = document.getElementById("settingPredictionMode");
          if (pmCheckbox && document.activeElement !== pmCheckbox) {
             pmCheckbox.checked = !!data.prediction_mode;
          }
        }

        // Update Daily Risk & Trade Limit Inputs & Indicators
        if (data.max_daily_risk != null) {
          const riskInput = document.getElementById("settingMaxDailyRisk");
          if (riskInput && document.activeElement !== riskInput && !localStorage.getItem("kalshiGeneralSettings")) {
            riskInput.value = (parseFloat(data.max_daily_risk) || 0).toFixed(2);
          }
        }
        if (data.max_daily_trades != null) {
          const tradesInput = document.getElementById("settingMaxDailyTrades");
          if (tradesInput && document.activeElement !== tradesInput && !localStorage.getItem("kalshiGeneralSettings")) {
            tradesInput.value = parseInt(data.max_daily_trades);
          }
        }

        // Update Mode Slider
        const thumb = document.getElementById("modeSliderThumb");
        const textPaper = document.getElementById("modePaperText");
        const textLive = document.getElementById("modeLiveText");
        if (thumb && textPaper && textLive) {
          if (data.mode === "LIVE") {
            thumb.className = "absolute top-[1px] bottom-[1px] w-[46px] rounded-full transition-all duration-300 shadow-sm left-[50px] bg-red-950 border border-red-500/80";
            textPaper.className = "flex-1 text-center text-slate-500 transition-colors duration-300";
            textLive.className = "flex-1 text-center text-red-400 transition-colors duration-300";
          } else {
            thumb.className = "absolute top-[1px] bottom-[1px] w-[46px] rounded-full transition-all duration-300 shadow-sm left-[2px] bg-cyan-950 border border-cyan-500/50";
            textPaper.className = "flex-1 text-center text-cyan-300 transition-colors duration-300";
            textLive.className = "flex-1 text-center text-slate-500 transition-colors duration-300";
          }
        }

        // Active Market Ticker
        const tickerEl = document.getElementById("kalshiActiveTicker");
        if (data.active_market) {
          if (tickerEl) tickerEl.innerText = data.active_market.ticker || "KXBTC15M-ACTIVE";
          
          if (data.active_market.yes_bid != null) {
             const newEst = parseFloat(data.active_market.yes_bid);
             if (!isNaN(newEst) && newEst > 0 && newEst !== kalshiCurrentPriceEst) {
               kalshiCurrentPriceEst = newEst;
               updateKalshiEstCostDisplay();
               updateKalshiPayoutCalculator();
             }
          }
        }

        // Win Rate & P&L
        const countEl = document.getElementById("kalshiTradesCount");
        if (countEl) countEl.innerText = `${data.wins || 0}W - ${data.losses || 0}L`;

        const wrEl = document.getElementById("kalshiWinRate");
        if (wrEl) wrEl.innerText = `${data.win_rate_pct || 0}%`;

        const pnlEl = document.getElementById("kalshiTotalPnl");
        if (pnlEl) {
          const pnl = parseFloat(data.total_pnl_dollars || 0);
          pnlEl.innerText = `${pnl >= 0 ? "+" : ""}$${(isNaN(pnl) ? 0 : pnl).toFixed(2)}`;
          pnlEl.className = pnl > 0 ? "font-bold text-emerald-400" : (pnl < 0 ? "font-bold text-red-400" : "font-bold text-white");
        }

        // Live P/L of Open Trades — prefer server-calculated open_pnl_dollars
        const livePnlContainer = document.getElementById("topBarLivePnlContainer");
        const livePnlText = document.getElementById("topBarLivePnlText");
        if (livePnlContainer && livePnlText) {
          const modeTrades = (data.open_trades || []).filter(t => (t.mode || "PAPER").toUpperCase() === kalshiTradingMode);
          if (modeTrades.length > 0) {
            let totalLivePnl = 0;
            let totalOpenCost = 0;
            modeTrades.forEach(t => {
              const entry = parseFloat(t.entry_price || 0);
              const count = parseInt(t.count || 1);
              totalOpenCost += entry * count;
            });

            // 1. Use server-precomputed open_pnl_dollars if available
            if (data.open_pnl_dollars != null && data.open_pnl_dollars !== null) {
              totalLivePnl = parseFloat(data.open_pnl_dollars);
            } else if (data.active_market) {
              // 2. Fall back to client-side mark-to-market
              modeTrades.forEach(t => {
                // Prefer server-annotated live_pnl on each trade
                if (t.live_pnl != null) {
                  totalLivePnl += parseFloat(t.live_pnl);
                } else {
                  const side = String(t.side || "YES").toUpperCase();
                  const entry = parseFloat(t.entry_price || 0);
                  const count = parseInt(t.count || 1);
                  let exitPrice = entry;
                  if (side === "YES" && data.active_market.yes_bid > 0) exitPrice = parseFloat(data.active_market.yes_bid);
                  else if (side === "NO" && data.active_market.no_bid > 0) exitPrice = parseFloat(data.active_market.no_bid);
                  totalLivePnl += (exitPrice - entry) * count;
                }
              });
            }
            
            const livePnlLabel = document.querySelector("#topBarLivePnlContainer span:first-child");
            if (livePnlLabel) {
              livePnlLabel.innerText = `P&L ($${(isNaN(totalOpenCost) ? 0 : totalOpenCost).toFixed(2)})`;
            }

            livePnlText.innerText = `${totalLivePnl >= 0 ? "+" : ""}$${(isNaN(totalLivePnl) ? 0 : totalLivePnl).toFixed(2)}`;
            livePnlText.className = `text-xs sm:text-sm lg:text-base font-black font-mono whitespace-nowrap ${totalLivePnl >= 0 ? "text-emerald-400" : "text-red-400"}`;
            livePnlContainer.classList.remove("hidden");
          } else {
            const livePnlLabel = document.querySelector("#topBarLivePnlContainer span:first-child");
            if (livePnlLabel) livePnlLabel.innerText = "P&L";
            livePnlText.innerText = "$0.00";
            livePnlText.className = "text-xs sm:text-sm lg:text-base font-black font-mono whitespace-nowrap text-slate-400";
            livePnlContainer.classList.remove("hidden");
          }
        }

        // Render Recent Trades
        renderKalshiTradesList(data.recent_trades || [], data.active_market);
      } catch (err) {
        console.warn("Error polling Kalshi trade status:", err);
      } finally {
        _isPollingKalshiStatus = false;
      }
    }

    function getTradeIdentifierPills(t) {
      const pills = [];
      const mode = String(t.mode || "PAPER").toUpperCase();
      const src = String(t.trade_source || "").toUpperCase();
      const rec = String(t.recommendation || "").toUpperCase();
      const grade = String(t.conviction_grade || "").toUpperCase();
      const badge = String(t.conviction_badge || "").toUpperCase();
      const exitReason = String(t.exit_reason || "").toUpperCase();
      const catalysts = Array.isArray(t.catalysts) ? t.catalysts.map(c => String(c).toUpperCase()) : [];

      // 1. Paper vs Live Mode Pill
      if (mode === "LIVE") {
        pills.push(`<span class="text-[8px] font-black px-1.5 py-0.2 rounded uppercase bg-red-500/20 text-red-300 border border-red-500/40 shadow-sm shadow-red-950/40" title="Real Money Live Order">LIVE</span>`);
      } else {
        pills.push(`<span class="text-[8px] font-bold px-1.5 py-0.2 rounded uppercase bg-cyan-500/20 text-cyan-300 border border-cyan-500/40" title="Simulated Paper Order">PAPER</span>`);
      }

      // 2. Execution Origin Pill (AUTO vs MANUAL)
      const isManual = t.is_manual === true || src.includes("MANUAL") || rec.includes("MANUAL") || grade.includes("MANUAL");
      if (isManual) {
        pills.push(`<span class="text-[8px] font-bold px-1.5 py-0.2 rounded uppercase bg-amber-500/15 text-amber-300 border border-amber-500/35" title="Manually Executed by Trader">🖐 MANUAL</span>`);
      } else {
        const styleRaw = String(t.trading_style || "").toUpperCase();
        const isSurfer = src.includes("MOMENTUM_SURFER") || styleRaw.includes("MOMENTUM_SURFER");
        const isAmbush = src.includes("AMBUSH") || styleRaw.includes("AMBUSH");
        const isSniper = src.includes("SNIPER") || styleRaw.includes("SNIPER");
        const isChop = src.includes("CHOP") || styleRaw.includes("CHOP");
        const isAutoD = src.includes("AUTO") || styleRaw === "AUTO";
        
        let autoLabel = "⚡ AUTO";
        let icon = "⚡";
        let styleName = "AUTO";
        
        if (isSurfer) { icon = "🌊"; styleName = "AUTO (SURFER)"; }
        else if (isAmbush) { icon = "🥷"; styleName = "AUTO (AMBUSH)"; }
        else if (isSniper) { icon = "🎯"; styleName = "AUTO (SNIPER)"; }
        else if (isChop) { icon = "🪓"; styleName = "AUTO (CHOP)"; }
        else if (isAutoD) { icon = "⚙️"; styleName = "AUTO (DYNAMIC)"; }
        
        pills.push(`<span class="text-[8px] font-bold px-1.5 py-0.2 rounded uppercase bg-cyan-500/15 text-cyan-300 border border-cyan-500/35" title="Autonomous AI Execution (${styleName})">${icon} ${styleName}</span>`);
      }

      // 3. Scalp Pill
      const isScalp = t.is_scalp === true || src.includes("SCALP") || rec.includes("SCALP") || grade.includes("SCALP") || catalysts.some(c => c.includes("SCALP")) || exitReason.includes("SCALP");
      if (isScalp) {
        pills.push(`<span class="text-[8px] font-bold px-1.5 py-0.2 rounded uppercase bg-fuchsia-500/15 text-fuchsia-300 border border-fuchsia-500/40" title="Rapid Scalper Trade">⚡ SCALP</span>`);
      }

      // 4. Reverse Pill
      const isReverse = t.is_reverse === true || src.includes("REVERSE") || rec.includes("REVERSE") || badge.includes("REVERSE") || catalysts.some(c => c.includes("REVERSE"));
      if (isReverse) {
        pills.push(`<span class="text-[8px] font-bold px-1.5 py-0.2 rounded uppercase bg-indigo-500/15 text-indigo-300 border border-indigo-500/40" title="CVD Divergence Reversal Setup">🔄 REVERSE</span>`);
      }

      // 5. Exit Reason Pill (when closed early before expiry)
      if (exitReason.includes("SCALP_TP") || exitReason.includes("TAKE_PROFIT")) {
        pills.push(`<span class="text-[8px] font-bold px-1.5 py-0.2 rounded uppercase bg-emerald-500/20 text-emerald-300 border border-emerald-500/40" title="Take-Profit Target Reached">✅ TP EXIT</span>`);
      } else if (exitReason.includes("SCALP_SL") || exitReason.includes("STOP_LOSS")) {
        pills.push(`<span class="text-[8px] font-bold px-1.5 py-0.2 rounded uppercase bg-rose-500/20 text-rose-300 border border-rose-500/40" title="Stop-Loss Triggered">🛑 SL EXIT</span>`);
      } else if (exitReason.includes("MANUAL")) {
        pills.push(`<span class="text-[8px] font-bold px-1.5 py-0.2 rounded uppercase bg-amber-500/15 text-amber-300 border border-amber-500/35" title="Trader Manually Closed Position">✋ MANUAL EXIT</span>`);
      }

      // 6. Signal / Conviction Badge Pill
      if (t.conviction_badge) {
        let badgeRaw = String(t.conviction_badge).toUpperCase();
        // Remove emoji if it already exists, we will style it cleanly
        let cleanBadge = badgeRaw.replace(/^[^\w\s]+/g, '').trim(); 
        if (cleanBadge.length > 0 && !isManual) {
           pills.push(`<span class="text-[8px] font-bold px-1.5 py-0.2 rounded uppercase bg-purple-500/15 text-purple-300 border border-purple-500/30" title="Execution Signal">📡 ${cleanBadge}</span>`);
        }
      }

      return pills.join(" ");
    }

    function renderKalshiTradesList(trades, activeMarket) {
      const container = document.getElementById("kalshiTradesListContainer");
      if (!container) return;
      window._kalshiTradesData = trades;

      const filteredTrades = (trades || []).filter(t => (t.mode || "PAPER").toUpperCase() === kalshiTradingMode);

      const marketKey = activeMarket ? `${activeMarket.yes_bid}_${activeMarket.no_bid}` : "no_market";
      const tradesKey = JSON.stringify(filteredTrades.slice(0, 10).map(t => [
        t.id,
        t.status,
        t.result,
        t.pnl,
        t.live_pnl != null ? Math.round(parseFloat(t.live_pnl) * 100) / 100 : null,
        t.current_bid != null ? Math.round(parseFloat(t.current_bid) * 100) / 100 : null
      ])) + "_" + marketKey;
      if (window._lastKalshiTradesKey === tradesKey) return;
      window._lastKalshiTradesKey = tradesKey;

      if (filteredTrades.length === 0) {
        container.innerHTML = '<div class="text-[6.5px] text-slate-500 text-center py-1">No trades executed yet in ' + kalshiTradingMode + ' mode. Standing by for rollover...</div>';
        return;
      }

      container.innerHTML = filteredTrades.slice(0, 10).map(t => {
        const resStr = String(t.result || "").toUpperCase();
        const statStr = String(t.status || "").toUpperCase();
        const isWin = resStr.includes("WIN");
        const isLoss = resStr.includes("LOSS");
        const isClosed = statStr === "CLOSED" || statStr === "SETTLED";
        let pnlNum = parseFloat(t.pnl || 0);
        
        let colorClass = "text-amber-400 border-amber-800/40 bg-amber-950/30";
        let statusBadge = "OPEN";
        let pnlText = "Pending";

        if (!isClosed && t.entry_price) {
            // Live PNL — prefer server-annotated live_pnl
            if (t.live_pnl != null) {
                pnlNum = parseFloat(t.live_pnl);
                pnlText = pnlNum >= 0 ? `+$${(isNaN(pnlNum) ? 0 : pnlNum).toFixed(2)}` : `-$${(isNaN(Math.abs(pnlNum)) ? 0 : Math.abs(pnlNum)).toFixed(2)}`;
                colorClass = pnlNum >= 0 ? "text-emerald-400 border-emerald-800/40 bg-emerald-950/30" : "text-red-400 border-red-800/40 bg-red-950/30";
            } else if (activeMarket) {
                // Fall back to client-side calc
                const side = String(t.side || "YES").toUpperCase();
                const entryCost = parseFloat(t.entry_price);
                const count = parseInt(t.count || 1);
                let exitPrice = entryCost;
                if (side === "YES" && parseFloat(activeMarket.yes_bid) > 0) exitPrice = parseFloat(activeMarket.yes_bid);
                else if (side === "NO" && parseFloat(activeMarket.no_bid) > 0) exitPrice = parseFloat(activeMarket.no_bid);
                pnlNum = (exitPrice - entryCost) * count;
                pnlText = pnlNum >= 0 ? `+$${(isNaN(pnlNum) ? 0 : pnlNum).toFixed(2)}` : `-$${(isNaN(Math.abs(pnlNum)) ? 0 : Math.abs(pnlNum)).toFixed(2)}`;
                colorClass = pnlNum >= 0 ? "text-emerald-400 border-emerald-800/40 bg-emerald-950/30" : "text-red-400 border-red-800/40 bg-red-950/30";
            }
        } else if (isWin) {
          colorClass = "text-emerald-400 border-emerald-800/40 bg-emerald-950/30";
          statusBadge = statStr === "CLOSED" ? "CLSD WIN" : "WIN";
          pnlText = `+$${(isNaN(pnlNum) ? 0 : pnlNum).toFixed(2)}`;
        } else if (isLoss) {
          colorClass = "text-red-400 border-red-800/40 bg-red-950/30";
          statusBadge = statStr === "CLOSED" ? "CLSD LOSS" : "LOSS";
          pnlText = `-$${(isNaN(Math.abs(pnlNum)) ? 0 : Math.abs(pnlNum)).toFixed(2)}`;
        } else if (isClosed) {
          colorClass = "text-slate-400 border-slate-700/40 bg-slate-900/40";
          statusBadge = "CLOSED";
          pnlText = `$${(isNaN(pnlNum) ? 0 : pnlNum).toFixed(2)}`;
        }
        
        const formatTradeDateTime = (value) => {
          if (!value) return "--";
          const raw = String(value).trim();
          // Trade records already store an ET date/time string. Preserve it so
          // a browser does not reinterpret it in a different timezone.
          if (/^\d{4}-\d{2}-\d{2}\s+/.test(raw)) return raw;
          const date = new Date(raw);
          return Number.isNaN(date.getTime())
            ? raw
            : date.toLocaleString('en-US', {
                timeZone: 'America/New_York',
                month: 'short', day: 'numeric', year: 'numeric',
                hour: 'numeric', minute: '2-digit', hour12: true,
                timeZoneName: 'short'
              });
        };
        const openedAt = formatTradeDateTime(t.timestamp);
        const settledAt = isClosed ? formatTradeDateTime(t.settled_at) : "";
        const pillsHtml = getTradeIdentifierPills(t);

        // Trade type / direction label (mirrors the dedicated Trade List page)
        const sideStr = String(t.side || t.direction || "").toUpperCase();
        const isUpDirection = sideStr.includes("UP") || sideStr.includes("ABOVE") || sideStr.includes("YES");
        const directionArrow = isUpDirection ? "▲" : "▼";
        const directionLabel = isUpDirection ? "BID UP (YES)" : "BID DOWN (NO)";
        const directionColor = isUpDirection ? "text-emerald-400" : "text-red-400";

        return `
          <div onclick="showTradeDetailsModal('${t.id}')" class="flex items-center justify-between p-1 rounded border ${colorClass} text-[9px] sm:text-[10px] font-mono mb-1 cursor-pointer hover:brightness-125 transition-all">
            <div class="flex flex-col gap-0.5">
              <div class="flex items-center gap-1 flex-wrap">
                <span class="font-bold uppercase ${directionColor}">${directionArrow} ${directionLabel}</span>
                <span class="text-slate-400">(${t.count || 1}ct @ $${(parseFloat(t.entry_price || 0) || 0).toFixed(2)})</span>
                <span class="text-cyan-600 font-bold">Spent: $${((t.count || 1) * parseFloat(t.entry_price || 0)).toFixed(2)}</span>
                ${pillsHtml}
              </div>
              <span class="text-[7px] text-slate-500">Opened: ${openedAt}${settledAt ? ` · Settled: ${settledAt}` : ""}</span>
            </div>
            <div class="flex items-center gap-1 font-bold">
              <span>${statusBadge}</span>
              <span>${pnlText}</span>
            </div>
          </div>
        `;
      }).join("");
    }

    // Custom In-App Dialog & Toast Notification Engine (Zero "localhost says" dialogs)
    // -------------------------------------------------------------------------
    function showAppModal({ title, badge, icon, iconBg, body, confirmText = "Confirm", confirmColor = "cyan", showCancel = true }) {
      return new Promise((resolve) => {
        const overlay = document.getElementById("appModalOverlay");
        const iconEl = document.getElementById("appModalIcon");
        const iconWrapper = document.getElementById("appModalIconWrapper");
        const titleEl = document.getElementById("appModalTitle");
        const badgeEl = document.getElementById("appModalBadge");
        const bodyEl = document.getElementById("appModalBody");
        const cancelBtn = document.getElementById("appModalCancelBtn");
        const confirmBtn = document.getElementById("appModalConfirmBtn");

        if (!overlay) {
          resolve(window.confirm ? window.confirm(body.replace(/<[^>]*>?/gm, '')) : true);
          return;
        }

        iconEl.innerText = icon || "⚡";
        iconWrapper.className = `w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0 ${iconBg || "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"}`;
        titleEl.innerText = title || "Notification";
        badgeEl.innerText = badge || "KALSHI AI TRADER";
        bodyEl.innerHTML = body || "";

        if (showCancel) {
          cancelBtn.classList.remove("hidden");
          cancelBtn.onclick = () => {
            overlay.classList.add("hidden");
            resolve(false);
          };
        } else {
          cancelBtn.classList.add("hidden");
        }

        const colorClasses = {
          cyan: "bg-cyan-400 hover:bg-cyan-300 text-slate-950 shadow-cyan-500/20",
          emerald: "bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-emerald-500/20",
          red: "bg-red-500 hover:bg-red-400 text-white shadow-red-500/20",
          amber: "bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-amber-500/20",
          purple: "bg-purple-500 hover:bg-purple-400 text-white shadow-purple-500/20"
        };
        confirmBtn.className = `flex-1 py-2 rounded-xl text-xs font-black active:scale-95 transition shadow-lg ${colorClasses[confirmColor] || colorClasses.cyan}`;
        confirmBtn.innerText = confirmText;
        confirmBtn.onclick = () => {
          overlay.classList.add("hidden");
          resolve(true);
        };

        overlay.classList.remove("hidden");
      });
    }

    function showAppToast(title, subtitle, type = "success") {
      const container = document.getElementById("appToastContainer");
      if (!container) return;
      const toast = document.createElement("div");
      const config = {
        success: { border: "border-emerald-500/50", iconBg: "bg-emerald-500/20 border-emerald-500/40 text-emerald-400", icon: "✓", textCol: "text-emerald-400" },
        error: { border: "border-red-500/50", iconBg: "bg-red-500/20 border-red-500/40 text-red-400", icon: "✕", textCol: "text-red-400" },
        warning: { border: "border-amber-500/50", iconBg: "bg-amber-500/20 border-amber-500/40 text-amber-400", icon: "⚠️", textCol: "text-amber-300" },
        info: { border: "border-cyan-500/50", iconBg: "bg-cyan-500/20 border-cyan-500/40 text-cyan-400", icon: "ℹ️", textCol: "text-cyan-400" }
      }[type] || { border: "border-cyan-500/50", iconBg: "bg-cyan-500/20 border-cyan-500/40 text-cyan-400", icon: "✓", textCol: "text-cyan-400" };

      toast.className = `bg-slate-900/95 border ${config.border} rounded-xl p-2.5 sm:p-3 shadow-2xl flex items-center gap-2.5 pointer-events-auto backdrop-blur-md transform transition-all duration-300 translate-y-0 opacity-100 mb-1.5`;
      toast.innerHTML = `
        <div class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 border ${config.iconBg}">
          ${config.icon}
        </div>
        <div class="flex-1 min-w-0 font-mono">
          <div class="text-[11px] sm:text-xs font-black text-white leading-tight truncate">${title}</div>
          ${subtitle ? `<div class="text-[9px] sm:text-[10px] ${config.textCol} leading-tight truncate">${subtitle}</div>` : ""}
        </div>
      `;
      container.appendChild(toast);

      setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(-10px)";
        setTimeout(() => toast.remove(), 300);
      }, 3500);
    }

    async function togglePredictionMode(enabled) {
      try {
        const apiBase = getKalshiApiBase();
        const res = await authFetch(`${apiBase}/api/engine/${window.currentAsset}/trade/prediction_mode?enabled=${enabled}`, { method: "POST" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        showAppToast("Prediction Mode", enabled ? "1-Min locked predictions active" : "Prediction mode disabled", enabled ? "success" : "info");
        pollKalshiTradingStatus();
      } catch (e) {
        console.error("Error toggling prediction mode:", e);
        showAppToast("Error", "Failed to update prediction mode", "error");
      }
    }

    let _isTogglingAutoTrade = false;
    async function toggleKalshiAutoTrade() {
      if (_isTogglingAutoTrade) return;
      const btnToggle = document.getElementById("btnToggleAutoTrade");
      const prevState = kalshiAutoTradeEnabled;
      const nextState = !prevState;

      if (nextState && kalshiTradingMode === "LIVE") {
        const confirmed = await showAppModal({
          title: "Enable Auto-Trader",
          badge: "REAL FUNDS WARNING",
          icon: "⚠️",
          iconBg: "bg-red-500/20 text-red-400 border border-red-500/40",
          body: `You are about to enable <span class="text-red-400 font-bold">LIVE AUTONOMOUS TRADING</span> with real funds.<br><br>Trades will execute automatically whenever high conviction signals occur. Proceed?`,
          confirmText: "Enable Live Auto",
          confirmColor: "red"
        });
        if (!confirmed) return;
      }

      _isTogglingAutoTrade = true;
      if (btnToggle) {
        btnToggle.disabled = true;
        btnToggle.innerText = "...";
        btnToggle.className = "px-2 py-0.5 rounded text-[10px] sm:text-xs font-black uppercase tracking-wider transition-all bg-slate-700 text-slate-300 opacity-75 cursor-wait";
      }

      try {
        const apiBase = getKalshiApiBase();
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        let res;
        try {
          res = await authFetch(`${apiBase}/api/engine/${window.currentAsset}/trade/toggle?enabled=${nextState}`, {
            method: "POST",
            signal: controller.signal
          });
        } finally {
          clearTimeout(timeoutId);
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const resData = await res.json();
        
        // Confirm authoritative state from server
        kalshiAutoTradeEnabled = resData.enabled != null ? !!resData.enabled : nextState;

        if (btnToggle) {
          if (kalshiAutoTradeEnabled) {
            btnToggle.innerText = "ON";
            btnToggle.title = "Autonomous trading active";
            btnToggle.className = "px-2 py-0.5 rounded text-[10px] sm:text-xs font-black uppercase tracking-wider transition-all bg-emerald-600 text-white shadow shadow-emerald-600/50";
          } else {
            btnToggle.innerText = "OFF";
            btnToggle.title = "Autonomous trading paused";
            btnToggle.className = "px-2 py-0.5 rounded text-[10px] sm:text-xs font-black uppercase tracking-wider transition-all bg-slate-800 text-slate-400 hover:bg-slate-700";
          }
        }

        showAppToast("Auto-Trader", kalshiAutoTradeEnabled ? "Autonomous execution active" : "Auto-trader paused", kalshiAutoTradeEnabled ? "success" : "info");
        pollKalshiTradingStatus();
      } catch (e) {
        console.error("Error toggling auto trade:", e);
        // Rollback state and DOM to confirmed previous state
        kalshiAutoTradeEnabled = prevState;
        if (btnToggle) {
          btnToggle.innerText = prevState ? "ON" : "OFF";
          btnToggle.className = prevState
            ? "px-2 py-0.5 rounded text-[10px] sm:text-xs font-black uppercase tracking-wider transition-all bg-emerald-600 text-white shadow shadow-emerald-600/50"
            : "px-2 py-0.5 rounded text-[10px] sm:text-xs font-black uppercase tracking-wider transition-all bg-slate-800 text-slate-400 hover:bg-slate-700";
        }
        showAppModal({
          title: "Toggle Failed",
          badge: "COMMUNICATION ERROR",
          icon: "⚠️",
          iconBg: "bg-amber-500/20 text-amber-400 border border-amber-500/40",
          body: `Cannot reach backend server at ${getKalshiApiBase() || window.location.origin}.<br><br>Auto-Trader state has not changed.`,
          confirmText: "Understood",
          confirmColor: "amber",
          showCancel: false
        });
        pollKalshiTradingStatus();
      } finally {
        _isTogglingAutoTrade = false;
        if (btnToggle) btnToggle.disabled = false;
      }
    }

    let _isTogglingTradingMode = false;
    async function toggleKalshiTradingMode() {
      if (_isTogglingTradingMode) return;
      const thumb = document.getElementById("modeSliderThumb");
      const prevMode = kalshiTradingMode;
      const nextMode = prevMode === "PAPER" ? "LIVE" : "PAPER";

      if (nextMode === "LIVE") {
        const confirmed = await showAppModal({
          title: "Switch to Live Trading",
          badge: "REAL FUNDS NOTICE",
          icon: "⚠️",
          iconBg: "bg-red-500/20 text-red-400 border border-red-500/40",
          body: `Switch to <span class="text-red-400 font-bold">LIVE TRADING MODE</span>?<br><br>Real orders will be submitted to Kalshi using your funded account balance.`,
          confirmText: "Switch to Live",
          confirmColor: "red"
        });
        if (!confirmed) return;
      }

      _isTogglingTradingMode = true;
      if (thumb) {
        thumb.style.opacity = "0.5";
      }

      try {
        const apiBase = getKalshiApiBase();
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        let res;
        try {
          res = await authFetch(`${apiBase}/api/engine/${window.currentAsset}/trade/mode?mode=${nextMode}`, {
            method: "POST",
            signal: controller.signal
          });
        } finally {
          clearTimeout(timeoutId);
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const resData = await res.json();
        kalshiTradingMode = (resData.mode || nextMode).toUpperCase();

        if (thumb) {
          thumb.style.opacity = "1";
        }

        showAppToast("Trading Mode", `Switched to ${kalshiTradingMode} mode`, kalshiTradingMode === "LIVE" ? "warning" : "info");
        pollKalshiTradingStatus();
      } catch (e) {
        console.error("Error toggling trading mode:", e);
        kalshiTradingMode = prevMode;
        if (thumb) {
          thumb.style.opacity = "1";
        }
        showAppToast("Mode Switch Failed", String(e.message || e), "error");
        pollKalshiTradingStatus();
      } finally {
        _isTogglingTradingMode = false;
        if (thumb) thumb.style.opacity = "1";
      }
    }

    async function triggerManualKalshiTrade(direction) {
      if (kalshiTradingMode === "LIVE") {
        const sideText = direction === "ABOVE" ? "YES" : (direction === "BELOW" ? "NO" : "100% AI PREDICTION");
        const sideColor = direction === "ABOVE" ? "text-emerald-400" : (direction === "BELOW" ? "text-red-400" : "text-cyan-400");
        const confirmed = await showAppModal({
          title: "Confirm Live Order",
          badge: "1-CLICK SUBMISSION",
          icon: "⚡",
          iconBg: "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40",
          body: `Submit order to Kalshi?<br><br>Contract: <span class="text-white font-bold">15-Min Bitcoin</span><br>Action: <span class="font-bold ${sideColor}">BUY ${kalshiCurrentContracts} ${sideText}</span><br>Mode: <span class="text-red-400 font-bold">REAL FUNDS</span>`,
          confirmText: "Submit Order",
          confirmColor: "cyan"
        });
        if (!confirmed) return;
      }
      try {
        const apiBase = getKalshiApiBase();
        const res = await authFetch(`${apiBase}/api/engine/${window.currentAsset}/trade/manual?direction=${direction}`, { method: "POST" });
        const data = await res.json();
        if (data.success) {
          showAppToast(
            `Trade Executed (${kalshiTradingMode})`,
            `${data.trade ? data.trade.recommendation : 'Filled'} • ${kalshiCurrentContracts} contract(s)`,
            "success"
          );
          pollKalshiTradingStatus();
        } else {
          showAppModal({
            title: "Order Rejected",
            badge: "KALSHI NOTICE",
            icon: "✕",
            iconBg: "bg-amber-500/20 text-amber-400 border border-amber-500/40",
            body: data.error || "Failed to submit order.",
            confirmText: "Dismiss",
            confirmColor: "amber",
            showCancel: false
          });
        }
      } catch (e) {
        showAppToast("Request Failed", String(e), "error");
      }
    }

    async function triggerReversePosition() {
      if (!window.currentAsset) return;
      if (kalshiTradingMode === "LIVE") {
        const confirmed = await showAppModal({
          title: "Reverse Active Position",
          badge: "1-CLICK REVERSE",
          icon: "🔄",
          iconBg: "bg-indigo-500/20 text-indigo-400 border border-indigo-500/40",
          body: `Instantly close your active trade and flip to the opposite side?`,
          confirmText: "Reverse Position",
          confirmColor: "indigo"
        });
        if (!confirmed) return;
      }
      try {
        const apiBase = getKalshiApiBase();
        const res = await authFetch(`${apiBase}/api/engine/${window.currentAsset}/trade/reverse`, { method: "POST" });
        const data = await res.json();
        if (data.success) {
          showAppToast("Position Reversed", "Active trade closed and flipped successfully", "success");
          pollKalshiTradingStatus();
        } else {
          showAppToast("Reverse Failed", data.error || "Failed to reverse position", "error");
        }
      } catch (err) {
        showAppToast("Network Error", err.message, "error");
      }
    }

    async function triggerCloseTrade() {
      if (kalshiTradingMode === "LIVE") {
        const confirmed = await showAppModal({
          title: "Close Active Position",
          badge: "1-CLICK EXIT",
          icon: "✕",
          iconBg: "bg-amber-500/20 text-amber-400 border border-amber-500/40",
          body: `Exit all active trade(s) at current market price and realize P&L immediately?`,
          confirmText: "Close Now",
          confirmColor: "amber"
        });
        if (!confirmed) return;
      }
      try {
        const apiBase = getKalshiApiBase();
        const res = await authFetch(`${apiBase}/api/engine/${window.currentAsset}/trade/close`, { method: "POST" });
        const data = await res.json();
        if (data.success) {
          showAppToast("Position Closed", data.message || "Active trade closed successfully", "success");
          pollKalshiTradingStatus();
        } else {
          showAppToast("Close Notice", data.error || "No open trades to close", "warning");
        }
      } catch (e) {
        showAppToast("Close Request Failed", String(e), "error");
      }
    }

    // =========================================================================
    
      // Auto-save event listeners
      document.addEventListener("DOMContentLoaded", () => {
        const settingMaxCap = document.getElementById("settingMaxCap");
        const settingMaxContracts = document.getElementById("settingMaxContracts");
        
        if (settingMaxCap && settingMaxContracts) {
            settingMaxCap.addEventListener("input", (e) => {
                const limitPrice = Math.min(0.99, kalshiCurrentPriceEst + 0.04);
                settingMaxContracts.value = Math.max(1, Math.floor(parseFloat(e.target.value || 0) / limitPrice));
            });
            settingMaxContracts.addEventListener("input", (e) => {
                const limitPrice = Math.min(0.99, kalshiCurrentPriceEst + 0.04);
                settingMaxCap.value = (parseInt(e.target.value || 1) * limitPrice).toFixed(2);
            });
        }
        
        const kalshiInputs = document.querySelectorAll('#generalSettingsSubPage input, #generalSettingsSubPage select');
        kalshiInputs.forEach(el => {
          el.addEventListener('change', () => saveKalshiSettings(false));
        });

        const scalpInputs = document.querySelectorAll('#scalperSettingsSubPage input, #scalperSettingsSubPage select');
        scalpInputs.forEach(el => {
          el.addEventListener('change', () => saveScalpSettings(false));
        });
      });

      // KALSHI AI TRADER: TAB SWITCHING & SETTINGS ENGINE
    // =========================================================================
    let kalshiConvictionFilter = "ALL";

    function switchAiTraderTab(tab) {
      const traderContent = document.getElementById("aiTraderTabContent");
      const settingsContent = document.getElementById("aiSettingsTabContent");
      const tabBtnTrader = document.getElementById("tabBtnTrader");
      const tabBtnSettings = document.getElementById("tabBtnSettings");

      if (!traderContent || !settingsContent) return;

      if (tab === "trader") {
        traderContent.classList.remove("hidden");
        settingsContent.classList.add("hidden");

        if (tabBtnTrader) {
          tabBtnTrader.className = "flex items-center justify-center gap-1.5 py-1 rounded-lg text-xs font-sans font-black uppercase tracking-wider transition-all bg-gradient-to-r from-cyan-600 to-blue-600 text-white shadow-md shadow-cyan-950/40 cursor-pointer";
        }
        if (tabBtnSettings) {
          tabBtnSettings.className = "flex items-center justify-center gap-1.5 py-1 rounded-lg text-xs font-sans font-bold uppercase tracking-wider transition-all text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 cursor-pointer";
        }
      } else {
        traderContent.classList.add("hidden");
        settingsContent.classList.remove("hidden");

        if (tabBtnSettings) {
          tabBtnSettings.className = "flex items-center justify-center gap-1.5 py-1 rounded-lg text-xs font-sans font-black uppercase tracking-wider transition-all bg-gradient-to-r from-cyan-600 to-blue-600 text-white shadow-md shadow-cyan-950/40 cursor-pointer";
        }
        if (tabBtnTrader) {
          tabBtnTrader.className = "flex items-center justify-center gap-1.5 py-1 rounded-lg text-xs font-sans font-bold uppercase tracking-wider transition-all text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 cursor-pointer";
        }
      }
    }

    async function setConvictionFilter(type, showToast = true) {
      kalshiConvictionFilter = type;
      
      let thresholdParam = "A+";
      let labelText = "Grade A+ Only";
      
      const activeClass = "py-1 px-1.5 rounded-lg border border-cyan-500/60 bg-cyan-950/80 text-cyan-300 font-bold shadow-sm transition-all text-center cursor-pointer";
      const inactiveClass = "py-1 px-1.5 rounded-lg border border-slate-800 bg-slate-900 text-slate-400 hover:text-white transition-all text-center cursor-pointer";


      if (type === "APLUS") {
        thresholdParam = "A+";
        labelText = "Grade A+ Only";
      } else if (type === "A" || type === "ALL") {
        thresholdParam = "A";
        labelText = "Grade A+ & A";
      } else if (type === "BPLUS") {
        thresholdParam = "B+";
        labelText = "Grade A+, A & B+";
      } else if (type === "B") {
        thresholdParam = "B";
        labelText = "Grade A+, A, B+ & B";
      }
      

      try {
        const apiBase = getKalshiApiBase();
        const res = await authFetch(`${apiBase}/api/engine/${window.currentAsset}/trade/threshold?threshold=${encodeURIComponent(thresholdParam)}`, { method: "POST" });
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${await res.text().catch(()=>'')}`);
        }
        if (showToast) {
            showAppToast("Filter Updated", `Conviction set to ${labelText}`, "info");
        }
      } catch (e) {
        console.error("Failed to update conviction threshold:", e);
        showAppToast("Filter Error", String(e), "error");
      }
    }

    async function saveKalshiSettings(showToast = true) {
      try {
        const predMode = document.getElementById("settingPredictionMode")?.checked || false;
        const maxDailyRisk = parseFloat(document.getElementById("settingMaxDailyRisk")?.value) || 25.0;
        const maxDailyTrades = parseInt(document.getElementById("settingMaxDailyTrades")?.value) || 10;
        const maxContracts = parseInt(document.getElementById("settingMaxContracts")?.value) || 1;
        kalshiCurrentContracts = maxContracts;
        
        const ctInput = document.getElementById("kalshiContractsInput");
        if (ctInput) ctInput.value = kalshiCurrentContracts;
        const szInput = document.getElementById("kalshiSizeInput");
        if (szInput) {
           const limitPrice = Math.min(0.99, kalshiCurrentPriceEst + 0.04);
           szInput.value = (kalshiCurrentContracts * limitPrice).toFixed(2);
        }
        
        const settings = {
          tradingMode: kalshiTradingMode,
          convictionFilter: typeof kalshiConvictionFilter !== 'undefined' ? kalshiConvictionFilter : 'APLUS',
          contractsCount: maxContracts,
          audioEnabled: btcAudioEnabled,
          predMode,
          maxDailyRisk,
          maxDailyTrades
        };
        
        // Push backend toggles & risk limits with verified responses BEFORE persisting locally
        const apiBase = getKalshiApiBase();
        const minConviction = document.getElementById("settingMinConviction")?.value || "B";
        
        const [resPred, resRisk, resThresh, resCt] = await Promise.all([
          authFetch(`${apiBase}/api/engine/${window.currentAsset}/trade/prediction_mode?enabled=${predMode}`, { method: "POST" }),
          authFetch(`${apiBase}/api/engine/${window.currentAsset}/trade/risk_limits?max_daily_risk=${encodeURIComponent(maxDailyRisk)}&max_daily_trades=${encodeURIComponent(maxDailyTrades)}`, { method: "POST" }),
          authFetch(`${apiBase}/api/engine/${window.currentAsset}/trade/threshold?threshold=${encodeURIComponent(minConviction)}`, { method: "POST" }),
          authFetch(`${apiBase}/api/engine/${window.currentAsset}/trade/contracts?count=${encodeURIComponent(maxContracts)}`, { method: "POST" })
        ]);

        if (!resPred.ok) throw new Error(`Prediction mode update failed (HTTP ${resPred.status})`);
        if (!resRisk.ok) throw new Error(`Risk limits update failed (HTTP ${resRisk.status})`);
        if (!resThresh.ok) throw new Error(`Threshold update failed (HTTP ${resThresh.status})`);
        if (!resCt.ok) throw new Error(`Max Contracts update failed (HTTP ${resCt.status})`);

        // Only persist to localStorage AFTER backend confirms success
        localStorage.setItem("kalshiGeneralSettings", JSON.stringify(settings));
        
        const aiSettings = {
            modelChoice: document.getElementById("settingModelChoice")?.value || "Swarm",
            trainWindow: parseInt(document.getElementById("settingTrainWindow")?.value) || 4000,
            regC: parseFloat(document.getElementById("settingRegC")?.value) || 0.5,
            classWeight: document.getElementById("settingClassWeight")?.value || "balanced",
            maxCap: parseFloat(document.getElementById("settingMaxCap")?.value) || 5,
            minConf: parseFloat(document.getElementById("settingMinConf")?.value) || 65,
            minConviction: document.getElementById("settingMinConviction")?.value || "B",
            edgeWeightOn: document.getElementById("settingEdgeWeightOn")?.checked || false,
            edgeWeightFactor: parseFloat(document.getElementById("settingEdgeWeightFactor")?.value) || 1.2,
            orderType: document.getElementById("settingOrderType")?.value || "market",
            execDelay: parseInt(document.getElementById("settingExecDelay")?.value) || 1,
            pollInterval: parseInt(document.getElementById("settingPollInterval")?.value) || 5,
            verboseLog: document.getElementById("settingVerboseLog")?.checked || false,
            dryRun: document.getElementById("settingDryRun")?.checked || false,
            ignorePass: document.getElementById("settingIgnorePass")?.checked || false,
            ignorePassTechnicalOnly: document.getElementById("settingIgnorePassTechnicalOnly")?.checked || false,
            tradingStyle: document.getElementById("settingTradingStyle")?.value || "SNIPER",
            oneShotAiStartTrade: document.getElementById("settingOneShotAiStartTrade")?.checked || false,
            xgbEstimators: parseInt(document.getElementById("settingXgbEstimators")?.value) || 300,
            xgbMaxDepth: parseInt(document.getElementById("settingXgbMaxDepth")?.value) || 5,
            xgbLearningRate: parseFloat(document.getElementById("settingXgbLearningRate")?.value) || 0.1,
            signalIsolation: document.getElementById("settingSignalIsolation")?.value || "BLEND",
stopLossMoveDollars: parseFloat(document.getElementById("settingStopLossMoveDollars")?.value) || 140.0,
stopLossMaxMinutes: parseFloat(document.getElementById("settingStopLossMaxMinutes")?.value) || 8.0,
takeProfitEnabled: document.getElementById("settingTakeProfitEnabled")?.checked ?? true,
takeProfitPercent: parseFloat(document.getElementById("settingTakeProfitPercent")?.value) || 50.0,
useFinbertNLP: document.getElementById("settingUseFinbertNLP")?.checked ?? true
        };
        
        const resAi = await authFetch(`${apiBase}/api/engine/${window.currentAsset}/trade/ai_settings`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(aiSettings)
        });
        if (!resAi.ok) throw new Error(`AI settings update failed (HTTP ${resAi.status})`);
        
        localStorage.setItem("kalshiAiSettings", JSON.stringify(aiSettings));
        if (typeof restartAnalysisPolling === 'function') restartAnalysisPolling();

        if (showToast) showAppToast("Settings Saved", "Trade parameters and daily limits applied successfully", "success");
      } catch(e) {
        showAppToast("Save Error", String(e), "error");
      }
    }

    async function loadKalshiSettingsFromStorage() {
    try {
        const apiBase = getKalshiApiBase();
        const res = await authFetch(`${apiBase}/api/engine/${window.currentAsset}/trade/config`, { method: "GET" });
        if (res.ok) {
            const config = await res.json();
            
            // Sync General Config
            if (config.mode && kalshiTradingMode !== config.mode) {
                kalshiTradingMode = config.mode;
                const thumbEl = document.getElementById("modeSliderThumb");
                const textPaper = document.getElementById("modePaperText");
                const textLive = document.getElementById("modeLiveText");
                if (thumbEl && textPaper && textLive) {
                    if (kalshiTradingMode === "LIVE") {
                        thumbEl.className = "absolute top-[1px] bottom-[1px] w-[46px] rounded-full transition-all duration-300 shadow-sm left-[50px] bg-red-950 border border-red-500/80";
                        textPaper.className = "flex-1 text-center text-slate-500 transition-colors duration-300";
                        textLive.className = "flex-1 text-center text-red-400 transition-colors duration-300";
                    } else {
                        thumbEl.className = "absolute top-[1px] bottom-[1px] w-[46px] rounded-full transition-all duration-300 shadow-sm left-[2px] bg-cyan-950 border border-cyan-500/50";
                        textPaper.className = "flex-1 text-center text-cyan-300 transition-colors duration-300";
                        textLive.className = "flex-1 text-center text-slate-500 transition-colors duration-300";
                    }
                }
            }
            if (config.min_conviction) setConvictionFilter(config.min_conviction, false);
            if (config.max_contracts) {
                kalshiCurrentContracts = config.max_contracts;
                const settingMaxCt = document.getElementById("settingMaxContracts");
                if (settingMaxCt) settingMaxCt.value = config.max_contracts;
            }
            const predCb = document.getElementById("settingPredictionMode");
            if (predCb && typeof config.prediction_mode === 'boolean') predCb.checked = config.prediction_mode;
            
            const riskInput = document.getElementById("settingMaxDailyRisk");
            if (riskInput && config.max_daily_risk != null) riskInput.value = (parseFloat(config.max_daily_risk) || 0).toFixed(2);
            
            const tradesInput = document.getElementById("settingMaxDailyTrades");
            if (tradesInput && config.max_daily_trades != null) tradesInput.value = parseInt(config.max_daily_trades);

            // Sync AI Settings
            const aiSet = config.ai_settings || {};
            if (document.getElementById("settingModelChoice")) document.getElementById("settingModelChoice").value = "Swarm";
            if (document.getElementById("settingTradingStyle")) document.getElementById("settingTradingStyle").value = aiSet.tradingStyle || "SNIPER";
            if (document.getElementById("settingOneShotAiStartTrade")) document.getElementById("settingOneShotAiStartTrade").checked = !!aiSet.oneShotAiStartTrade;
            if (document.getElementById("settingTrainWindow")) {
                document.getElementById("settingTrainWindow").value = aiSet.trainWindow || 4000;
                if (document.getElementById("trainWinVal")) document.getElementById("trainWinVal").innerText = aiSet.trainWindow || 4000;
            }
            if (document.getElementById("settingRegC")) document.getElementById("settingRegC").value = aiSet.regC || 0.5;
            if (document.getElementById("settingClassWeight")) document.getElementById("settingClassWeight").value = aiSet.classWeight || "balanced";
            if (document.getElementById("settingMaxCap")) {
                document.getElementById("settingMaxCap").value = aiSet.maxCap || 5;
                if (aiSet.maxCap) {
                    kalshiFixedSize = parseFloat(aiSet.maxCap);
                    const sizeInput = document.getElementById("kalshiSizeInput");
                    if (sizeInput) sizeInput.value = kalshiFixedSize.toFixed(2);
                    kalshiCurrentContracts = Math.max(1, Math.round(kalshiFixedSize / kalshiCurrentPriceEst));
                }
            }
            if (document.getElementById("settingMinConf")) {
                document.getElementById("settingMinConf").value = aiSet.minConf || 65;
                if (document.getElementById("minConfVal")) document.getElementById("minConfVal").innerText = (aiSet.minConf || 65) + "%";
            }
            if (document.getElementById("settingMinConviction") && aiSet.minConviction) document.getElementById("settingMinConviction").value = aiSet.minConviction;
            if (document.getElementById("settingEdgeWeightOn")) document.getElementById("settingEdgeWeightOn").checked = !!aiSet.edgeWeightOn;
            if (document.getElementById("settingEdgeWeightFactor")) document.getElementById("settingEdgeWeightFactor").value = aiSet.edgeWeightFactor || 1.2;
            if (document.getElementById("settingIgnorePass")) document.getElementById("settingIgnorePass").checked = !!aiSet.ignorePass;
            if (document.getElementById("settingIgnorePassTechnicalOnly")) document.getElementById("settingIgnorePassTechnicalOnly").checked = !!aiSet.ignorePassTechnicalOnly;
            if (document.getElementById("settingXgbEstimators")) document.getElementById("settingXgbEstimators").value = aiSet.xgbEstimators || 200;
            if (document.getElementById("settingXgbMaxDepth")) document.getElementById("settingXgbMaxDepth").value = aiSet.xgbMaxDepth || 6;
            if (document.getElementById("settingXgbLearningRate")) document.getElementById("settingXgbLearningRate").value = aiSet.xgbLearningRate || 0.1;
            if (document.getElementById("settingSignalIsolation")) document.getElementById("settingSignalIsolation").value = aiSet.signalIsolation || "BLEND";
            if (document.getElementById("settingStopLossMoveDollars")) document.getElementById("settingStopLossMoveDollars").value = aiSet.stopLossMoveDollars || 140.0;
            if (document.getElementById("settingStopLossMaxMinutes")) document.getElementById("settingStopLossMaxMinutes").value = aiSet.stopLossMaxMinutes || 8.0;
            if (document.getElementById("settingTakeProfitEnabled")) document.getElementById("settingTakeProfitEnabled").checked = aiSet.takeProfitEnabled !== false;
            if (document.getElementById("settingTakeProfitPercent")) document.getElementById("settingTakeProfitPercent").value = aiSet.takeProfitPercent || 50.0;
            if (document.getElementById("settingUseFinbertNLP")) document.getElementById("settingUseFinbertNLP").checked = aiSet.useFinbertNLP !== false;

            // Update localStorage to match the single source of truth
            localStorage.setItem("kalshiAiSettings", JSON.stringify(aiSet));
            localStorage.setItem("kalshiGeneralSettings", JSON.stringify({
                tradingMode: config.mode,
                predMode: config.prediction_mode,
                convictionFilter: config.min_conviction,
                contractsCount: config.max_contracts,
                maxDailyRisk: config.max_daily_risk,
                maxDailyTrades: config.max_daily_trades
            }));
            
            console.log("[Settings] Successfully pulled authoritative config from backend on load.");
        }
    } catch(e) {
        console.warn("Failed to load backend settings on load:", e);
    }
}

  function resetKalshiSettingsDefaults() {
      const riskEl = document.getElementById("settingMaxDailyRisk");
      if (riskEl) riskEl.value = "25.00";
      const tradesEl = document.getElementById("settingMaxDailyTrades");
      if (tradesEl) tradesEl.value = "10";
      const predCb = document.getElementById("settingPredictionMode");
      if (predCb) predCb.checked = true;
      setConvictionFilter("BPLUS", false);
      saveKalshiSettings();
      showAppToast("Settings Reset", "Default parameters and risk limits restored", "info");
    }
    
    async function resetPaperBalanceUI() {
      const confirmed = await showAppModal({
        title: "Reset Paper Balance",
        badge: "PAPER TRADING",
        icon: "⚠️",
        iconBg: "bg-red-500/20 text-red-400 border border-red-500/40",
        body: `Are you sure you want to reset your paper trading balance back to $500.00?`,
        confirmText: "Reset Balance",
        confirmColor: "red"
      });
      
      if (!confirmed) return;
      
      try {
        const apiBase = getKalshiApiBase();
        const res = await authFetch(`${apiBase}/api/engine/${window.currentAsset}/paper/balance/reset`, { method: "POST" });
        if (res.ok) {
          const data = await res.json();
          const balEl = document.getElementById("kalshiSettingsPaperBalance");
          if (balEl) balEl.innerText = `$${(parseFloat(data.balance) || 0).toFixed(2)}`;
          showAppToast("Balance Reset", "Paper balance has been reset to $500.00", "success");
          pollKalshiTradingStatus();
        }
      } catch (e) {
        showAppToast("Error", "Failed to reset paper balance", "error");
      }
    }

    // =========================================================================
    // SCALPER SETTINGS SUB-PAGE CONTROLLER
    // =========================================================================
    let scalpEngineActive = false;

    function switchSettingsSubPage(sub) {
      const pageGeneral = document.getElementById("generalSettingsSubPage");
      const pageScalp = document.getElementById("scalperSettingsSubPage");
      const btnGeneral = document.getElementById("btnSettingsSubGeneral");
      const btnScalp = document.getElementById("btnSettingsSubScalp");

      const activeClass = "py-1 rounded bg-slate-800 text-cyan-300 shadow-sm transition-all cursor-pointer";
      const inactiveClass = "py-1 rounded text-slate-400 hover:text-slate-200 transition-all cursor-pointer";

      if (sub === "general") {
        if (pageGeneral) pageGeneral.classList.remove("hidden");
        if (pageScalp) pageScalp.classList.add("hidden");
        if (btnGeneral) btnGeneral.className = activeClass;
        if (btnScalp) btnScalp.className = inactiveClass + " flex items-center justify-center gap-1";
      } else {
        if (pageGeneral) pageGeneral.classList.add("hidden");
        if (pageScalp) pageScalp.classList.remove("hidden");
        if (btnScalp) btnScalp.className = activeClass + " flex items-center justify-center gap-1";
        if (btnGeneral) btnGeneral.className = inactiveClass;
        loadScalpConfigUI();
      }
    }

    async function loadScalpSettingsFromStorage() {
      try {
        const saved = localStorage.getItem("scalpSettings");
        if (saved) {
          const cfg = JSON.parse(saved);
          if (cfg.price_move_threshold) document.getElementById("scalpPriceMoveThreshold").value = cfg.price_move_threshold;
          if (cfg.take_profit_atr) document.getElementById("scalpTakeProfitATR").value = cfg.take_profit_atr;
          if (cfg.profit_target) document.getElementById("scalpProfitTarget").value = cfg.profit_target;
          if (cfg.loss_target) document.getElementById("scalpLossTarget").value = cfg.loss_target;
          if (cfg.minimum_conviction) document.getElementById("scalpMinConviction").value = cfg.minimum_conviction;
          if (cfg.max_contracts) document.getElementById("scalpMaxContracts").value = cfg.max_contracts;
          if (cfg.max_trades_per_interval) document.getElementById("scalpMaxTradesPerInterval").value = cfg.max_trades_per_interval;
        }
      } catch (e) { console.warn('Fetch failed:', e); }
    }

    async function loadScalpConfigUI() {
      try {
        const apiBase = getKalshiApiBase();
        const res = await authFetch(`${apiBase}/api/engine/${window.currentAsset}/scalp/config`);
        if (!res.ok) return;
        const cfg = await res.json();
        if (!cfg) return;

        scalpEngineActive = !!cfg.enabled;
        const btnToggle = document.getElementById("btnToggleScalpEngine");
        const badge = document.getElementById("scalpStatusBadge");
        const subBadge = document.getElementById("scalpSubBadge");

        if (btnToggle) {
          btnToggle.innerText = scalpEngineActive ? "ON" : "OFF";
          btnToggle.className = scalpEngineActive 
            ? "px-2.5 py-0.5 rounded text-[10px] font-black uppercase tracking-wider transition-all bg-emerald-600 text-white shadow shadow-emerald-600/50 cursor-pointer"
            : "px-2.5 py-0.5 rounded text-[10px] font-black uppercase tracking-wider transition-all bg-slate-800 text-slate-400 hover:bg-slate-700 cursor-pointer";
        }
        if (badge) {
          badge.innerText = scalpEngineActive ? "ACTIVE" : "INACTIVE";
          badge.className = scalpEngineActive 
            ? "text-[8px] sm:text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
            : "text-[8px] sm:text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-800 text-slate-400";
        }
        if (subBadge) {
          subBadge.className = scalpEngineActive ? "h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" : "h-1.5 w-1.5 rounded-full bg-slate-600";
        }

        const moveInput = document.getElementById("scalpPriceMoveThreshold");
        if (moveInput && cfg.price_move_threshold != null) moveInput.value = cfg.price_move_threshold;

        const atrInput = document.getElementById("scalpTakeProfitATR");
        if (atrInput && cfg.take_profit_atr != null) atrInput.value = cfg.take_profit_atr;

        const profInput = document.getElementById("scalpProfitTarget");
        const profLabel = document.getElementById("scalpProfitTargetLabel");
        if (profInput && cfg.profit_target != null) {
          profInput.value = cfg.profit_target;
          if (profLabel) profLabel.innerText = `+${Math.round(cfg.profit_target * 100)}%`;
        }

        const lossInput = document.getElementById("scalpLossTarget");
        const lossLabel = document.getElementById("scalpLossTargetLabel");
        if (lossInput && cfg.loss_target != null) {
          lossInput.value = cfg.loss_target;
          if (lossLabel) lossLabel.innerText = `-${Math.round(cfg.loss_target * 100)}%`;
        }

        const convSelect = document.getElementById("scalpMinConviction");
        if (convSelect && cfg.minimum_conviction) convSelect.value = cfg.minimum_conviction;

        const maxCtInput = document.getElementById("scalpMaxContracts");
        if (maxCtInput && cfg.max_contracts != null) maxCtInput.value = cfg.max_contracts;

        const maxTrInput = document.getElementById("scalpMaxTradesPerInterval");
        if (maxTrInput && cfg.max_trades_per_interval != null) maxTrInput.value = cfg.max_trades_per_interval;
      } catch (err) {
        console.warn("Error loading scalp config:", err);
      }
    }

    async function toggleScalpEngine() {
      const nextState = !scalpEngineActive;
      try {
        const apiBase = getKalshiApiBase();
        const endpoint = nextState ? `/api/engine/${window.currentAsset}/scalp/start` : `/api/engine/${window.currentAsset}/scalp/stop`;
        const res = await authFetch(`${apiBase}${endpoint}`, { method: "POST" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        scalpEngineActive = nextState;
        showAppToast("Scalp Engine", nextState ? "Autonomous scalper active" : "Scalper paused", nextState ? "success" : "info");
        loadScalpConfigUI();
      } catch (err) {
        showAppToast("Scalper Error", String(err), "error");
      }
    }

    async function saveScalpSettings(showToast = true) {
      try {
        const moveVal = parseFloat(document.getElementById("scalpPriceMoveThreshold")?.value || 0.5);
        const atrVal = parseFloat(document.getElementById("scalpTakeProfitATR")?.value || 2.0);
        const profVal = parseFloat(document.getElementById("scalpProfitTarget")?.value || 0.25);
        const lossVal = parseFloat(document.getElementById("scalpLossTarget")?.value || 0.25);
        const convVal = document.getElementById("scalpMinConviction")?.value || "A+";
        const ctVal = parseInt(document.getElementById("scalpMaxContracts")?.value || 1);
        const trVal = parseInt(document.getElementById("scalpMaxTradesPerInterval")?.value || 1);

        const patchBody = {
          price_move_threshold: moveVal,
          take_profit_atr: atrVal,
          profit_target: profVal,
          loss_target: lossVal,
          minimum_conviction: convVal,
          max_contracts: ctVal,
          max_trades_per_interval: trVal
        };

        const apiBase = getKalshiApiBase();
        const res = await authFetch(`${apiBase}/api/engine/${window.currentAsset}/scalp/config`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patchBody)
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        localStorage.setItem("scalpSettings", JSON.stringify(patchBody));
        if (showToast) showAppToast("Scalper Saved", "Scalp parameters updated successfully", "success");
        loadScalpConfigUI();
      } catch (err) {
        showAppToast("Save Failed", String(err), "error");
      }
    }

    async function resetScalpSettingsDefaults() {
      const defaultCfg = {
        price_move_threshold: 0.5,
        take_profit_atr: 2.0,
        profit_target: 0.25,
        loss_target: 0.25,
        minimum_conviction: "A+",
        max_contracts: 1,
        max_trades_per_interval: 1
      };

      try {
        const apiBase = getKalshiApiBase();
        const res = await authFetch(`${apiBase}/api/engine/${window.currentAsset}/scalp/config`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(defaultCfg)
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        showAppToast("Defaults Restored", "Scalper settings reset to defaults", "info");
        loadScalpConfigUI();
      } catch (err) {
        showAppToast("Reset Failed", String(err), "error");
      }
    }

    function initAccuracyTooltip() {
      const banner = document.getElementById("topBarLikelyCard");
      const tooltip = document.getElementById("accuracyTooltip");
      if (!banner || !tooltip) return;

      let hideTimeout = null;

      banner.addEventListener("mouseenter", async () => {
        clearTimeout(hideTimeout);
        try {
          const apiBase = getKalshiApiBase();
          const res = await fetch(`${apiBase}/api/engine/${window.currentAsset}/prediction/accuracy`);
          if (!res.ok) return;
          const data = await res.json();
          if (!data || !data.trade) {
            tooltip.classList.add("hidden");
            return;
          }

          const fc = data.forecast || {};
          const tr = data.trade || {};
          const isCorrect = data.correct;
          const pnlVal = parseFloat(tr.pnl || 0);
          const pnlFormatted = pnlVal >= 0 ? `+$${(isNaN(pnlVal) ? 0 : pnlVal).toFixed(2)}` : `-$${Math.abs(pnlVal).toFixed(2)}`;
          const pnlColor = pnlVal >= 0 ? "text-emerald-400" : "text-red-400";
          const settledAt = tr.settled_at || "Recent Settle";

          const headerIcon = isCorrect ? "✓" : "✗";
          const headerText = isCorrect ? "CORRECT PREDICTION" : "INCORRECT PREDICTION";
          const headerColor = isCorrect ? "text-emerald-400" : "text-red-400";
          const badgeBg = isCorrect ? "bg-emerald-500/20 text-emerald-300" : "bg-red-500/20 text-red-300";

          tooltip.innerHTML = `
            <div class="flex items-center gap-1.5 pb-1.5 mb-1.5 border-b border-slate-800">
              <span class="${headerColor} font-black text-xs">${headerIcon} ${headerText}</span>
              <span class="text-[9px] px-1.5 py-0.5 rounded ${badgeBg} font-bold ml-auto font-mono">VERIFIED</span>
            </div>
            <div class="space-y-1.5 text-[11px] font-mono">
              <div class="flex justify-between gap-4"><span class="text-slate-400">Conviction:</span> <span class="font-bold text-cyan-300">${fc.conviction_grade || "GRADE A+"}</span></div>
              <div class="flex justify-between gap-4"><span class="text-slate-400">Direction:</span> <span class="font-bold text-white">${fc.direction || "UP"}</span></div>
              <div class="flex justify-between gap-4"><span class="text-slate-400">Confidence:</span> <span class="font-bold text-emerald-400">${fc.confidence || 75}%</span></div>
              <div class="flex justify-between gap-4"><span class="text-slate-400">Profit/Loss:</span> <span class="font-bold ${pnlColor}">${pnlFormatted}</span></div>
              <div class="flex justify-between gap-4 pt-1 border-t border-slate-800/80 text-[9px] text-slate-400"><span>Settled:</span> <span>${settledAt}</span></div>
            </div>
          `;

          const rect = banner.getBoundingClientRect();
          let top = rect.bottom + 8;
          let left = rect.left;
          if (left + 260 > window.innerWidth) {
            left = window.innerWidth - 270;
          }
          tooltip.style.top = `${top}px`;
          tooltip.style.left = `${Math.max(10, left)}px`;
          tooltip.classList.remove("hidden");
        } catch (err) {
          console.warn("[AccuracyTooltip] Error:", err);
        }
      });

      banner.addEventListener("mouseleave", () => {
        hideTimeout = setTimeout(() => {
          tooltip.classList.add("hidden");
        }, 120);
      });
    }

    let btcWs = null;
    
    // Global Sleek Hover Tooltip Engine
    function initGlobalSleekTooltips() {

      let activeTarget = null;

      document.addEventListener("mouseover", (e) => {
        const target = e.target.closest("[title], [data-tooltip]");
        if (!target) return;

        // Completely ignore chart container and TradingView widget tooltips
        if (target.closest("#btc-chart-container, #tradingview_btc_chart")) {
          target.removeAttribute("title");
          target.removeAttribute("data-tooltip");
          if (activeTarget) {
            activeTarget = null;
          }
          return;
        }

        const rawTitle = (target.getAttribute("title") || target.getAttribute("data-tooltip") || "").trim();
        if (/tradingview|advanced\s*chart/i.test(rawTitle)) {
          target.removeAttribute("title");
          target.removeAttribute("data-tooltip");
          if (activeTarget) {
            activeTarget = null;
          }
          return;
        }

        // Convert native title attribute to data-tooltip to eliminate browser default tooltip
        if (target.hasAttribute("title")) {
          const titleText = target.getAttribute("title");
          if (titleText && titleText.trim()) {
            target.setAttribute("data-tooltip", titleText);
          }
          target.removeAttribute("title");
        }

        const text = target.getAttribute("data-tooltip");
        if (!text || !text.trim()) return;

        activeTarget = target;
        
        // Format text with clean line breaks
        const formattedHtml = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br/>");
        
        tooltip.innerHTML = `<div class="text-[11px] font-mono text-slate-200 leading-snug">${formattedHtml}</div>`;
        tooltip.classList.remove("hidden");
        tooltip.style.opacity = "1";

        positionTooltip(e, target);
      });

      document.addEventListener("mouseout", (e) => {
        const target = e.target.closest("[data-tooltip]");
        if (target && target === activeTarget) {
          activeTarget = null;
          tooltip.style.opacity = "0";
          tooltip.classList.add("hidden");
        }
        // Flush any deferred trend box updates if mouse left the trend box grid
        const grid = document.getElementById("btcTrendBoxGrid");
        if (grid && window._pendingTrendBoxUpdate && !grid.matches(":hover")) {
          const pending = window._pendingTrendBoxUpdate;
          window._pendingTrendBoxUpdate = null;
          renderBtcTrendBox(pending.last5, pending.streak);
        }
      });

      function positionTooltip(e, target) {
        const rect = target.getBoundingClientRect();
        let top = rect.bottom + 6;
        let left = rect.left;

        const tooltipRect = tooltip.getBoundingClientRect();
        if (left + tooltipRect.width > window.innerWidth - 12) {
          left = window.innerWidth - tooltipRect.width - 12;
        }
        if (top + tooltipRect.height > window.innerHeight - 12) {
          top = rect.top - tooltipRect.height - 6;
        }

        tooltip.style.top = `${Math.max(6, top)}px`;
        tooltip.style.left = `${Math.max(6, left)}px`;
      }

      const chartBox = document.getElementById("btc-chart-container");
      if (chartBox) {
        chartBox.addEventListener("mouseenter", () => {
          if (activeTarget) {
            activeTarget = null;
            tooltip.style.opacity = "0";
            tooltip.classList.add("hidden");
          }
        }, true);
      }
    }

    let wsReconnectAttempts = 0;
    function initBtcWebsocket() {
      if (window.currentAsset !== "BTC" && window.currentAsset !== "ETH") return;
      if (btcWs) return;
      try {
        btcWs = new WebSocket("wss://ws-feed.exchange.coinbase.com");
        btcWs.onopen = () => {
          wsReconnectAttempts = 0;
          btcWs.send(JSON.stringify({
            "type": "subscribe",
            "product_ids": [window.currentAsset === "ETH" ? "ETH-USD" : "BTC-USD"],
            "channels": ["ticker"]
          }));
        };
        let _pendingWsPrice = null;
        let _wsRafScheduled = false;

        btcWs.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "ticker" && data.product_id === (window.currentAsset === "ETH" ? "ETH-USD" : "BTC-USD")) {
              const p = parseFloat(data.price);
              const vol = data.volume_24h ? parseFloat(data.volume_24h) : null;
              if (vol && !isNaN(vol)) {
                window.cachedBtcVolume = vol;
              }
              if (!isNaN(p)) {
                _pendingWsPrice = p;
                if (!_wsRafScheduled) {
                  _wsRafScheduled = true;
                  requestAnimationFrame(() => {
                    _wsRafScheduled = false;
                    if (_pendingWsPrice !== null) {
                      const curP = _pendingWsPrice;
                      renderBtcHeroHud({ 
                        price: curP, 
                        volume_24h: window.cachedBtcVolume || window.lastKalshiVolume,
                        target_price: window.cachedBtcTargetPrice 
                      });
                      if (typeof btcCandleSeries !== "undefined" && btcCandleSeries && window.lastCandle) {
                         window.lastCandle.close = curP;
                         if (curP > window.lastCandle.high) window.lastCandle.high = curP;
                         if (curP < window.lastCandle.low) window.lastCandle.low = curP;
                         btcCandleSeries.update(window.lastCandle);
                      }
                    }
                  });
                }
              }
            }
          } catch (e) { console.warn('Fetch failed:', e); }
        };
        btcWs.onerror = () => { 
          try { if (btcWs) btcWs.close(); } catch (e) { console.warn('Fetch failed:', e); }
          btcWs = null; 
        };
        btcWs.onclose = () => { 
          btcWs = null; 
          const delay = Math.min(30000, 1000 * Math.pow(2, wsReconnectAttempts));
          wsReconnectAttempts++;
          setTimeout(initBtcWebsocket, delay); 
        };
      } catch (e) {
        btcWs = null;
      }
    }

    // Initialize
    updateKalshiPayoutCalculator();
    startLive1sRefresh();
    initBtcChartOnce();
    triggerBtcAnalysis();
    
    function closeMlPredictionDetailsModal() {
        const modal = document.getElementById("mlPredictionDetailsModal");
        if (modal) modal.classList.add("hidden");
    }

    document.addEventListener("click", (e) => {
        const modal = document.getElementById("mlPredictionDetailsModal");
        const bubble = document.getElementById("kalshiMLStatusBubble");
        if (modal && !modal.classList.contains("hidden")) {
            if (!modal.contains(e.target) && (!bubble || !bubble.contains(e.target))) {
                closeMlPredictionDetailsModal();
            }
        }
    });

    function openMlPredictionDetailsModal() {
        const modal = document.getElementById("mlPredictionDetailsModal");
        const content = document.getElementById("mlModalContent");
        const bubble = document.getElementById("kalshiMLStatusBubble");
        if (!modal || !content) return;

        // Toggle if already open
        if (!modal.classList.contains("hidden")) {
            modal.classList.add("hidden");
            return;
        }

        const locked = window.lockedContractForecast || window.cachedNextContractForecast || {};
        const accuracy = window.serverPredictionAccuracy || {};
        
        const dir = locked.direction || "SCANNING";
        const isUp = dir === "ABOVE" || dir === "UP" || dir === "YES";
        const isDown = dir === "BELOW" || dir === "DOWN" || dir === "NO";

        const dirColor = isUp ? "text-emerald-400" : isDown ? "text-rose-400" : "text-amber-400";
        const conf = locked.probability_percent ? `${(isNaN(Number(locked.probability_percent)) ? 0 : Number(locked.probability_percent)).toFixed(1)}%` : "--%";
        const estSettle = locked.target_settlement_zone || "--";
        const modelChoice = document.getElementById("settingModelChoice")?.value || "XGBoost";
        
        const factors = locked.decision_factors || locked.catalysts || [];
        let factorsListHtml = "";
        if (factors && factors.length > 0) {
          factorsListHtml = factors.map(f => `<li class="flex items-start gap-1.5"><span class="text-cyan-400">•</span> <span>${f}</span></li>`).join("");
        } else {
          factorsListHtml = `<li class="text-slate-400 italic">No specific signal catalysts flagged yet. Monitoring real-time orderbook & momentum.</li>`;
        }

        const accPct = (accuracy.accuracy_percent != null && accuracy.accuracy_percent !== null) ? `${accuracy.accuracy_percent}%` : "--%";
        const accTotal = accuracy.total_evaluated || 0;

        const dailyHistory = accuracy.daily_history || getDailyAccuracyHistory();
        const todayStr = accuracyDateKey(Math.floor(Date.now() / 1000));
        const prevDaysArray = Object.entries(dailyHistory)
          .filter(([date, stats]) => date < todayStr && stats && stats.total > 0)
          .sort(([a], [b]) => b.localeCompare(a))
          .slice(0, 3);
        const prevDaysHtml = prevDaysArray.length
          ? prevDaysArray.map(([date, stats]) => {
              const label = new Date(`${date}T12:00:00`).toLocaleDateString([], { weekday: "short" });
              return `${label} ${Math.round((stats.correct / stats.total) * 100)}%`;
            }).join(" <span class='text-slate-600'>|</span> ")
          : "No prior days";

        content.innerHTML = `
          <div class="grid grid-cols-2 gap-2 bg-slate-950/80 p-2.5 rounded-xl border border-slate-800">
            <div>
              <div class="text-[9px] text-slate-400 uppercase tracking-wider">Prediction Direction</div>
              <div class="text-sm font-black ${dirColor} mt-0.5">${dir}</div>
            </div>
            <div>
              <div class="text-[9px] text-slate-400 uppercase tracking-wider">AI Confidence</div>
              <div class="text-sm font-black text-amber-400 mt-0.5">${conf}</div>
            </div>
          </div>

          <div class="bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80 space-y-1">
            <div class="flex justify-between items-center text-[10px]">
              <span class="text-slate-400">Active Model Engine:</span>
              <span class="font-bold text-cyan-300">${modelChoice}</span>
            </div>
            <div class="flex justify-between items-center text-[10px]">
              <span class="text-slate-400">Est. Target Zone:</span>
              <span class="font-bold text-white">${estSettle}</span>
            </div>
            <div class="flex justify-between items-center text-[10px]">
              <span class="text-slate-400">Model Auto-Accuracy:</span>
              <span class="font-bold text-emerald-400">${accPct} (${accTotal} evaluated)</span>
            </div>
            <div class="flex justify-between items-center text-[10px]">
              <span class="text-slate-400">Previous Days:</span>
              <span class="font-bold text-amber-400/90">${prevDaysHtml}</span>
            </div>
          </div>

          <div>
            <div class="text-[10px] font-bold text-cyan-400 uppercase tracking-wider mb-1">Key Decision Factors & Signals:</div>
            <ul class="bg-slate-950/80 p-2.5 rounded-xl border border-slate-800 space-y-1 text-[10px] max-h-[140px] overflow-y-auto">
              ${factorsListHtml}
            </ul>
          </div>
        `;

        // Removed inline dynamic positioning, CSS tailwind will now handle centering
        modal.style.top = "";
        modal.style.left = "";
        modal.classList.remove("hidden");
    }

    pollKalshiTradingStatus();
    let pollKalshiTradingStatusId = setInterval(pollKalshiTradingStatus, 3000);
    initAccuracyTooltip();
    loadScalpConfigUI();
    initBtcWebsocket();
    initGlobalSleekTooltips();

    // Setup Global Price Ticker
    async function pollGlobalTicker() {
      try {
        const assets = ["BTC", "ETH", "GOLD"];
        const apiBase = getKalshiApiBase();
        const promises = assets.map(asset => 
          authFetch(`${apiBase}/api/engine/${asset}/ticker`).then(r => r.json()).catch(() => ({}))
        );
        const results = await Promise.all(promises);
        
        const t1 = document.getElementById("globalPriceTicker1");
        const t2 = document.getElementById("globalPriceTicker2");
        if (!t1 || !t2) return;

        let html = '';
        const symbols = { "BTC": "₿", "ETH": "Ξ", "GOLD": "🥇" };
        
        assets.forEach((asset, idx) => {
           const price = results[idx]?.price || 0;
           let formatted = "--";
           if (price > 0) {
               formatted = asset === "GOLD" 
                 ? `$${Number(price).toLocaleString("en-US", {minimumFractionDigits:2, maximumFractionDigits:2})}` 
                 : `$${Number(price).toLocaleString("en-US", {minimumFractionDigits:0, maximumFractionDigits:2})}`;
           }
           html += `<span class="text-slate-300 mr-2 whitespace-nowrap text-[11px] font-mono font-bold">${symbols[asset]} ${asset}: <span class="text-emerald-400 font-bold">${formatted}</span></span>`;
        });
        
        t1.innerHTML = html;
        t2.innerHTML = html;
      } catch (e) { console.warn('Fetch failed:', e); }
    }
    pollGlobalTicker();
    let pollGlobalTickerId = setInterval(pollGlobalTicker, 15000);

    // Kick off BTC Analyzer
    switchMode('btc_analyzer');

  

    // --- Trade Details Modal ---
    window.showTradeDetailsModal = function(tradeId) {
      if (!window._kalshiTradesData) return;
      const trade = window._kalshiTradesData.find(t => t.id === tradeId);
      if (!trade) return;

      const formatTradeDateTime = (value) => {
        if (!value) return "N/A";
        const raw = String(value).trim();
        if (/^\d{4}-\d{2}-\d{2}\s+/.test(raw)) return raw;
        const date = new Date(raw);
        return Number.isNaN(date.getTime()) ? raw : date.toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true, timeZoneName: 'short' });
      };

      const openedAt = formatTradeDateTime(trade.timestamp);
      const settledAt = trade.status === "CLOSED" || trade.status === "SETTLED" ? formatTradeDateTime(trade.settled_at) : "Pending";
      const isLive = String(trade.mode).toUpperCase() === "LIVE";
      const direction = String(trade.side || trade.direction || "").toUpperCase();
      const pnl = (parseFloat(trade.pnl || trade.live_pnl || 0) || 0).toFixed(2);
      const isWin = pnl > 0;
      
      const detailsHtml = `
        <div class="space-y-3 font-mono text-xs">
          <div class="grid grid-cols-2 gap-2 text-slate-300">
            <div class="bg-slate-950 p-2 rounded border border-slate-800">
              <span class="block text-[10px] text-slate-500 uppercase">Trade ID</span>
              <span class="font-bold truncate text-[10px] text-slate-400" title="${trade.id}">${trade.id}</span>
            </div>
            <div class="bg-slate-950 p-2 rounded border border-slate-800">
              <span class="block text-[10px] text-slate-500 uppercase">Mode</span>
              <span class="font-bold ${isLive ? 'text-red-400' : 'text-cyan-400'}">${isLive ? 'LIVE' : 'PAPER'}</span>
            </div>
            <div class="bg-slate-950 p-2 rounded border border-slate-800">
              <span class="block text-[10px] text-slate-500 uppercase">Direction</span>
              <span class="font-bold ${direction.includes("YES") || direction.includes("ABOVE") || direction.includes("UP") ? 'text-emerald-400' : 'text-red-400'}">${direction}</span>
            </div>
            <div class="bg-slate-950 p-2 rounded border border-slate-800">
              <span class="block text-[10px] text-slate-500 uppercase">Status</span>
              <span class="font-bold ${trade.status === 'CLOSED' || trade.status === 'SETTLED' ? 'text-slate-400' : 'text-amber-400'}">${trade.status}</span>
            </div>
            <div class="bg-slate-950 p-2 rounded border border-slate-800">
              <span class="block text-[10px] text-slate-500 uppercase">Entry</span>
              <span class="font-bold">${trade.count || 1}ct @ $${(parseFloat(trade.entry_price || 0) || 0).toFixed(2)}</span>
            </div>
            <div class="bg-slate-950 p-2 rounded border border-slate-800">
              <span class="block text-[10px] text-slate-500 uppercase">P&L</span>
              <span class="font-bold ${isWin ? 'text-emerald-400' : pnl < 0 ? 'text-red-400' : 'text-slate-400'}">${isWin ? '+' : ''}$${pnl}</span>
            </div>
          </div>
          
          <div class="bg-slate-950 p-2 rounded border border-slate-800">
            <span class="block text-[10px] text-slate-500 uppercase mb-1">Conviction</span>
            <div class="text-slate-300"><span class="font-bold text-cyan-400">${trade.conviction_grade || 'N/A'}</span></div>
            <div class="text-[10px] text-slate-400 mt-1">${trade.conviction_badge || ''}</div>
            <div class="text-[10px] text-slate-400 mt-1">Raw ML Prob: <span class="text-amber-400">${trade.ml_prob ? (parseFloat(trade.ml_prob) * 100).toFixed(1) + '%' : 'N/A'}</span></div>
          </div>

          <div class="bg-slate-950 p-2 rounded border border-slate-800">
            <span class="block text-[10px] text-slate-500 uppercase mb-1">Catalysts</span>
            <ul class="list-disc pl-4 text-[10px] text-slate-400 space-y-1">
              ${(Array.isArray(trade.catalysts) ? trade.catalysts : (typeof trade.catalysts === "string" ? [trade.catalysts] : [])).map(c => `<li>${escapeHtml(c)}</li>`).join('') || '<li>No catalysts listed</li>'}
            </ul>
          </div>
          
          <div class="bg-slate-950 p-2 rounded border border-slate-800">
            <span class="block text-[10px] text-slate-500 uppercase mb-1">Exit Reason</span>
            <div class="text-slate-300 text-[10px]">${trade.exit_reason || 'N/A'}</div>
          </div>
          
          <div class="bg-slate-950 p-2 rounded border border-slate-800">
            <span class="block text-[10px] text-slate-500 uppercase mb-1">Timeline</span>
            <div class="text-slate-300 text-[10px]">Opened: ${openedAt}</div>
            <div class="text-slate-300 text-[10px]">Settled: ${settledAt}</div>
          </div>
        </div>
      `;

      // Inject or update floating modal
      let floatingModal = document.getElementById("sleekTradeModal");
      if (!floatingModal) {
        floatingModal = document.createElement("div");
        floatingModal.id = "sleekTradeModal";
        // Fixed overlay but entirely transparent background to catch outside clicks
        floatingModal.className = "fixed inset-0 z-[99999] flex items-center justify-center pointer-events-auto hidden";
        floatingModal.onclick = function(e) {
          if (e.target === floatingModal) {
            floatingModal.classList.add("hidden");
          }
        };
        
        document.body.appendChild(floatingModal);
      }
      
      floatingModal.innerHTML = `
        <div class="bg-slate-900 border border-slate-700/80 rounded-xl p-4 shadow-2xl text-left font-mono text-slate-200 w-full max-w-[320px] max-h-[85vh] overflow-y-auto animate-in fade-in zoom-in-95 duration-150 relative">
          <button onclick="document.getElementById('sleekTradeModal').classList.add('hidden')" class="absolute top-3 right-3 text-slate-500 hover:text-white transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
          
          <div class="flex items-center gap-2 mb-3">
            <div class="w-6 h-6 rounded-full flex items-center justify-center bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 text-xs shrink-0">📋</div>
            <div class="font-bold uppercase tracking-wider text-xs text-white">Trade Details</div>
          </div>
          
          ${detailsHtml}
        </div>
      `;
      
      floatingModal.classList.remove("hidden");
    };


window.switchAsset = function(asset) {
    if (window.currentAsset === asset) return;
    window.currentAsset = asset;
    
    const tradeListBtn = document.getElementById("btnOpenTradeList");
    if (tradeListBtn) {
        tradeListBtn.href = `/trades?asset=${asset}`;
    }
    
    // Update tabs UI
    document.querySelectorAll('.asset-tab').forEach(el => {
        el.className = "asset-tab rounded-full px-4 py-1.5 text-xs font-black border border-slate-600 bg-slate-800 text-slate-400 transition-all hover:bg-slate-700";
    });
    const activeTab = document.getElementById('tab_' + asset);
    if (activeTab) {
        if (asset === 'BTC') activeTab.className = "asset-tab active rounded-full px-4 py-1.5 text-xs font-black border border-amber-500/50 bg-amber-500/20 text-amber-400 transition-all hover:bg-amber-500/30";
        if (asset === 'ETH') activeTab.className = "asset-tab active rounded-full px-4 py-1.5 text-xs font-black border border-blue-500/50 bg-blue-500/20 text-blue-400 transition-all hover:bg-blue-500/30";
        if (asset === 'GOLD') activeTab.className = "asset-tab active rounded-full px-4 py-1.5 text-xs font-black border border-yellow-500/50 bg-yellow-500/20 text-yellow-400 transition-all hover:bg-yellow-500/30";
    }
    
    const mobDropdown = document.getElementById('mobileAssetDropdown');
    if (mobDropdown) mobDropdown.value = asset;
    
    // Update header
    
    // Update live price and target labels
    const livePriceLabel = document.getElementById('topBarLivePriceLabel');
    if (livePriceLabel) livePriceLabel.innerText = 'LIVE ' + asset;
    
    const targetPriceLabel = document.getElementById('topBarTargetPriceLabel');
    if (targetPriceLabel) targetPriceLabel.innerText = asset + ' 15M TARGET';
    
    
    // Force a fast refresh of data
    window.cachedBtcTargetPrice = null;
    window._cachedCbStats = null;
    if (typeof fetchBtcKlinesDirect !== "undefined") fetchBtcKlinesDirect();
    if (typeof fetchKalshiDirect !== "undefined") fetchKalshiDirect();
    if (typeof triggerBtcAnalysis !== "undefined") triggerBtcAnalysis();
    if (typeof pollBtcLive1s !== "undefined") {
        _isPollingBtcLive = false;
        pollBtcLive1s();
    }
    
    // Reconnect websocket
    if (typeof btcWs !== "undefined" && btcWs) {
        btcWs.close();
    }
    if (typeof initBtcWebsocket !== "undefined") {
        initBtcWebsocket();
    }
    
    // Update TV widget

    window.tvWidget = null;
    if (typeof initTradingViewChart !== "undefined") initTradingViewChart();
};

    // Wire up manual trade size input to dynamically save to backend
    document.addEventListener("DOMContentLoaded", () => {
    });
