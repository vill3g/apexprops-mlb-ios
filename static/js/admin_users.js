/**



 * Admin User Control Panel Controller



 * Multi-user management, configuration editing, and autonomous execution controls.



 */







(function () {



  let adminUsersList = [];



  let selectedUserId = null;



  try {



    const savedUid = parseInt(localStorage.getItem("admin_selected_user_id"), 10);



    if (!isNaN(savedUid)) selectedUserId = savedUid;



  } catch (_) {}



  let currentSearch = "";



  let currentModeFilter = "ALL";



  let currentAiFilter = "ALL";



  let isPolling = false;



  let currentUserDetailTab = "settings"; // 'settings' | 'trades'



  let currentUserTrades = [];



  let currentTradesUserId = null;



  let currentTradeFilterMode = "ALL"; // 'ALL' | 'PAPER' | 'LIVE'



  let currentTradeFilterStatus = "ALL"; // 'ALL' | 'CLOSED' | 'OPEN' | 'WIN' | 'LOSS'



  let currentTradeSearch = "";

  // Support Tickets State
  let adminCurrentSection = "users"; // 'users' | 'tickets'
  let adminTicketsList = [];
  let selectedTicketId = null;
  let currentTicketFilterStatus = "ALL"; // 'ALL' | 'OPEN' | 'RESOLVED'
  let currentTicketSearch = "";
  let isAnalyzingTicket = false;




  function escapeHtml(str) {



    if (str === null || str === undefined) return "";



    return String(str)



      .replace(/&/g, "&amp;")



      .replace(/</g, "&lt;")



      .replace(/>/g, "&gt;")



      .replace(/"/g, "&quot;")



      .replace(/'/g, "&#039;");



  }







    function getAdminAuthHeaders() {



    const headers = { "Content-Type": "application/json" };



    const saasToken = localStorage.getItem("saas_token");



    if (saasToken) {



      headers["Authorization"] = `Bearer ${saasToken}`;



    }



    const adminToken = localStorage.getItem("admin_api_token") || localStorage.getItem("api_token") || localStorage.getItem("app_api_token");



    if (adminToken) {



      headers["X-API-Token"] = adminToken;



    }



    return headers;



  }







  







  function showAdminToast(message, type = "success") {



    const container = document.getElementById("appToastContainer");



    if (!container) {



      console.log(`[Toast ${type}]`, message);



      return;



    }



    const toast = document.createElement("div");



    const isSuccess = type === "success";



    toast.className = `flex items-center gap-2.5 px-4 py-2.5 rounded-xl border text-xs font-mono shadow-2xl backdrop-blur-md transition-all duration-300 animate-in fade-in slide-in-from-top-2 ${



      isSuccess



        ? "bg-slate-950/95 border-emerald-500/50 text-emerald-300 shadow-emerald-500/20"



        : "bg-slate-950/95 border-rose-500/50 text-rose-300 shadow-rose-500/20"



    }`;



    toast.innerHTML = `



      <span class="text-sm">${isSuccess ? "✅" : "❌"}</span>



      <span class="font-bold flex-1">${escapeHtml(message)}</span>



    `;



    container.appendChild(toast);



    setTimeout(() => {



      toast.style.opacity = "0";



      toast.style.transform = "translateY(-8px)";



      setTimeout(() => toast.remove(), 300);



    }, 3500);



  }







  async function fetchAdminUsers(isBackground = false) {



    try {



      const resp = await fetch("/api/admin/users", { cache: "no-store", 



        headers: getAdminAuthHeaders(),



      });



      if (!resp.ok) {



        throw new Error(`Server returned HTTP ${resp.status}`);



      }



      const data = await resp.json();



      if (data.success && Array.isArray(data.users)) {



        adminUsersList = data.users;



        updateHeaderBadge(adminUsersList.length);



        updateSummaryStats();



        renderUserList();



        



        let targetUser = null;



        if (selectedUserId) {



          targetUser = adminUsersList.find((u) => u.id === selectedUserId);



        }



        if (!targetUser && adminUsersList.length > 0) {



          targetUser = adminUsersList[0];



          selectedUserId = targetUser.id;



        }



        if (targetUser && !isBackground) {



          selectUserToEdit(targetUser.id);



        }







        // Also fetch broadcast status to sync toggle



        try {



          const bResp = await fetch("/api/admin/broadcast/status", { headers: getAdminAuthHeaders() });



          if (bResp.ok) {



            const bData = await bResp.json();



            const isEnabled = !!bData.broadcast_trades;



            const bCastModal = document.getElementById("modalBroadcastToggle");



            if (bCastModal) bCastModal.checked = isEnabled;



            const bCastBadge = document.getElementById("modalBroadcastStatusBadge");



            if (bCastBadge) {



              bCastBadge.textContent = isEnabled ? "ON" : "OFF";



              bCastBadge.className = isEnabled ? "text-[9px] font-mono font-bold uppercase text-cyan-400" : "text-[9px] font-mono font-bold uppercase text-slate-500";



            }



          }



        } catch (_) {}



      }



    } catch (err) {



      console.error("[AdminUserPanel] Failed to fetch users:", err);



      if (!isBackground) {



        showAdminToast(`Failed to load users: ${err.message}`, "error");



      }



    }



  }







  function updateHeaderBadge(count) {



    const badge = document.getElementById("headerUserCountBadge");



    if (badge) {



      badge.textContent = `${count} Users`;



    }



    const countEl = document.getElementById("headerUserCount");



    if (countEl) {



      countEl.textContent = `${count} Users`;



    }



    const mobCount = document.getElementById("adminMobileUserCount");



    if (mobCount) {



      mobCount.textContent = count;



    }



  }







  function updateSummaryStats() {



    const total = adminUsersList.length;



    const activeAi = adminUsersList.filter((u) => u.ai_enabled && u.is_active).length;



    const liveUsers = adminUsersList.filter((u) => u.trading_mode === "LIVE").length;



    const totalPnl = adminUsersList.reduce((sum, u) => sum + (u.net_pnl || 0), 0);



    const totalKalshi = adminUsersList.reduce((sum, u) => {



      const b = u.kalshi_balance !== null && u.kalshi_balance !== undefined && !isNaN(u.kalshi_balance)



        ? Number(u.kalshi_balance)



        : (u.live_balance !== null && u.live_balance !== undefined && !isNaN(u.live_balance) ? Number(u.live_balance) : 0);



      return sum + b;



    }, 0);







    const elTotal = document.getElementById("adminTotalUsersCount");



    if (elTotal) elTotal.textContent = total;







    const elAi = document.getElementById("adminActiveAiCount");



    if (elAi) elAi.textContent = activeAi;







    const elLive = document.getElementById("adminLiveTradingCount");



    if (elLive) elLive.textContent = liveUsers;







    const elKalshi = document.getElementById("adminTotalKalshiBal");



    if (elKalshi) {



      elKalshi.textContent = `$${totalKalshi.toFixed(2)}`;



    }







    const elPnl = document.getElementById("adminTotalPnlSum");



    if (elPnl) {



      const prefix = totalPnl >= 0 ? "+$" : "-$";



      elPnl.textContent = `${prefix}${Math.abs(totalPnl).toFixed(2)}`;



      elPnl.className = totalPnl >= 0 ? "text-emerald-400 font-bold" : "text-rose-400 font-bold";



    }



  }







  function renderUserList() {



    const listContainer = document.getElementById("adminUserListContainer");



    if (!listContainer) return;







    let filtered = adminUsersList.filter((u) => {



      if (currentSearch) {



        const q = currentSearch.toLowerCase();



        const matchesName = u.username && u.username.toLowerCase().includes(q);



        const matchesId = String(u.id).includes(q);



        if (!matchesName && !matchesId) return false;



      }



      if (currentModeFilter !== "ALL" && u.trading_mode !== currentModeFilter) {



        return false;



      }



      if (currentAiFilter === "ENABLED" && !u.ai_enabled) return false;



      if (currentAiFilter === "DISABLED" && u.ai_enabled) return false;



      return true;



    });







    if (filtered.length === 0) {



      listContainer.innerHTML = `



        <div class="p-8 text-center text-slate-500 font-mono text-xs">



          No users match the selected filters.



        </div>



      `;



      return;



    }







    let $scrollTop = listContainer.scrollTop; listContainer.innerHTML = filtered



      .map((u) => {



        const isSelected = u.id === selectedUserId;



        const isLive = u.trading_mode === "LIVE";



        const kalshiBalNum = u.kalshi_balance !== null && u.kalshi_balance !== undefined && !isNaN(u.kalshi_balance)



          ? Number(u.kalshi_balance)



          : (u.live_balance !== null && u.live_balance !== undefined && !isNaN(u.live_balance) ? Number(u.live_balance) : null);



        const hasKalshi = u.has_kalshi_keys && kalshiBalNum !== null;



        const kalshiBalText = hasKalshi ? `$${kalshiBalNum.toFixed(2)}` : (u.has_kalshi_keys ? "Syncing..." : "No Keys");



        const kalshiBalColor = hasKalshi ? "text-emerald-400 font-bold font-mono" : (u.has_kalshi_keys ? "text-amber-400 font-bold font-mono" : "text-slate-500 font-mono");







        const pnl = u.net_pnl || 0;



        const pnlClass = pnl >= 0 ? "text-emerald-400" : "text-rose-400";



        const pnlText = `${pnl >= 0 ? "+$" : "-$"}${Math.abs(pnl).toFixed(2)}`;







        return `



        <div onclick="window.selectUserToEdit(${u.id})" class="p-3 rounded-xl border cursor-pointer transition-all ${



          isSelected



            ? "bg-slate-900 border-cyan-500 shadow-lg shadow-cyan-500/10 ring-1 ring-cyan-500/30"



            : "bg-slate-950/60 border-slate-800 hover:border-slate-700 hover:bg-slate-900/40"



        }">



          <div class="flex items-center justify-between gap-2 mb-2">



            <div class="flex items-center gap-2 min-w-0">



              <div class="w-8 h-8 rounded-lg ${
                u.ai_enabled ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30" : "bg-slate-800 text-slate-400 border border-slate-700"
              } flex items-center justify-center font-black text-xs shrink-0 overflow-hidden bg-cover bg-center"
              ${u.profile_picture_url ? `style="background-image: url('${escapeHtml(u.profile_picture_url)}'); border: 1px solid #334155;"` : ''}>
                ${u.profile_picture_url ? '' : (u.username ? escapeHtml(u.username.substring(0, 2).toUpperCase()) : `U${u.id}`)}
              </div>



              <div class="min-w-0">



                <div class="flex items-center gap-1.5">



                  <span class="font-bold text-xs text-white truncate">${escapeHtml(u.username)}</span>



                  <span class="text-[9px] font-mono font-bold px-1 rounded ${



                    u.role === "admin" ? "bg-amber-500/20 text-amber-400 border border-amber-500/40" : "bg-slate-800 text-slate-400"



                  }">#${u.id}</span>



                </div>



                <div class="flex items-center gap-1.5 mt-0.5">



                  <span class="text-[9px] font-mono px-1.5 py-0.2 rounded font-bold ${



                    isLive ? "bg-amber-500/20 text-amber-300 border border-amber-500/30" : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"



                  }">${escapeHtml(u.trading_mode)}</span>



                  <span class="text-[8px] font-mono px-1.5 py-0.2 rounded font-bold bg-cyan-950/50 text-cyan-400 border border-cyan-500/30" title="Signal Source">${escapeHtml(u.signal_source === "AI_ONLY" ? "RL_DQN" : (u.signal_source || "BLEND"))}</span>



                  ${



                    u.has_kalshi_keys



                      ? '<span class="text-[8px] font-mono text-emerald-400 bg-emerald-950/60 px-1 rounded border border-emerald-500/30">API KEY </span>'



                      : '<span class="text-[8px] font-mono text-slate-500 bg-slate-900 px-1 rounded">NO KEYS</span>'



                  }



                </div>



              </div>



            </div>







            <!-- AI Autotrader Toggle Switch -->



            <div class="flex flex-col items-end gap-1 shrink-0" onclick="event.stopPropagation()">



              <label class="relative inline-flex items-center cursor-pointer" title="Toggle AI Auto-Trading">



                <input type="checkbox" ${u.ai_enabled ? "checked" : ""} onchange="window.quickToggleAi(${u.id}, this.checked)" class="sr-only peer">



                <div class="w-8 h-4 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-cyan-500"></div>



              </label>



              <span class="text-[8px] font-mono font-bold uppercase ${u.ai_enabled ? "text-cyan-400" : "text-slate-500"}">${



          u.ai_enabled ? "AI ACTIVE" : "OFF"



        }</span>



            </div>



          </div>







          <!-- Bottom Metric Row: Kalshi Balance | Paper Balance | Win Rate | Net PnL -->



          <div class="grid grid-cols-4 gap-1.5 pt-2 border-t border-slate-800/80 text-[10px] font-mono">



            <div>



              <div class="text-[7.5px] text-slate-500 uppercase">Kalshi Bal</div>



              <div class="${kalshiBalColor} truncate" title="Live Kalshi API Account Balance">${kalshiBalText}</div>



            </div>



            <div>



              <div class="text-[7.5px] text-slate-500 uppercase">Paper Bal</div>



              <div class="font-bold text-slate-300 truncate">$${(u.paper_balance || 0).toFixed(2)}</div>



            </div>



            <div>



              <div class="text-[7.5px] text-slate-500 uppercase">Win Rate</div>



              <div class="font-bold text-slate-200">${u.win_rate || 0}%</div>



            </div>



            <div class="text-right">



              <div class="text-[7.5px] text-slate-500 uppercase">Net P&L</div>



              <div class="font-bold ${pnlClass}">${pnlText}</div>



            </div>



          </div>



        </div>



      `;



      })



      .join("");



  }







  function selectUserToEdit(userId) {



    selectedUserId = userId;



    try {



      localStorage.setItem("admin_selected_user_id", userId);



    } catch (_) {}



    renderUserList();



    const user = adminUsersList.find((u) => u.id === userId);



    if (user) {



      renderUserDetail(user);



      if (window.innerWidth < 1024) {



        switchAdminMobileTab("settings");



      }



    }



  }







  function renderUserDetail(u) {



    const detailPanel = document.getElementById("adminUserDetailPanel");



    if (!detailPanel) return;







    // Prevent overwriting panel if the admin is actively editing a field



    const active = document.activeElement;



    if (active && detailPanel.contains(active) && ['INPUT', 'SELECT', 'TEXTAREA'].includes(active.tagName)) {



        return;



    }







    const kalshiBalNum = u.kalshi_balance !== null && u.kalshi_balance !== undefined && !isNaN(u.kalshi_balance)



      ? Number(u.kalshi_balance)



      : (u.live_balance !== null && u.live_balance !== undefined && !isNaN(u.live_balance) ? Number(u.live_balance) : null);



    const hasKalshi = u.has_kalshi_keys && kalshiBalNum !== null;



    const kalshiBalText = hasKalshi ? `$${kalshiBalNum.toFixed(2)}` : (u.has_kalshi_keys ? "Syncing..." : "No Keys");







    detailPanel.innerHTML = `



      <div class="space-y-4">



        <!-- Mobile Return Button -->



        <button type="button" onclick="window.switchAdminMobileTab('users')" class="lg:hidden mb-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-cyan-300 rounded-lg text-xs font-bold flex items-center gap-1.5 border border-slate-700 active:scale-95 transition-all">



          <span> Back to Users List</span>



        </button>







        <!-- User Header Card -->



        <div class="flex items-center justify-between p-3.5 bg-slate-900 border border-slate-800 rounded-xl">



          <div class="flex items-center gap-3">



            <div class="w-10 h-10 rounded-xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 flex items-center justify-center font-black text-sm overflow-hidden bg-cover bg-center"
              ${u.profile_picture_url ? `style="background-image: url('${escapeHtml(u.profile_picture_url)}'); border-color: transparent;"` : ''}>
              ${u.profile_picture_url ? '' : (u.username ? escapeHtml(u.username.substring(0, 2).toUpperCase()) : `U${u.id}`)}
            </div>



            <div>



              <div class="flex items-center gap-2">



                <h3 class="text-sm font-black text-white">${escapeHtml(u.username)}</h3>



                <span class="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300">User ID: #${u.id}</span>



                <span class="text-[9px] font-mono px-1.5 py-0.5 rounded ${



                  u.role === "admin" ? "bg-amber-500/20 text-amber-300 border border-amber-500/40" : "bg-slate-800 text-slate-400"



                }">${escapeHtml(String(u.role || "user").toUpperCase())}</span>



              </div>



              <div class="text-[10px] text-slate-400 font-mono mt-0.5">



                Total Trades: <span class="text-white font-bold">${u.total_trades || 0}</span>  Win Rate: <span class="text-white font-bold">${u.win_rate || 0}%</span>  P&L: <span class="${(u.net_pnl || 0) >= 0 ? "text-emerald-400" : "text-rose-400"} font-bold">$${(u.net_pnl || 0).toFixed(2)}</span>



              </div>



            </div>



          </div>



          <div class="flex items-center gap-2">



            <button type="button" onclick="window.switchUserDetailTab('trades')" class="px-2.5 py-1.5 bg-cyan-950/70 hover:bg-cyan-900 text-cyan-300 border border-cyan-500/40 rounded-lg text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5 transition-all active:scale-95 cursor-pointer shadow-sm shadow-cyan-950/40" title="View trade ledger in panel">



              <span> Trades (${u.total_trades || 0})</span>



            </button>



            <a href="/trades?user=${u.id}" target="_blank" class="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 rounded-lg text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 transition-all active:scale-95" title="Open full trade ledger in new tab">



              



            </a>



            <button type="button" onclick="window.confirmDeleteUser(${Number(u.id)}, ${escapeHtml(JSON.stringify(String(u.username || '')))})" class="px-2.5 py-1.5 bg-rose-950/60 hover:bg-rose-900 text-rose-300 hover:text-white border border-rose-500/40 rounded-lg text-[10px] font-bold uppercase tracking-wider flex items-center gap-1 transition-all active:scale-95 cursor-pointer shadow-sm shadow-rose-950/40" title="Permanently delete user account">



              <span> Delete</span>



            </button>



          </div>



        </div>







        <!-- Real-Time Kalshi Account Balance Card -->



        <div class="p-3 bg-slate-900/90 border ${hasKalshi ? 'border-emerald-500/40 shadow-lg shadow-emerald-500/5' : 'border-slate-800'} rounded-xl flex flex-wrap items-center justify-between gap-3">



          <div class="flex items-center gap-3 min-w-0">



            <div class="w-9 h-9 rounded-xl ${hasKalshi ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'bg-slate-800 text-slate-400 border border-slate-700'} flex items-center justify-center text-lg font-bold shrink-0">



              



            </div>



            <div class="min-w-0">



              <div class="flex items-center gap-2">



                <span class="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-bold">Kalshi Account Balance</span>



                <span class="text-[8px] font-mono px-1.5 py-0.2 rounded font-bold ${hasKalshi ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : (u.has_kalshi_keys ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-slate-800 text-slate-400')}">${hasKalshi ? 'LIVE API SYNCED' : (u.has_kalshi_keys ? 'SYNCING' : 'NO KEYS')}</span>



              </div>



              <div class="text-xl font-black font-mono tracking-tight ${hasKalshi ? 'text-emerald-400' : 'text-slate-500'}">



                ${hasKalshi ? `$${kalshiBalNum.toFixed(2)}` : (u.has_kalshi_keys ? 'Syncing...' : 'No Kalshi Keys Configured')}



              </div>



            </div>



          </div>



          <div class="text-right shrink-0">



            <div class="text-[9px] font-mono text-slate-400">Kalshi Key ID</div>



            <div class="text-xs font-mono font-bold ${u.has_kalshi_keys ? 'text-cyan-300' : 'text-slate-600'}">



              ${u.has_kalshi_keys ? `${(u.kalshi_key_id || '').substring(0, 10)}...` : 'Not Connected'}



            </div>



          </div>



        </div>







        <!-- Navigation Sub-Tabs -->



        <div class="flex items-center justify-between border-b border-slate-800 pb-2">



          <div class="flex items-center gap-2">



            <button type="button" id="tabBtnUserSettings" onclick="window.switchUserDetailTab('settings')" 



                    class="px-3.5 py-1.5 rounded-lg text-xs font-bold font-mono uppercase tracking-wider transition-all cursor-pointer ${currentUserDetailTab === 'settings' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/10' : 'text-slate-400 hover:text-white hover:bg-slate-800 border border-transparent'}">



               🤖 Bot Settings



            </button>



            <button type="button" id="tabBtnUserTrades" onclick="window.switchUserDetailTab('trades')" 



                    class="px-3.5 py-1.5 rounded-lg text-xs font-bold font-mono uppercase tracking-wider transition-all cursor-pointer ${currentUserDetailTab === 'trades' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/10' : 'text-slate-400 hover:text-white hover:bg-slate-800 border border-transparent'}">



               User Trades (${u.total_trades || 0})



            </button>



          </div>



          <div class="text-[9px] font-mono text-slate-500 hidden sm:block">



            ${currentUserDetailTab === 'trades' ? 'Real-Time Ledger' : 'Active Bot Parameters'}



          </div>



        </div>







        <!-- Section 1: Settings Form -->



        <div id="adminUserConfigSection" class="${currentUserDetailTab === 'settings' ? 'block' : 'hidden'} space-y-3.5">



          <form id="adminUserConfigForm" class="space-y-3.5">



          



          <!-- Section 1: Account & Execution Mode -->



          <div class="p-3 bg-slate-900/60 border border-slate-800/80 rounded-xl space-y-2.5">



            <div class="flex items-center justify-between text-xs font-bold text-slate-300 pb-1.5 border-b border-slate-800">



              <span class="flex items-center gap-1.5 text-cyan-400">



                <span>⚙️</span> 📊 Mode & Account State



              </span>



              <span class="text-[9px] font-mono text-slate-500 uppercase">Core Profile</span>



            </div>







            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">



              <div>



                <label class="block text-[9px] font-mono uppercase text-slate-400 mb-1">Trading Mode</label>



                <select id="edit_trading_mode" onchange="window.handleTradingModeChange(this.value)" class="w-full bg-slate-950 border border-slate-700 rounded-lg py-1.5 px-2 text-xs font-bold text-white focus:border-cyan-500 focus:outline-none">



                  <option value="PAPER" ${u.trading_mode === "PAPER" ? "selected" : ""}> 📄 PAPER</option>



                  <option value="LIVE" ${u.trading_mode === "LIVE" ? "selected" : ""}> LIVE (Kalshi API)</option>



                </select>



              </div>







              <div>



                <label id="lbl_user_balance" class="block text-[9px] font-mono uppercase text-slate-400 mb-1">${u.trading_mode === "LIVE" ? "Live Balance ($)" : "Paper Balance ($)"}</label>



                <div class="flex flex-col sm:flex-row flex-wrap gap-1.5 sm:gap-1 items-start sm:items-center">



                  <div class="flex w-full gap-1">



                      <input type="text" id="edit_paper_balance" value="${u.trading_mode === 'LIVE' ? (u.has_kalshi_keys && u.live_balance !== null && u.live_balance !== undefined && !isNaN(u.live_balance) ? Number(u.live_balance).toFixed(2) : '***.**') : (u.paper_balance || 500.0)}" ${u.trading_mode === 'LIVE' && !(u.has_kalshi_keys && u.live_balance !== null && u.live_balance !== undefined && !isNaN(u.live_balance)) ? 'readonly' : ''} class="flex-1 bg-slate-950 border ${u.trading_mode === 'LIVE' && !(u.has_kalshi_keys && u.live_balance !== null && u.live_balance !== undefined && !isNaN(u.live_balance)) ? 'border-amber-500/40 bg-amber-950/20 text-amber-400' : 'border-slate-700 text-emerald-400'} rounded-lg py-1.5 px-2 text-xs font-mono font-bold focus:border-cyan-500 focus:outline-none" title="${u.trading_mode === 'LIVE' && !(u.has_kalshi_keys && u.live_balance !== null && u.live_balance !== undefined && !isNaN(u.live_balance)) ? 'Live balance unavailable' : 'Account balance'}">



                      <button type="button" id="btn_quick_reset_balance" onclick="window.quickResetBalance(${u.id})" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 rounded-lg text-[9px] font-bold ${u.trading_mode === 'LIVE' ? 'hidden' : ''}" title="Reset balance to $500"> 🔄 $500</button>



                  </div>



                  <span id="live_balance_status_badge" class="${u.trading_mode === 'LIVE' ? '' : 'hidden'} text-[8px] font-mono px-1.5 py-1 rounded ${u.has_kalshi_keys && u.live_balance !== null && u.live_balance !== undefined && !isNaN(u.live_balance) ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'} whitespace-nowrap">${u.has_kalshi_keys && u.live_balance !== null && u.live_balance !== undefined && !isNaN(u.live_balance) ? 'SYNCED' : '***.**'}</span>



                </div>



              </div>







              <div>



                <label class="block text-[9px] font-mono uppercase text-slate-400 mb-1">Account Active</label>



                <div class="flex items-center h-[34px]">



                  <label class="relative inline-flex items-center cursor-pointer">



                    <input type="checkbox" id="edit_is_active" ${u.is_active ? "checked" : ""} class="sr-only peer">



                    <div class="w-8 h-4 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-emerald-500"></div>



                  </label>



                  <span class="ml-2 text-[10px] font-mono text-slate-300">Active Login</span>



                </div>



              </div>



            </div>



          </div>







          <!-- Section 2: Automation & AI Toggles -->



          <div class="p-3 bg-slate-900/60 border border-slate-800/80 rounded-xl space-y-2.5">



            <div class="flex items-center justify-between text-xs font-bold text-slate-300 pb-1.5 border-b border-slate-800">



              <span class="flex items-center gap-1.5 text-cyan-400 cursor-pointer group" onclick="toggleAdminGlassInfo('auto_trader', event)">



                <span>⚡</span> ⚙️ Autonomous Execution Toggles



                <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-cyan-500/20 border border-white/10 flex items-center justify-center text-[9px] font-bold text-gray-400 transition-all ml-1">i</span>



              </span>



              <span class="text-[9px] font-mono text-slate-500 uppercase">Automation Rules</span>



            </div>







            <div class="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs">



              <div class="p-2 rounded-lg bg-slate-950/70 border border-slate-800/80 flex items-center justify-between">



                <div>



                  <div class="text-[10px] font-bold text-white">AI Auto-Trader</div>



                  <div class="text-[8px] text-slate-500">Autonomous execution</div>



                </div>



                <label class="relative inline-flex items-center cursor-pointer">



                  <input type="checkbox" id="edit_ai_enabled" ${u.ai_enabled ? "checked" : ""} class="sr-only peer">



                  <div class="w-7 h-4 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-cyan-500"></div>



                </label>



              </div>







              <div class="p-2 rounded-lg bg-slate-950/70 border border-slate-800/80 flex items-center justify-between">



                <div>



                  <div class="text-[10px] font-bold text-amber-300">Auto Force Trade</div>



                  <div class="text-[8px] text-slate-500">Trades underlying on PASS</div>



                </div>



                <label class="relative inline-flex items-center cursor-pointer">



                  <input type="checkbox" id="edit_auto_force_trade" ${u.auto_force_trade ? "checked" : ""} class="sr-only peer">



                  <div class="w-7 h-4 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-amber-500"></div>



                </label>



              </div>







              <div class="p-2 rounded-lg bg-slate-950/70 border border-slate-800/80 flex items-center justify-between">



                <div>



                  <div class="text-[10px] font-bold text-cyan-300">1-Shot AI Trade</div>



                  <div class="text-[8px] text-slate-500">Executes single trade then halts</div>



                </div>



                <label class="relative inline-flex items-center cursor-pointer">



                  <input type="checkbox" id="edit_one_shot_ai" ${u.one_shot_ai ? "checked" : ""} class="sr-only peer">



                  <div class="w-7 h-4 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-cyan-500"></div>



                </label>



              </div>







              <div class="p-2 rounded-lg bg-slate-950/70 border border-slate-800/80 flex items-center justify-between">



                <div>



                  <div class="text-[10px] font-bold text-slate-200">Ignore PASS on Tech</div>



                  <div class="text-[8px] text-slate-500">Chart momentum takes over</div>



                </div>



                <label class="relative inline-flex items-center cursor-pointer">



                  <input type="checkbox" id="edit_ignore_pass_technical" ${u.ignore_pass_technical ? "checked" : ""} class="sr-only peer">



                  <div class="w-7 h-4 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-purple-500"></div>



                </label>



              </div>







              <div class="p-2 rounded-lg bg-slate-950/70 border border-slate-800/80 flex items-center justify-between gap-2">



                <div class="min-w-0">



                  <div class="text-[10px] font-bold text-slate-200">Edge Guard</div>



                  <div class="text-[8px] text-slate-500 flex items-center gap-1">Min edge



                    <input type="number" id="edit_min_edge_cents" value="${Number(u.min_edge_cents ?? 0)}" min="0" max="25" step="0.5" class="w-10 bg-slate-900 border border-slate-700 rounded px-1 py-0 text-[9px] text-white text-center">



                  </div>



                </div>



                <label class="relative inline-flex items-center cursor-pointer shrink-0">



                  <input type="checkbox" id="edit_edge_gate_enabled" ${u.edge_gate_enabled !== false ? "checked" : ""} class="sr-only peer">



                  <div class="w-7 h-4 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-emerald-500"></div>



                </label>



              </div>







              <div class="p-2 rounded-lg bg-slate-950/70 border border-slate-800/80 flex items-center justify-between">



                <div>



                  <div class="text-[10px] font-bold text-slate-200">One-Click Trade</div>



                  <div class="text-[8px] text-slate-500">Instant manual buttons</div>



                </div>



                <label class="relative inline-flex items-center cursor-pointer">



                  <input type="checkbox" id="edit_one_click_trade" ${u.one_click_trade ? "checked" : ""} class="sr-only peer">



                  <div class="w-7 h-4 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-emerald-500"></div>



                </label>



              </div>



            </div>



          </div>







          <!-- Section 3: Strategy & Signals -->



          <div class="p-3 bg-slate-900/60 border border-slate-800/80 rounded-xl space-y-2.5">



            <div class="flex items-center justify-between text-xs font-bold text-slate-300 pb-1.5 border-b border-slate-800">



              <span class="flex items-center gap-1.5 text-cyan-400 cursor-pointer group" onclick="toggleAdminGlassInfo('strategy', event)">



                 Strategy Archetype & Sizing



                <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-cyan-500/20 border border-white/10 flex items-center justify-center text-[9px] font-bold text-gray-400 transition-all ml-1">i</span>



              </span>



              <span class="text-[9px] font-mono text-slate-500 uppercase">Execution Logic</span>



            </div>







            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">



              <div>



                <label class="block text-[9px] font-mono uppercase text-slate-400 mb-1">Trading Style</label>



                <select id="edit_trading_style" class="w-full bg-slate-950 border border-slate-700 rounded-lg py-1.5 px-2 text-xs font-bold text-white focus:border-cyan-500 focus:outline-none">



                  <option value="AUTO" ${u.trading_style === "AUTO" ? "selected" : ""}>🤖 AUTO (Adaptive Regime)</option>



                  <option value="SNIPER" ${u.trading_style === "SNIPER" ? "selected" : ""}>🎯 SNIPER (High Conviction)</option>



                  <option value="PREDICTION" ${u.trading_style === "PREDICTION" ? "selected" : ""}>🔮 PREDICTION (Open Blended)</option>



                  <option value="MOMENTUM_SURFER" ${u.trading_style === "MOMENTUM_SURFER" ? "selected" : ""}>🏄 MOMENTUM (Trend Surfer)</option>



                  <option value="AMBUSH" ${u.trading_style === "AMBUSH" ? "selected" : ""}>🥷 AMBUSH (Fade Reversals)</option>



                  <option value="CHOP" ${u.trading_style === "CHOP" ? "selected" : ""}>🪓 CHOP (Mean Reversion)</option>



                </select>



              </div>







              <div>



                <label class="block text-[9px] font-mono uppercase text-slate-400 mb-1">Signal Source</label>



                <select id="edit_signal_source" class="w-full bg-slate-950 border border-slate-700 rounded-lg py-1.5 px-2 text-xs font-bold text-white focus:border-cyan-500 focus:outline-none">



                  <option value="RL_DQN" ${u.signal_source === "RL_DQN" || u.signal_source === "AI_ONLY" ? "selected" : ""}> Primary AI Engine (100% AI)</option>



                  <option value="BLEND" ${u.signal_source === "BLEND" || !u.signal_source ? "selected" : ""}>⚖️ BLEND (AI Model + Chart Confluence)</option>



                  <option value="TECHNICAL_ONLY" ${u.signal_source === "TECHNICAL_ONLY" || u.signal_source === "CHART_ONLY" ? "selected" : ""}> TECHNICAL_ONLY (100% Chart)</option>



                  <option value="ML_ENSEMBLE" ${u.signal_source === "ML_ENSEMBLE" ? "selected" : ""}> Secondary ML Engine (100% AI)</option>



                  <option value="RL_SCALPER" ${u.signal_source === "RL_SCALPER" ? "selected" : ""}> RL Scalper (testing  no trades until validated)</option>



                </select>



              </div>







              <div>



                <label class="block text-[9px] font-mono uppercase text-slate-400 mb-1">Trade Size ($)</label>



                <input type="number" step="1.0" min="5" max="5000" id="edit_trade_size_dollars" value="${u.trade_size_dollars || 5.0}" class="w-full bg-slate-950 border border-slate-700 rounded-lg py-1.5 px-2 text-xs font-mono font-bold text-white focus:border-cyan-500 focus:outline-none">



              </div>



            </div>



          </div>







          <!-- Section 4: Risk Limits & Exits -->



          <div class="p-3 bg-slate-900/60 border border-slate-800/80 rounded-xl space-y-2.5">



            <div class="flex items-center justify-between text-xs font-bold text-slate-300 pb-1.5 border-b border-slate-800">



              <span class="flex items-center gap-1.5 text-cyan-400 cursor-pointer group" onclick="toggleAdminGlassInfo('risk_limits', event)">



                 Risk Management & Profit Targets



                <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-cyan-500/20 border border-white/10 flex items-center justify-center text-[9px] font-bold text-gray-400 transition-all ml-1">i</span>



              </span>



              <span class="text-[9px] font-mono text-slate-500 uppercase">Protection</span>



            </div>







            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">



              <div>



                <label class="block text-[9px] font-mono uppercase text-slate-400 mb-1">Stop Loss (%)</label>



                <input type="number" step="0.5" min="1" max="100" id="edit_stop_loss_pct" value="${u.stop_loss_pct || 10.0}" class="w-full bg-slate-950 border border-slate-700 rounded-lg py-1.5 px-2 text-xs font-mono font-bold text-rose-400 focus:border-rose-500 focus:outline-none">



              </div>







              <div>



                <label class="block text-[9px] font-mono uppercase text-slate-400 mb-1">Take Profit (%)</label>



                <input type="number" step="1.0" min="1" max="500" id="edit_take_profit_pct" value="${u.take_profit_pct || 50.0}" class="w-full bg-slate-950 border border-slate-700 rounded-lg py-1.5 px-2 text-xs font-mono font-bold text-emerald-400 focus:border-emerald-500 focus:outline-none">



              </div>







              <div>



                <label class="block text-[9px] font-mono uppercase text-slate-400 mb-1">Max Daily Trades</label>



                <input type="number" step="1" min="1" max="100" id="edit_max_daily_trades" value="${u.max_daily_trades || 10}" class="w-full bg-slate-950 border border-slate-700 rounded-lg py-1.5 px-2 text-xs font-mono font-bold text-white focus:border-cyan-500 focus:outline-none">



              </div>







              <div>



                <label class="block text-[9px] font-mono uppercase text-slate-400 mb-1">Max Daily Risk ($)</label>



                <input type="number" step="5" min="5" max="10000" id="edit_max_daily_risk" value="${u.max_daily_risk || 50.0}" class="w-full bg-slate-950 border border-slate-700 rounded-lg py-1.5 px-2 text-xs font-mono font-bold text-white focus:border-cyan-500 focus:outline-none">



              </div>



            </div>







            <!-- Trailing Stop & Second Entry Row -->



            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-2 border-t border-slate-800">



              



              <!-- Trailing Stop Card -->



              <div class="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 space-y-2">



                <div class="flex items-center justify-between">



                  <span class="text-[10px] font-bold text-cyan-300">Trailing Stop Loss</span>



                  <label class="relative inline-flex items-center cursor-pointer">



                    <input type="checkbox" id="edit_trailing_stop_enabled" ${u.trailing_stop_enabled ? "checked" : ""} class="sr-only peer">



                    <div class="w-7 h-4 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-cyan-500"></div>



                  </label>



                </div>



                <div class="grid grid-cols-2 gap-2 text-[10px] font-mono">



                  <div>



                    <span class="text-[8px] text-slate-500 uppercase">Activation %</span>



                    <input type="number" step="1" id="edit_trailing_stop_activation_pct" value="${u.trailing_stop_activation_pct || 35.0}" class="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-1 text-white">



                  </div>



                  <div>



                    <span class="text-[8px] text-slate-500 uppercase">Distance %</span>



                    <input type="number" step="0.5" id="edit_trailing_stop_distance_pct" value="${u.trailing_stop_distance_pct || 6.0}" class="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-1 text-white">



                  </div>



                </div>



              </div>







              <!-- Second Entry After Scalp Card -->



              <div class="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 space-y-2">



                <div class="flex items-center justify-between">



                  <span class="text-[10px] font-bold text-emerald-300">Second Entry After Scalp</span>



                  <label class="relative inline-flex items-center cursor-pointer">



                    <input type="checkbox" id="edit_second_entry_enabled" ${u.second_entry_enabled ? "checked" : ""} class="sr-only peer">



                    <div class="w-7 h-4 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-emerald-500"></div>



                  </label>



                </div>



                <div class="flex items-center justify-between text-xs mt-2">

                  <span class="text-[10px] font-bold text-amber-300">Re-entry After Stop Loss</span>

                  <label class="relative inline-flex items-center cursor-pointer">

                    <input type="checkbox" id="edit_reentry_after_stop_loss" ${u.reentry_after_stop_loss ? "checked" : ""} class="sr-only peer">

                    <div class="w-7 h-4 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-amber-500"></div>

                  </label>

                </div>

                <div class="flex items-center justify-between text-xs mt-2">

                  <span class="text-[10px] font-bold text-cyan-300">Kelly Criterion Sizing</span>

                  <label class="relative inline-flex items-center cursor-pointer">

                    <input type="checkbox" id="edit_use_kelly_criterion" ${u.use_kelly_criterion ? "checked" : ""} class="sr-only peer">

                    <div class="w-7 h-4 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-cyan-500"></div>

                  </label>

                </div>

                <div class="text-[10px] font-mono mt-2">

                  <span class="text-[8px] text-slate-500 uppercase">Max Ask Price ($)</span>

                  <input type="number" step="0.01" min="0.05" max="0.99" id="edit_second_entry_max_ask" value="${u.second_entry_max_ask || 0.75}" class="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-1 text-white">

                </div>



              </div>







            </div>



          </div>







          <!-- Section 5: Model & Training Controls -->



          <div class="p-3 bg-slate-900/60 border border-slate-800/80 rounded-xl space-y-2.5">



            <div class="flex items-center justify-between text-xs font-bold text-slate-300 pb-1.5 border-b border-slate-800">



              <span class="flex items-center gap-1.5 text-purple-400 cursor-pointer group" onclick="toggleAdminGlassInfo('ai_model', event)">



                 AI Model & Reinforcement Learning



                <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-purple-500/20 border border-white/10 flex items-center justify-center text-[9px] font-bold text-gray-400 transition-all ml-1">i</span>



              </span>



              <span class="text-[9px] font-mono text-slate-500 uppercase">Deep Q-Network</span>



            </div>







            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs font-mono">



              <div>



                <label class="block text-[8px] uppercase text-slate-400 mb-1">Model Choice</label>



                <select id="edit_model_choice" class="w-full bg-slate-950 border border-slate-700 rounded py-1 px-1.5 text-xs text-white">



                  <option value="RL_DQN" ${u.model_choice === "RL_DQN" ? "selected" : ""}>Deep Q-Network (RL)</option>



                  <option value="Swarm" ${u.model_choice !== "RL_DQN" ? "selected" : ""}>God-Tier Swarm</option>



                </select>



              </div>



              <div>



                <label class="block text-[8px] uppercase text-slate-400 mb-1">Candle Window</label>



                <input type="number" step="100" id="edit_train_window" value="${u.train_window || 4000}" class="w-full bg-slate-950 border border-slate-700 rounded py-1 px-1.5 text-xs text-white">



              </div>



              <div>



                <label class="block text-[8px] uppercase text-slate-400 mb-1">L2 Reg (C)</label>



                <input type="number" step="0.1" id="edit_regularization_c" value="${u.regularization_c || 0.5}" class="w-full bg-slate-950 border border-slate-700 rounded py-1 px-1.5 text-xs text-white">



              </div>



              <div>



                <label class="block text-[8px] uppercase text-slate-400 mb-1">Class Weight</label>



                <select id="edit_class_weight" class="w-full bg-slate-950 border border-slate-700 rounded py-1 px-1.5 text-xs text-white">



                  <option value="balanced" ${u.class_weight === "balanced" ? "selected" : ""}>Balanced</option>



                  <option value="none" ${u.class_weight === "none" ? "selected" : ""}>None</option>



                </select>



              </div>



            </div>



          </div>







          <!-- Bottom Action Buttons -->



          <div class="flex items-center gap-3 pt-2">



            <button type="button" onclick="window.saveSelectedUserConfig();" id="btnSaveUserConfig" class="flex-1 py-2.5 px-4 bg-gradient-to-r from-cyan-500 to-cyan-400 hover:from-cyan-400 hover:to-cyan-300 text-slate-950 font-black text-xs uppercase tracking-wider rounded-xl shadow-lg shadow-cyan-500/20 active:scale-95 transition-all flex items-center justify-center gap-2 cursor-pointer">



              <span> Save & Apply User Settings</span>



            </button>



          </div>







          <!-- Section 6: Danger Zone -->



          <div class="p-3 bg-rose-950/20 border border-rose-500/30 rounded-xl flex items-center justify-between">



            <div>



              <div class="text-[11px] font-bold text-rose-300 flex items-center gap-1.5">



                 Danger Zone



              </div>



              <div class="text-[9px] text-slate-400 font-mono mt-0.5">Permanently delete this account, its trading profile, and trade history.</div>



            </div>



            <button type="button" onclick="window.confirmDeleteUser(${Number(u.id)}, ${escapeHtml(JSON.stringify(String(u.username || '')))})" class="px-3 py-1.5 bg-rose-600/90 hover:bg-rose-600 text-white rounded-lg text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5 transition-all active:scale-95 shadow-md shadow-rose-900/50 cursor-pointer">



              <span> Delete Account</span>



            </button>



          </div>







        </form>



      </div>







      <!-- Section 2: Trades Ledger Section -->



      <div id="adminUserTradesSection" class="${currentUserDetailTab === 'trades' ? 'block' : 'hidden'} space-y-3.5">



        <!-- Summary Metric Cards -->



        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono">



          <div class="p-2.5 bg-slate-900/80 border border-slate-800 rounded-xl">



            <div class="text-[9px] uppercase text-slate-400">Total Trades</div>



            <div class="text-base font-bold text-white mt-0.5" id="userTradesTotal">${u.total_trades || 0}</div>



          </div>



          <div class="p-2.5 bg-slate-900/80 border border-slate-800 rounded-xl">



            <div class="text-[9px] uppercase text-slate-400">Win Rate</div>



            <div class="text-base font-bold text-emerald-400 mt-0.5" id="userTradesWinRate">${u.win_rate || 0}%</div>



          </div>



          <div class="p-2.5 bg-slate-900/80 border border-slate-800 rounded-xl">



            <div class="text-[9px] uppercase text-slate-400">Net Realized P&L</div>



            <div class="text-base font-bold mt-0.5 ${(u.net_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}" id="userTradesNetPnl">



              ${(u.net_pnl || 0) >= 0 ? "+$" : "-$"}${Math.abs(u.net_pnl || 0).toFixed(2)}



            </div>



          </div>



          <div class="p-2.5 bg-slate-900/80 border border-slate-800 rounded-xl">



            <div class="text-[9px] uppercase text-slate-400">Open Positions</div>



            <div class="text-base font-bold text-cyan-400 mt-0.5" id="userTradesOpenCount">--</div>



          </div>



        </div>







        <!-- Filter / Search Controls Bar -->



        <div class="p-2.5 bg-slate-900/60 border border-slate-800 rounded-xl flex flex-wrap items-center justify-between gap-2 text-xs">



          <div class="flex items-center gap-1.5 flex-wrap">



            <span class="text-[9px] font-mono uppercase text-slate-500 mr-1">Mode:</span>



            <button type="button" onclick="window.setTradeFilterMode('ALL')" data-tmode="ALL" class="admin-tmode-pill px-2 py-0.5 text-[10px] font-mono font-bold rounded-md bg-cyan-900/50 text-cyan-300 border border-cyan-500/30">ALL</button>



            <button type="button" onclick="window.setTradeFilterMode('PAPER')" data-tmode="PAPER" class="admin-tmode-pill px-2 py-0.5 text-[10px] font-mono font-bold rounded-md text-slate-400 hover:text-white">PAPER</button>



            <button type="button" onclick="window.setTradeFilterMode('LIVE')" data-tmode="LIVE" class="admin-tmode-pill px-2 py-0.5 text-[10px] font-mono font-bold rounded-md text-slate-400 hover:text-white">LIVE</button>







            <span class="text-[9px] font-mono uppercase text-slate-500 ml-2 mr-1">Status:</span>



            <button type="button" onclick="window.setTradeFilterStatus('ALL')" data-tstatus="ALL" class="admin-tstatus-pill px-2 py-0.5 text-[10px] font-mono font-bold rounded-md bg-cyan-900/50 text-cyan-300 border border-cyan-500/30">ALL</button>



            <button type="button" onclick="window.setTradeFilterStatus('CLOSED')" data-tstatus="CLOSED" class="admin-tstatus-pill px-2 py-0.5 text-[10px] font-mono font-bold rounded-md text-slate-400 hover:text-white">CLOSED</button>



            <button type="button" onclick="window.setTradeFilterStatus('OPEN')" data-tstatus="OPEN" class="admin-tstatus-pill px-2 py-0.5 text-[10px] font-mono font-bold rounded-md text-slate-400 hover:text-white">OPEN</button>



            <button type="button" onclick="window.setTradeFilterStatus('WINS')" data-tstatus="WINS" class="admin-tstatus-pill px-2 py-0.5 text-[10px] font-mono font-bold rounded-md text-slate-400 hover:text-white">WINS</button>



            <button type="button" onclick="window.setTradeFilterStatus('LOSSES')" data-tstatus="LOSSES" class="admin-tstatus-pill px-2 py-0.5 text-[10px] font-mono font-bold rounded-md text-slate-400 hover:text-white">LOSSES</button>



          </div>







          <div class="flex items-center gap-2">



            <input type="text" id="userTradeSearchInput" oninput="window.filterUserTradesList(this.value)" placeholder="Search ticker, side..." class="bg-slate-950 border border-slate-700/80 rounded-lg px-2.5 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono w-40">



            <button type="button" onclick="window.loadUserTrades(${u.id})" class="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg text-xs" title="Refresh trade list">



              



            </button>



          </div>



        </div>







        <!-- Trades List Container -->



        <div id="adminUserTradesList" class="space-y-2 max-h-[480px] overflow-y-auto pr-1 admin-custom-scroll">



          <div class="p-8 text-center text-slate-500 font-mono text-xs">



            Loading user trades...



          </div>



        </div>



      </div>



    </div>



  `;







  if (currentUserDetailTab === "trades") {



    loadUserTrades(u.id);



  }



}







  window.handleTradingModeChange = function (mode) {



    const u = selectedUserId ? adminUsersList.find((x) => x.id === selectedUserId) : null;



    const balInput = document.getElementById("edit_paper_balance");



    const lbl = document.getElementById("lbl_user_balance");



    const resetBtn = document.getElementById("btn_quick_reset_balance");



    const badge = document.getElementById("live_balance_status_badge");







    if (mode === "LIVE") {



      if (lbl) lbl.textContent = "Live Balance ($)";



      if (resetBtn) resetBtn.classList.add("hidden");



      const hasLiveBal = u && u.has_kalshi_keys && u.live_balance !== null && u.live_balance !== undefined && !isNaN(u.live_balance);



      if (balInput) {



        if (!hasLiveBal) {



          balInput.value = "***.**";



          balInput.readOnly = true;



          balInput.className = "flex-1 bg-slate-950 border border-amber-500/40 bg-amber-950/20 rounded-lg py-1.5 px-2 text-xs font-mono font-bold text-amber-400 focus:outline-none";



          balInput.title = "Live balance unavailable (No active Kalshi API keys linked or connection unavailable)";



        } else {



          balInput.value = Number(u.live_balance).toFixed(2);



          balInput.readOnly = true;



          balInput.className = "flex-1 bg-slate-950 border border-emerald-500/40 rounded-lg py-1.5 px-2 text-xs font-mono font-bold text-emerald-400 focus:outline-none";



          balInput.title = "Live Kalshi account balance";



        }



      }



      if (badge) {



        badge.classList.remove("hidden");



        badge.textContent = hasLiveBal ? "SYNCED" : "***.**";



        badge.className = `text-[8px] font-mono px-1.5 py-1 rounded whitespace-nowrap ${



          hasLiveBal ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" : "bg-amber-500/20 text-amber-300 border border-amber-500/30"



        }`;



      }



    } else {



      // PAPER



      if (lbl) lbl.textContent = "Paper Balance ($)";



      if (resetBtn) resetBtn.classList.remove("hidden");



      if (badge) badge.classList.add("hidden");



      if (balInput) {



        balInput.readOnly = false;



        balInput.value = (u && u.paper_balance !== undefined ? u.paper_balance : 500.0).toFixed(2);



        balInput.className = "flex-1 bg-slate-950 border border-slate-700 rounded-lg py-1.5 px-2 text-xs font-mono font-bold text-emerald-400 focus:border-cyan-500 focus:outline-none";



        balInput.title = "Paper trading balance ($)";



      }



    }



  };







  async function saveSelectedUserConfig() {



    if (!selectedUserId) return;



    const saveBtn = document.getElementById("btnSaveUserConfig");



    if (saveBtn) {



      saveBtn.disabled = true;



      saveBtn.innerText = " Saving...";



    }







    try {



      const balStr = document.getElementById("edit_paper_balance")?.value;



      const parsedBal = (balStr && balStr !== "***.**") ? parseFloat(balStr) : null;



      const payload = {



        trading_mode: document.getElementById("edit_trading_mode")?.value,



        is_active: document.getElementById("edit_is_active")?.checked,



        ai_enabled: document.getElementById("edit_ai_enabled")?.checked,



        auto_force_trade: document.getElementById("edit_auto_force_trade")?.checked,



        one_shot_ai: document.getElementById("edit_one_shot_ai")?.checked,



        ignore_pass_technical: document.getElementById("edit_ignore_pass_technical")?.checked,



        edge_gate_enabled: document.getElementById("edit_edge_gate_enabled")?.checked,



        min_edge_cents: Math.min(25, Math.max(0, parseFloat(document.getElementById("edit_min_edge_cents")?.value) || 0)),



        one_click_trade: document.getElementById("edit_one_click_trade")?.checked,



        trading_style: document.getElementById("edit_trading_style")?.value,



        signal_source: document.getElementById("edit_signal_source")?.value,



        trade_size_dollars: parseFloat(document.getElementById("edit_trade_size_dollars")?.value || 5.0),



        stop_loss_pct: parseFloat(document.getElementById("edit_stop_loss_pct")?.value || 10.0),



        take_profit_pct: parseFloat(document.getElementById("edit_take_profit_pct")?.value || 50.0),



        max_daily_trades: parseInt(document.getElementById("edit_max_daily_trades")?.value || 10),



        max_daily_risk: parseFloat(document.getElementById("edit_max_daily_risk")?.value || 50.0),



        trailing_stop_enabled: document.getElementById("edit_trailing_stop_enabled")?.checked,



        trailing_stop_activation_pct: parseFloat(document.getElementById("edit_trailing_stop_activation_pct")?.value || 35.0),



        trailing_stop_distance_pct: parseFloat(document.getElementById("edit_trailing_stop_distance_pct")?.value || 6.0),



        second_entry_enabled: document.getElementById("edit_second_entry_enabled")?.checked,



        second_entry_max_ask: parseFloat(document.getElementById("edit_second_entry_max_ask")?.value || 0.75),



        reentry_after_stop_loss: document.getElementById("edit_reentry_after_stop_loss")?.checked,

        use_kelly_criterion: document.getElementById("edit_use_kelly_criterion")?.checked ?? false,

        model_choice: document.getElementById("edit_model_choice")?.value,



        train_window: parseInt(document.getElementById("edit_train_window")?.value || 4000),



        regularization_c: parseFloat(document.getElementById("edit_regularization_c")?.value || 0.5),



        class_weight: document.getElementById("edit_class_weight")?.value,



      };



      // The balance box shows the Kalshi balance for LIVE users - never save that as paper balance



      if (payload.trading_mode === "PAPER" && parsedBal !== null && !isNaN(parsedBal)) {



        payload.paper_balance = parsedBal;



      }







      const resp = await fetch(`/api/admin/users/${selectedUserId}/config`, {



        method: "POST",



        headers: getAdminAuthHeaders(),



        body: JSON.stringify(payload),



      });







      const res = await resp.json();



      if (!resp.ok || !res.success) {



        const detail = Array.isArray(res.detail)



          ? res.detail.map(d => `${(d.loc || []).slice(-1)[0] || "value"}: ${d.msg}`).join("; ")



          : res.detail;



        throw new Error(detail || res.message || "Failed to update settings");



      }







      const savedUid = selectedUserId;



      showAdminToast(`User #${selectedUserId} settings saved and synchronized successfully!`, "success");



      await fetchAdminUsers();



      if (savedUid) {



        selectUserToEdit(savedUid);



      }



    } catch (err) {



      console.error("[AdminUserPanel] Save error:", err);



      showAdminToast(`Save failed: ${err.message}`, "error");



    } finally {



      if (saveBtn) {



        saveBtn.disabled = false;



        saveBtn.innerText = " Save & Apply User Settings";



      }



    }



  }







  async function quickToggleAi(userId, newEnabled) {



    try {



      const resp = await fetch(`/api/admin/users/${userId}/toggle_ai`, {



        method: "POST",



        headers: getAdminAuthHeaders(),



        body: JSON.stringify({ enabled: newEnabled }),



      });



      const res = await resp.json();



      if (!resp.ok || !res.success) {



        throw new Error(res.detail || "Failed to toggle AI state");



      }



      showAdminToast(`User #${userId} AI Auto-Trader ${newEnabled ? "ENABLED" : "DISABLED"}`, "success");



      const savedUid = selectedUserId;



      await fetchAdminUsers();



      if (savedUid) {



        selectUserToEdit(savedUid);



      }



    } catch (err) {



      console.error("[AdminUserPanel] Toggle error:", err);



      showAdminToast(`Toggle failed: ${err.message}`, "error");



    }



  }







  async function quickResetBalance(userId) {



    if (!confirm(`Reset paper trading balance for user #${userId} to $500.00?`)) return;



    try {



      const resp = await fetch(`/api/admin/users/${userId}/reset_balance`, {



        method: "POST",



        headers: getAdminAuthHeaders(),



        body: JSON.stringify({ balance: 500.0 }),



      });



      const res = await resp.json();



      if (!resp.ok || !res.success) {



        throw new Error(res.detail || "Failed to reset balance");



      }



      showAdminToast(`User #${userId} paper balance reset to $500.00`, "success");



      const savedUid = selectedUserId;



      await fetchAdminUsers();



      if (savedUid) {



        selectUserToEdit(savedUid);



      }



    } catch (err) {



      console.error("[AdminUserPanel] Reset balance error:", err);



      showAdminToast(`Reset failed: ${err.message}`, "error");



    }



  }







  async function confirmDeleteUser(userId, username) {



    const confirmed = confirm(



      ` PERMANENT ACCOUNT DELETION\n\nAre you sure you want to permanently delete user account '${username}' (User ID: #${userId})?\n\nThis will remove their profile from the database, purge their trading history, and evict active background executors.\n\nClick OK to confirm permanent deletion.`



    );



    if (!confirmed) return;







    try {



      const resp = await fetch(`/api/admin/users/${userId}`, {



        method: "DELETE",



        headers: getAdminAuthHeaders(),



      });



      const res = await resp.json();



      if (!resp.ok || !res.success) {



        throw new Error(res.detail || res.message || "Failed to delete account");



      }







      showAdminToast(`Account '${username}' (#${userId}) permanently deleted.`, "success");







      if (selectedUserId === userId) {



        selectedUserId = null;



      }







      await fetchAdminUsers();







      if (window.innerWidth < 1024) {



        switchAdminMobileTab("users");



      }



    } catch (err) {



      console.error("[AdminUserPanel] Delete error:", err);



      showAdminToast(`Delete failed: ${err.message}`, "error");



    }



  }







  function openAdminUserPanel() {



    const modal = document.getElementById("adminUserModal");



    if (modal) {



      modal.classList.remove("hidden");



      document.body.style.overflow = 'hidden';



      fetchAdminUsers();
      fetchAdminTickets(true);



    }



  }







  function closeAdminUserPanel() {



    const modal = document.getElementById("adminUserModal");



    if (modal) {



      modal.classList.add("hidden");



      document.body.style.overflow = '';



    }



  }







  function setFilterSearch(val) {



    currentSearch = val;



    renderUserList();



  }







  function setFilterMode(mode) {



    currentModeFilter = mode;



    document.querySelectorAll(".admin-mode-pill").forEach((btn) => {



      if (btn.getAttribute("data-mode") === mode) {



        btn.className = "admin-mode-pill px-2.5 py-1 text-[10px] font-bold rounded-md bg-cyan-900/50 text-cyan-300 border border-cyan-500/30";



      } else {



        btn.className = "admin-mode-pill px-2.5 py-1 text-[10px] font-bold rounded-md text-slate-400 hover:text-slate-200";



      }



    });



    renderUserList();



  }







  function setFilterAi(ai) {



    currentAiFilter = ai;



    document.querySelectorAll(".admin-ai-pill").forEach((btn) => {



      if (btn.getAttribute("data-ai") === ai) {



        btn.className = "admin-ai-pill px-2.5 py-1 text-[10px] font-bold rounded-md bg-cyan-900/50 text-cyan-300 border border-cyan-500/30";



      } else {



        btn.className = "admin-ai-pill px-2.5 py-1 text-[10px] font-bold rounded-md text-slate-400 hover:text-slate-200";



      }



    });



    renderUserList();



  }







  function switchAdminMobileTab(tab) {



    const listEl = document.getElementById("adminUserListContainer");



    const detailEl = document.getElementById("adminUserDetailPanel");



    const tabUsers = document.getElementById("adminTabUsers");



    const tabSettings = document.getElementById("adminTabSettings");







    if (tab === "users") {



      if (listEl) listEl.classList.remove("hidden");



      if (detailEl) detailEl.classList.add("hidden");



      if (tabUsers) tabUsers.className = "flex-1 py-2.5 px-3 text-center text-xs font-bold text-cyan-400 border-b-2 border-cyan-400 transition-all flex items-center justify-center gap-1.5";



      if (tabSettings) tabSettings.className = "flex-1 py-2.5 px-3 text-center text-xs font-bold text-slate-400 hover:text-slate-200 border-b-2 border-transparent transition-all flex items-center justify-center gap-1.5";



    } else {



      if (listEl) listEl.classList.add("hidden");



      if (detailEl) detailEl.classList.remove("hidden");



      if (tabUsers) tabUsers.className = "flex-1 py-2.5 px-3 text-center text-xs font-bold text-slate-400 hover:text-slate-200 border-b-2 border-transparent transition-all flex items-center justify-center gap-1.5";



      if (tabSettings) tabSettings.className = "flex-1 py-2.5 px-3 text-center text-xs font-bold text-cyan-400 border-b-2 border-cyan-400 transition-all flex items-center justify-center gap-1.5";



    }



  }







  function switchUserDetailTab(tab) {



    currentUserDetailTab = tab;



    const settingsSection = document.getElementById("adminUserConfigSection");



    const tradesSection = document.getElementById("adminUserTradesSection");



    const tabBtnSettings = document.getElementById("tabBtnUserSettings");



    const tabBtnTrades = document.getElementById("tabBtnUserTrades");







    if (tab === "settings") {



      if (settingsSection) settingsSection.classList.remove("hidden");



      if (tradesSection) tradesSection.classList.add("hidden");



      if (tabBtnSettings) {



        tabBtnSettings.className = "px-3.5 py-1.5 rounded-lg text-xs font-bold font-mono uppercase tracking-wider transition-all cursor-pointer bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/10";



      }



      if (tabBtnTrades) {



        tabBtnTrades.className = "px-3.5 py-1.5 rounded-lg text-xs font-bold font-mono uppercase tracking-wider transition-all cursor-pointer text-slate-400 hover:text-white hover:bg-slate-800 border border-transparent";



      }



    } else {



      if (settingsSection) settingsSection.classList.add("hidden");



      if (tradesSection) tradesSection.classList.remove("hidden");



      if (tabBtnSettings) {



        tabBtnSettings.className = "px-3.5 py-1.5 rounded-lg text-xs font-bold font-mono uppercase tracking-wider transition-all cursor-pointer text-slate-400 hover:text-white hover:bg-slate-800 border border-transparent";



      }



      if (tabBtnTrades) {



        tabBtnTrades.className = "px-3.5 py-1.5 rounded-lg text-xs font-bold font-mono uppercase tracking-wider transition-all cursor-pointer bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/10";



      }







      if (selectedUserId) {



        loadUserTrades(selectedUserId);



      }



    }



  }







  async function loadUserTrades(userId) {



    if (!userId) return;



    const listEl = document.getElementById("adminUserTradesList");



    if (listEl) {



      listEl.innerHTML = `



        <div class="p-8 text-center text-slate-500 font-mono text-xs">



           Fetching trade ledger for user #${userId}...



        </div>



      `;



    }







    try {



      const resp = await fetch(`/api/admin/users/${userId}/trades`, {



        method: "GET",



        headers: getAdminAuthHeaders(),



      });



      const res = await resp.json();



      if (!resp.ok || !res.success) {



        throw new Error(res.detail || "Failed to load trades");



      }







      currentUserTrades = Array.isArray(res.trades) ? res.trades : [];



      currentTradesUserId = userId;







      // Update summary cards



      const summary = res.summary || {};



      const elTotal = document.getElementById("userTradesTotal");



      const elWinRate = document.getElementById("userTradesWinRate");



      const elNetPnl = document.getElementById("userTradesNetPnl");



      const elOpenCount = document.getElementById("userTradesOpenCount");







      if (elTotal) elTotal.innerText = summary.total_trades ?? currentUserTrades.length;



      if (elWinRate) elWinRate.innerText = `${summary.win_rate ?? 0}% (${summary.wins ?? 0}W / ${summary.losses ?? 0}L)`;



      if (elNetPnl) {



        const netPnl = summary.net_pnl ?? 0;



        elNetPnl.innerText = `${netPnl >= 0 ? "+$" : "-$"}${Math.abs(netPnl).toFixed(2)}`;



        elNetPnl.className = `text-base font-bold mt-0.5 ${netPnl >= 0 ? "text-emerald-400" : "text-rose-400"}`;



      }



      if (elOpenCount) elOpenCount.innerText = summary.open_trades ?? 0;







      renderUserTradesList();



    } catch (err) {



      console.error("[AdminUserPanel] Trade fetch error:", err);



      if (listEl) {



        listEl.innerHTML = `



          <div class="p-6 text-center text-rose-400 font-mono text-xs border border-rose-900/40 rounded-xl bg-rose-950/20">



            Failed to load trades: ${escapeHtml(err.message)}



          </div>



        `;



      }



    }



  }







  function setTradeFilterMode(mode) {



    currentTradeFilterMode = mode;



    document.querySelectorAll(".admin-tmode-pill").forEach((btn) => {



      if (btn.getAttribute("data-tmode") === mode) {



        btn.className = "admin-tmode-pill px-2 py-0.5 text-[10px] font-mono font-bold rounded-md bg-cyan-900/50 text-cyan-300 border border-cyan-500/30";



      } else {



        btn.className = "admin-tmode-pill px-2 py-0.5 text-[10px] font-mono font-bold rounded-md text-slate-400 hover:text-white";



      }



    });



    renderUserTradesList();



  }







  function setTradeFilterStatus(status) {



    currentTradeFilterStatus = status;



    document.querySelectorAll(".admin-tstatus-pill").forEach((btn) => {



      if (btn.getAttribute("data-tstatus") === status) {



        btn.className = "admin-tstatus-pill px-2 py-0.5 text-[10px] font-mono font-bold rounded-md bg-cyan-900/50 text-cyan-300 border border-cyan-500/30";



      } else {



        btn.className = "admin-tstatus-pill px-2 py-0.5 text-[10px] font-mono font-bold rounded-md text-slate-400 hover:text-white";



      }



    });



    renderUserTradesList();



  }







  function filterUserTradesList(query) {



    currentTradeSearch = (query || "").trim().toLowerCase();



    renderUserTradesList();



  }







  function renderUserTradesList() {



    const listEl = document.getElementById("adminUserTradesList");



    if (!listEl) return;







    if (!currentUserTrades || currentUserTrades.length === 0) {



      listEl.innerHTML = `



        <div class="p-8 text-center text-slate-500 font-mono text-xs border border-slate-800 rounded-xl bg-slate-900/30">



          No trades recorded for this user yet.



        </div>



      `;



      return;



    }







    const filtered = currentUserTrades.filter((t) => {



      // Mode filter



      const tMode = (t.mode || "PAPER").toUpperCase();



      if (currentTradeFilterMode !== "ALL" && tMode !== currentTradeFilterMode) {



        return false;



      }







      // Status / Win filter



      const status = (t.status || "CLOSED").toUpperCase();



      const pnl = parseFloat(t.pnl || 0);



      if (currentTradeFilterStatus === "CLOSED" && status === "OPEN") return false;



      if (currentTradeFilterStatus === "OPEN" && status !== "OPEN") return false;



      if (currentTradeFilterStatus === "WINS" && (status === "OPEN" || pnl <= 0)) return false;



      if (currentTradeFilterStatus === "LOSSES" && (status === "OPEN" || pnl >= 0)) return false;







      // Search query



      if (currentTradeSearch) {



        const targetStr = `${t.id || ""} ${t.ticker || ""} ${t.side || ""} ${t.direction || ""} ${t.trading_style || ""} ${t.signal_source || ""} ${t.reason || ""} ${t.exit_reason || ""} ${t.mode || ""}`.toLowerCase();



        if (!targetStr.includes(currentTradeSearch)) {



          return false;



        }



      }







      return true;



    });







    if (filtered.length === 0) {



      listEl.innerHTML = `



        <div class="p-8 text-center text-slate-500 font-mono text-xs border border-slate-800 rounded-xl bg-slate-900/30">



          No trades match the current filter criteria.



        </div>



      `;



      return;



    }







    listEl.innerHTML = filtered.reverse().map((t) => {



      const isClosed = (t.status || "CLOSED").toUpperCase() !== "OPEN";



      const pnl = parseFloat(t.pnl || 0);



      const isWin = isClosed && pnl > 0;



      const isLoss = isClosed && pnl < 0;



      const side = (t.side || t.direction || "YES").toUpperCase();



      const isYes = side === "YES";



      const mode = (t.mode || "PAPER").toUpperCase();



      const count = t.count || t.contracts || 1;



      const entryPrice = t.entry_price != null ? (t.entry_price * 100).toFixed(0) + "" : (t.price != null ? (t.price * 100).toFixed(0) + "" : "--");



      const exitPrice = t.exit_price != null ? (t.exit_price * 100).toFixed(0) + "" : null;



      const reason = t.reason || t.exit_reason || (isClosed ? "SETTLEMENT" : "ACTIVE");







      let formattedTime = "N/A";



      if (t.timestamp) {



        if (typeof t.timestamp === "number" || (!isNaN(t.timestamp) && !isNaN(parseFloat(t.timestamp)))) {



          try {



            const dt = new Date(parseFloat(t.timestamp) * (parseFloat(t.timestamp) < 10000000000 ? 1000 : 1));



            formattedTime = dt.toLocaleString();



          } catch (_) {



            formattedTime = String(t.timestamp);



          }



        } else {



          formattedTime = String(t.timestamp);



        }



      }







      let pnlBadge = "";



      if (isClosed) {



        pnlBadge = `<span class="text-xs font-mono font-black ${isWin ? "text-emerald-400" : isLoss ? "text-rose-400" : "text-slate-400"}">${pnl >= 0 ? "+$" : "-$"}${Math.abs(pnl).toFixed(2)}</span>`;



      } else {



        pnlBadge = `<span class="text-[10px] font-mono font-bold text-cyan-400 bg-cyan-950/80 px-2 py-0.5 rounded border border-cyan-500/40">OPEN</span>`;



      }







      const cardBorder = isClosed



        ? (isWin ? "border-emerald-500/30 hover:border-emerald-500/60" : isLoss ? "border-rose-500/30 hover:border-rose-500/60" : "border-slate-800 hover:border-slate-700")



        : "border-cyan-500/40 hover:border-cyan-500/70";







      // Style and Signal Badges



      const badges = [];



      const exitReasonStr = String(t.exit_reason || t.reason || "").toUpperCase();



      const isManual = t.is_manual === true || String(t.trading_style || "").toUpperCase() === "MANUAL" || String(t.signal_source || "").toUpperCase() === "MANUAL" || exitReasonStr === "MANUAL";







      // Style badge



      if (isManual) {



        badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-amber-500/20 text-amber-300 border border-amber-500/35"> MANUAL</span>');



      } else {



        const rawStyle = String(t.trading_style || "AUTO").toUpperCase();



        if (rawStyle.includes("MOMENTUM")) {



          badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-sky-500/20 text-sky-300 border border-sky-500/35">🏄 MOMENTUM</span>');



        } else if (rawStyle.includes("SNIPER")) {



          badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-emerald-500/20 text-emerald-300 border border-emerald-500/35">🎯 SNIPER</span>');



        } else if (rawStyle.includes("PREDICTION")) {



          badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-purple-500/20 text-purple-300 border border-purple-500/35">🔮 PREDICTION</span>');



        } else if (rawStyle.includes("AMBUSH")) {



          badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-amber-500/20 text-amber-300 border border-amber-500/35">🥷 AMBUSH</span>');



        } else if (rawStyle.includes("CHOP")) {



          badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-violet-500/20 text-violet-300 border border-violet-500/35">🪓 CHOP</span>');



        } else if (rawStyle.includes("GUARD") || rawStyle.includes("CAPITAL")) {



          badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-indigo-500/20 text-indigo-300 border border-indigo-500/35"> GUARD</span>');



        } else if (rawStyle.includes("FORCE")) {



          badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-rose-500/20 text-rose-300 border border-rose-500/35"> FORCE</span>');



        } else if (rawStyle.includes("SECOND") || rawStyle.includes("2ND")) {



          badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-teal-500/20 text-teal-300 border border-teal-500/35"> 2ND ENTRY</span>');



        } else {



          badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-blue-500/20 text-blue-300 border border-blue-500/35"> ' + escapeHtml(rawStyle.replace(/_/g, ' ')) + '</span>');



        }



      }







      // Signal Source badge



      if (!isManual) {



        const rawSource = String(t.signal_source || "").toUpperCase();



        if (rawSource.includes("BLEND")) {



          badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-fuchsia-500/20 text-fuchsia-300 border border-fuchsia-500/35">⚖️ BLEND</span>');



        } else if (rawSource.includes("DQN") || rawSource.includes("RL")) {



          badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-purple-500/20 text-purple-300 border border-purple-500/35"> RL DQN</span>');



        } else if (rawSource.includes("TECH")) {



          badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-orange-500/20 text-orange-300 border border-orange-500/35"> TECH</span>');



        } else if (rawSource.includes("SWARM") || rawSource.includes("ENSEMBLE")) {



          badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-indigo-500/20 text-indigo-300 border border-indigo-500/35"> SWARM</span>');



        } else if (rawSource && !rawSource.includes("REVERSAL")) {



          badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-slate-500/20 text-slate-300 border border-slate-500/35"> ' + escapeHtml(rawSource.replace(/_/g, ' ')) + '</span>');



        }



      }







      // Tactical badges



      if (t.is_profit_reentry || exitReasonStr.includes("SECOND_ENTRY")) {



        badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/35"> 2ND ENTRY</span>');



      }



      if (t.is_reversal || t.is_reverse || exitReasonStr.includes("REVERSAL")) {



        badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-pink-500/20 text-pink-300 border border-pink-500/35"> REVERSAL</span>');



      }







      return `



        <div class="p-3 bg-slate-900/70 border ${cardBorder} rounded-xl transition-all font-mono text-xs space-y-2">



          <div class="flex items-center justify-between gap-2">



            <div class="flex items-center gap-2 min-w-0">



              <span class="px-2 py-0.5 rounded text-[10px] font-black ${



                isYes ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40" : "bg-purple-500/20 text-purple-300 border border-purple-500/40"



              }">${escapeHtml(side)}</span>



              <span class="font-bold text-white truncate text-xs" title="${escapeHtml(t.ticker || "UNKNOWN")}">${escapeHtml(t.ticker || "UNKNOWN")}</span>



              <span class="text-[9px] px-1.5 py-0.2 rounded font-bold ${



                mode === "LIVE" ? "bg-amber-500/20 text-amber-300 border border-amber-500/30" : "bg-slate-800 text-slate-300"



              }">${escapeHtml(mode)}</span>



            </div>



            <div class="shrink-0 text-right">



              ${pnlBadge}



            </div>



          </div>







          <div class="flex flex-wrap gap-1">



            ${Array.from(new Map(badges.map(b => [b.replace(/<[^>]*>/g, '').trim().toUpperCase(), b])).values()).join("")}



          </div>







          <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 border-t border-slate-800/80 text-[10px] text-slate-400">



            <div>



              <span class="text-slate-500 text-[8px] uppercase block">Contracts</span>



              <span class="text-slate-200 font-bold">${escapeHtml(count)}x</span>



            </div>



            <div>



              <span class="text-slate-500 text-[8px] uppercase block">Entry / Exit</span>



              <span class="text-slate-200 font-bold">${escapeHtml(entryPrice)}${exitPrice ? `  ${escapeHtml(exitPrice)}` : ""}</span>



            </div>



            <div>



              <span class="text-slate-500 text-[8px] uppercase block">Outcome / Reason</span>



              <span class="text-slate-200 font-bold truncate block" title="${escapeHtml(reason)}">${escapeHtml(reason)}</span>



            </div>



            <div class="text-right sm:text-right">



              <span class="text-slate-500 text-[8px] uppercase block">Timestamp</span>



              <span class="text-slate-300 text-[9px] truncate block" title="${escapeHtml(formattedTime)}">${escapeHtml(formattedTime)}</span>



            </div>



          </div>



        </div>



      `;



    }).join("");



  }







  // Ensure both columns show on desktop on resize



  window.addEventListener("resize", () => {



    if (window.innerWidth >= 1024) {



      const listEl = document.getElementById("adminUserListContainer");



      const detailEl = document.getElementById("adminUserDetailPanel");



      if (listEl) listEl.classList.remove("hidden");



      if (detailEl) detailEl.classList.remove("hidden");



    }



  });







  // ==========================================
  // SUPPORT TICKETS MODULE
  // ==========================================

  function switchAdminSection(section) {
    adminCurrentSection = section;
    const btnUsers = document.getElementById("adminNavBtnUsers");
    const btnTickets = document.getElementById("adminNavBtnTickets");
    const secUsers = document.getElementById("adminSectionUsers");
    const secTickets = document.getElementById("adminSectionTickets");

    if (section === "tickets") {
      if (btnUsers) {
        btnUsers.className = "px-3 py-1 font-bold rounded-lg transition-all text-slate-400 hover:text-white flex items-center gap-1.5 cursor-pointer";
      }
      if (btnTickets) {
        btnTickets.className = "px-3 py-1 font-bold rounded-lg transition-all bg-indigo-600 text-white shadow-sm flex items-center gap-1.5 cursor-pointer";
      }
      if (secUsers) secUsers.classList.add("hidden");
      if (secTickets) secTickets.classList.remove("hidden");
      fetchAdminTickets();
    } else {
      if (btnUsers) {
        btnUsers.className = "px-3 py-1 font-bold rounded-lg transition-all bg-indigo-600 text-white shadow-sm flex items-center gap-1.5 cursor-pointer";
      }
      if (btnTickets) {
        btnTickets.className = "px-3 py-1 font-bold rounded-lg transition-all text-slate-400 hover:text-white flex items-center gap-1.5 cursor-pointer";
      }
      if (secUsers) secUsers.classList.remove("hidden");
      if (secTickets) secTickets.classList.add("hidden");
    }
  }

  async function fetchAdminTickets(isBackground = false) {
    try {
      const resp = await fetch("/api/admin/tickets", {
        cache: "no-store",
        headers: getAdminAuthHeaders(),
      });
      if (!resp.ok) {
        throw new Error(`Server returned HTTP ${resp.status}`);
      }
      const data = await resp.json();
      if (data && Array.isArray(data.tickets)) {
        adminTicketsList = data.tickets;
        updateTicketBadgesAndStats();
        renderTicketsList();
        if (selectedTicketId !== null) {
          const currentTicket = adminTicketsList.find(t => t.id === selectedTicketId);
          if (currentTicket) {
            renderTicketDetail(currentTicket);
          }
        }
      }
    } catch (err) {
      if (!isBackground) {
        console.error("Failed to fetch tickets:", err);
        showAdminToast(`Failed to load tickets: ${err.message}`, "error");
      }
    }
  }

  function updateTicketBadgesAndStats() {
    const total = adminTicketsList.length;
    const open = adminTicketsList.filter(t => t.status === "OPEN").length;
    const resolved = adminTicketsList.filter(t => t.status === "RESOLVED").length;
    const aiAnalyzed = adminTicketsList.filter(t => Boolean(t.bot_recommendation)).length;

    // Header badge
    const headerTicketCount = document.getElementById("headerTicketCount");
    const headerTicketBadge = document.getElementById("headerTicketBadge");
    if (headerTicketCount) headerTicketCount.textContent = open;
    if (headerTicketBadge) {
      if (open > 0) {
        headerTicketBadge.classList.remove("hidden");
      } else {
        headerTicketBadge.classList.add("hidden");
      }
    }

    // Stats row
    const totalEl = document.getElementById("adminTotalTicketsCount");
    const openEl = document.getElementById("adminOpenTicketsCount");
    const resolvedEl = document.getElementById("adminResolvedTicketsCount");
    const aiEl = document.getElementById("adminAiAnalyzedCount");

    if (totalEl) totalEl.textContent = total;
    if (openEl) openEl.textContent = open;
    if (resolvedEl) resolvedEl.textContent = resolved;
    if (aiEl) aiEl.textContent = aiAnalyzed;
  }

  function setTicketFilterStatus(status) {
    currentTicketFilterStatus = status;
    const btnAll = document.getElementById("ticketFilterBtnAll");
    const btnOpen = document.getElementById("ticketFilterBtnOpen");
    const btnResolved = document.getElementById("ticketFilterBtnResolved");

    const activeClass = "flex-1 py-1 text-center font-bold rounded bg-indigo-600 text-white shadow-sm transition-all cursor-pointer";
    const inactiveClass = "flex-1 py-1 text-center font-bold rounded text-slate-400 hover:text-white transition-all cursor-pointer";

    if (btnAll) btnAll.className = status === "ALL" ? activeClass : inactiveClass;
    if (btnOpen) btnOpen.className = status === "OPEN" ? activeClass : inactiveClass;
    if (btnResolved) btnResolved.className = status === "RESOLVED" ? activeClass : inactiveClass;

    renderTicketsList();
  }

  function setTicketSearch(query) {
    currentTicketSearch = (query || "").trim().toLowerCase();
    renderTicketsList();
  }

  function renderTicketsList() {
    const listContainer = document.getElementById("adminTicketListContainer");
    if (!listContainer) return;

    let filtered = adminTicketsList.filter(t => {
      if (currentTicketFilterStatus !== "ALL" && t.status !== currentTicketFilterStatus) {
        return false;
      }
      if (currentTicketSearch) {
        const username = (t.username || "").toLowerCase();
        const issue = (t.issue_text || "").toLowerCase();
        const idStr = String(t.id);
        if (!username.includes(currentTicketSearch) && !issue.includes(currentTicketSearch) && !idStr.includes(currentTicketSearch)) {
          return false;
        }
      }
      return true;
    });

    if (filtered.length === 0) {
      listContainer.innerHTML = `
        <div class="p-8 text-center text-slate-500 font-mono text-xs">
          No tickets found matching criteria.
        </div>
      `;
      return;
    }

    listContainer.innerHTML = filtered.map(t => {
      const isSelected = t.id === selectedTicketId;
      const isOpen = t.status === "OPEN";
      const hasAi = Boolean(t.bot_recommendation);
      const dateStr = t.created_at ? new Date(t.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : "";

      return `
        <div onclick="window.selectAdminTicket(${t.id})" 
             class="p-3 rounded-xl border transition-all cursor-pointer ${
               isSelected
                 ? "bg-indigo-950/40 border-indigo-500/80 shadow-[0_0_15px_rgba(99,102,241,0.25)]"
                 : "bg-slate-900/80 hover:bg-slate-800/80 border-slate-800"
             }">
          <div class="flex items-center justify-between gap-2 mb-1.5">
            <div class="flex items-center gap-1.5">
              <span class="font-mono font-bold text-xs ${isSelected ? "text-indigo-300" : "text-slate-300"}">#${t.id}</span>
              <span class="text-xs font-semibold text-white truncate max-w-[120px]">@${escapeHtml(t.username || "User " + t.user_id)}</span>
            </div>
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold font-mono tracking-wide ${
              isOpen
                ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
            }">
              ${isOpen ? "OPEN" : "RESOLVED"}
            </span>
          </div>

          <p class="text-xs text-slate-400 line-clamp-2 leading-relaxed mb-2 font-sans">
            ${escapeHtml(t.issue_text || "No issue description provided.")}
          </p>

          <div class="flex items-center justify-between text-[10px] font-mono text-slate-500 pt-1 border-t border-slate-800/60">
            <span>${dateStr}</span>
            ${hasAi ? `
              <span class="flex items-center gap-1 text-cyan-400 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-800/50">
                <span>🤖</span> AI Diagnosed
              </span>
            ` : `
              <span class="text-slate-600">Pending AI</span>
            `}
          </div>
        </div>
      `;
    }).join("");
  }

  function selectAdminTicket(ticketId) {
    selectedTicketId = ticketId;
    const ticket = adminTicketsList.find(t => t.id === ticketId);

    // Responsive toggle for smaller screens
    const listTab = document.getElementById("adminTabTicketList");
    const detailTab = document.getElementById("adminTabTicketDetail");
    if (window.innerWidth < 1024) {
      if (listTab) listTab.classList.add("hidden");
      if (detailTab) {
        detailTab.classList.remove("hidden");
        detailTab.classList.add("flex");
      }
    }

    renderTicketsList();
    if (ticket) {
      renderTicketDetail(ticket);
    }
  }

  function backToTicketList() {
    const listTab = document.getElementById("adminTabTicketList");
    const detailTab = document.getElementById("adminTabTicketDetail");
    if (listTab) listTab.classList.remove("hidden");
    if (detailTab) {
      detailTab.classList.add("hidden");
      detailTab.classList.remove("flex");
    }
  }

  function renderSimpleMarkdown(md) {
    if (!md) return "";
    let html = escapeHtml(md);

    // Code blocks with triple backticks
    html = html.replace(/```(?:[a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, function(match, code) {
      return '<pre class="bg-black/80 p-3 rounded-xl border border-slate-800 text-[11px] font-mono text-cyan-200 overflow-x-auto my-3 select-text shadow-inner"><code>' + code + '</code></pre>';
    });

    // Inline code with single backticks
    html = html.replace(/`([^`]+)`/g, '<code class="bg-slate-800 px-1.5 py-0.5 rounded text-[11px] font-mono text-cyan-300 font-semibold border border-slate-700/60">$1</code>');

    // Headings
    html = html.replace(/^### (.*$)/gim, '<h3 class="text-sm font-bold text-cyan-300 mt-3 mb-1.5 border-b border-cyan-900/40 pb-1 flex items-center gap-1.5"><span class="text-xs">⚡</span> $1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 class="text-base font-bold text-white mt-4 mb-2 pb-1 border-b border-slate-800">$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1 class="text-lg font-black text-white mt-4 mb-2">$1</h1>');

    // Horizontal rule ---
    html = html.replace(/^---$/gim, '<hr class="border-slate-800 my-3">');

    // Bold **text**
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong class="text-white font-bold">$1</strong>');
    
    // Italic *text*
    html = html.replace(/\*(.*?)\*/g, '<em class="text-slate-300">$1</em>');

    // Bullet items
    html = html.replace(/^[\*\-] (.*$)/gim, '<div class="flex items-start gap-2 my-1 ml-2"><span class="text-cyan-400 text-xs leading-5">•</span><span class="text-slate-200 text-xs leading-5">$1</span></div>');

    // Numbered lists 1. 2. etc
    html = html.replace(/^(\d+)\. (.*$)/gim, '<div class="flex items-start gap-2 my-1 ml-2"><span class="text-indigo-400 font-mono text-xs font-bold leading-5">$1.</span><span class="text-slate-200 text-xs leading-5">$2</span></div>');

    // Double newline to paragraph spacing
    html = html.replace(/\n\n+/g, '<div class="h-2"></div>');

    // Single newline to br
    html = html.replace(/\n/g, '<br>');

    return html;
  }

  function renderTicketDetail(ticket) {
    const panel = document.getElementById("adminTicketDetailPanel");
    if (!panel) return;

    const isOpen = ticket.status === "OPEN";
    const dateFormatted = ticket.created_at ? new Date(ticket.created_at).toLocaleString() : "Unknown";
    const hasAi = Boolean(ticket.bot_recommendation);

    panel.innerHTML = `
      <div class="space-y-4 max-w-4xl mx-auto">
        <!-- Top Action / Title Bar -->
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 bg-slate-950/80 rounded-2xl border border-slate-800 shadow-md">
          <div class="flex items-center gap-3">
            <button onclick="window.backToTicketList()" class="lg:hidden px-2.5 py-1 text-xs bg-slate-800 text-slate-300 hover:text-white rounded-lg border border-slate-700 font-bold transition-all cursor-pointer">
              ← Back
            </button>
            <div>
              <div class="flex items-center gap-2">
                <span class="font-mono text-base font-black text-indigo-400">Ticket #${ticket.id}</span>
                <span class="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold ${
                  isOpen
                    ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                    : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                }">
                  ${isOpen ? "● OPEN" : "✓ RESOLVED"}
                </span>
              </div>
              <div class="text-xs text-slate-400 mt-0.5">
                Submitted by <strong class="text-slate-200">@${escapeHtml(ticket.username || "User " + ticket.user_id)}</strong> 
                <span class="text-slate-600">•</span> ${dateFormatted}
              </div>
            </div>
          </div>

          <!-- Action Buttons -->
          <div class="flex items-center gap-2">
            <button id="btnAiAnalyze" onclick="window.runAiDevBot(${ticket.id})" 
                    ${isAnalyzingTicket ? "disabled" : ""}
                    class="px-3.5 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shadow-sm cursor-pointer ${
                      isAnalyzingTicket
                        ? "bg-cyan-900/50 text-cyan-300 border border-cyan-800 cursor-not-allowed opacity-75"
                        : "bg-cyan-600 hover:bg-cyan-500 text-white shadow-cyan-900/30"
                    }">
              ${isAnalyzingTicket ? `
                <svg class="animate-spin w-4 h-4 text-white" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg>
                Analyzing...
              ` : `
                <span>🤖</span> ${hasAi ? "Re-Run AI Dev Bot" : "Run AI Dev Bot"}
              `}
            </button>

            ${isOpen ? `
              <button onclick="window.approveTicket(${ticket.id})" 
                      class="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shadow-sm shadow-emerald-900/30 cursor-pointer">
                <span>✅</span> Approve & Resolve
              </button>
            ` : `
              <button onclick="window.reopenTicket(${ticket.id})" 
                      class="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-amber-300 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 border border-slate-700 cursor-pointer">
                <span>↺</span> Re-open
              </button>
            `}

            <button onclick="window.deleteTicketPrompt(${ticket.id})" 
                    class="p-2 text-slate-500 hover:text-rose-400 hover:bg-slate-800/80 rounded-xl transition-all cursor-pointer" title="Delete Ticket">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
            </button>
          </div>
        </div>

        <!-- Issue Text Box -->
        <div class="bg-slate-950/60 p-4 rounded-2xl border border-slate-800 space-y-2">
          <div class="flex items-center justify-between text-xs font-bold text-slate-400 uppercase tracking-wider">
            <span class="flex items-center gap-1.5">
              <span>📝</span> User Reported Issue
            </span>
            <span class="text-[10px] font-mono text-slate-600">User ID: ${ticket.user_id}</span>
          </div>
          <div class="p-3 bg-slate-900/90 rounded-xl border border-slate-800/80 text-sm text-slate-200 leading-relaxed font-sans select-text">
            ${escapeHtml(ticket.issue_text || "No description provided.")}
          </div>
        </div>

        <!-- AI Dev Bot Recommendation Panel -->
        <div class="bg-slate-950/60 p-4 rounded-2xl border border-slate-800 space-y-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-lg">🤖</span>
              <div>
                <h3 class="text-xs font-bold uppercase tracking-wider text-cyan-400">AI Dev Bot Analysis</h3>
                <span class="text-[10px] text-slate-500 font-mono">Engine: Gemini 3.8 Flash Architecture</span>
              </div>
            </div>
            ${hasAi ? `
              <span class="px-2 py-0.5 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800 text-[10px] font-mono">
                Analysis Ready
              </span>
            ` : ""}
          </div>

          ${hasAi ? `
            <div class="p-4 bg-slate-900/95 rounded-xl border border-cyan-500/20 text-xs leading-relaxed text-slate-200 select-text font-sans shadow-inner">
              ${renderSimpleMarkdown(ticket.bot_recommendation)}
            </div>
            ${isOpen ? `
              <div class="flex justify-end pt-2">
                <button onclick="window.approveTicket(${ticket.id})" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition-all flex items-center gap-2 cursor-pointer shadow-md">
                  <span>✅</span> Approve Proposed Fix & Mark Ticket Resolved
                </button>
              </div>
            ` : ""}
          ` : `
            <div class="p-6 text-center bg-slate-900/40 rounded-xl border border-dashed border-slate-800 space-y-2">
              <div class="text-2xl">⚡</div>
              <div class="text-xs font-bold text-slate-300">No Automated Diagnostic Yet</div>
              <p class="text-xs text-slate-500 max-w-md mx-auto">
                Click "Run AI Dev Bot" above to perform real-time triage using Gemini. The bot will inspect the report, identify the underlying root cause in the trading engine or UI, and provide actionable technical steps.
              </p>
            </div>
          `}
        </div>
      </div>
    `;
  }

  async function runAiDevBot(ticketId) {
    if (isAnalyzingTicket) return;
    isAnalyzingTicket = true;
    const ticket = adminTicketsList.find(t => t.id === ticketId);
    if (ticket) renderTicketDetail(ticket);

    try {
      showAdminToast("Contacting Gemini AI Dev Bot...", "info");
      const resp = await fetch(`/api/admin/tickets/${ticketId}/analyze`, {
        method: "POST",
        headers: getAdminAuthHeaders(),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${resp.status}`);
      }

      const data = await resp.json();
      if (data && data.bot_recommendation) {
        if (ticket) {
          ticket.bot_recommendation = data.bot_recommendation;
        }
        updateTicketBadgesAndStats();
        renderTicketsList();
        if (ticket) renderTicketDetail(ticket);
        showAdminToast("AI Dev Bot analysis completed successfully!", "success");
      }
    } catch (err) {
      console.error("AI Dev Bot failed:", err);
      showAdminToast(`AI Dev Bot failed: ${err.message}`, "error");
    } finally {
      isAnalyzingTicket = false;
      const t = adminTicketsList.find(x => x.id === ticketId);
      if (t) renderTicketDetail(t);
    }
  }

  async function approveTicket(ticketId) {
    try {
      const resp = await fetch(`/api/admin/tickets/${ticketId}/approve`, {
        method: "POST",
        headers: getAdminAuthHeaders(),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${resp.status}`);
      }

      const ticket = adminTicketsList.find(t => t.id === ticketId);
      if (ticket) {
        ticket.status = "RESOLVED";
      }
      updateTicketBadgesAndStats();
      renderTicketsList();
      if (ticket) renderTicketDetail(ticket);
      showAdminToast(`Ticket #${ticketId} marked as RESOLVED!`, "success");
    } catch (err) {
      console.error("Approve ticket failed:", err);
      showAdminToast(`Failed to approve ticket: ${err.message}`, "error");
    }
  }

  async function reopenTicket(ticketId) {
    try {
      const resp = await fetch(`/api/admin/tickets/${ticketId}/reopen`, {
        method: "POST",
        headers: getAdminAuthHeaders(),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${resp.status}`);
      }

      const ticket = adminTicketsList.find(t => t.id === ticketId);
      if (ticket) {
        ticket.status = "OPEN";
      }
      updateTicketBadgesAndStats();
      renderTicketsList();
      if (ticket) renderTicketDetail(ticket);
      showAdminToast(`Ticket #${ticketId} re-opened!`, "info");
    } catch (err) {
      console.error("Reopen ticket failed:", err);
      showAdminToast(`Failed to re-open ticket: ${err.message}`, "error");
    }
  }

  async function deleteTicketPrompt(ticketId) {
    if (!confirm(`Are you sure you want to permanently delete Support Ticket #${ticketId}?`)) return;
    try {
      const resp = await fetch(`/api/admin/tickets/${ticketId}`, {
        method: "DELETE",
        headers: getAdminAuthHeaders(),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${resp.status}`);
      }

      adminTicketsList = adminTicketsList.filter(t => t.id !== ticketId);
      if (selectedTicketId === ticketId) {
        selectedTicketId = null;
        const panel = document.getElementById("adminTicketDetailPanel");
        if (panel) {
          panel.innerHTML = `
            <div class="flex h-full items-center justify-center text-slate-500 font-mono text-sm">
              Select a ticket to review issue and AI bot diagnosis
            </div>
          `;
        }
      }
      updateTicketBadgesAndStats();
      renderTicketsList();
      showAdminToast(`Ticket #${ticketId} deleted.`, "info");
    } catch (err) {
      console.error("Delete ticket failed:", err);
      showAdminToast(`Failed to delete ticket: ${err.message}`, "error");
    }
  }

  // Expose global methods for UI interaction
  window.openAdminUserPanel = openAdminUserPanel;
  window.closeAdminUserPanel = closeAdminUserPanel;
  window.fetchAdminUsers = fetchAdminUsers;
  window.selectUserToEdit = selectUserToEdit;
  window.saveSelectedUserConfig = saveSelectedUserConfig;
  window.quickToggleAi = quickToggleAi;
  window.quickResetBalance = quickResetBalance;

  window.toggleMasterEngine = async function() {
    const btn = document.getElementById('masterEngineToggleBtn');
    try {
        const r = await fetch('/api/admin/broadcast/toggle', {
            method: 'POST',
            headers: getAdminAuthHeaders(),
            body: JSON.stringify({enabled: false})
        });
        if (r.ok) {
            btn.innerText = 'TRADING KILLED';
            btn.className = 'px-4 py-1.5 rounded-lg text-xs font-bold bg-slate-800 text-slate-500 border border-slate-700';
            btn.disabled = true;
            showAdminToast('Master Engine Trading Disabled', 'success');
        } else {
            showAdminToast('Failed to kill trading', 'error');
        }
    } catch(e) {
        showAdminToast('Error killing trading', 'error');
    }
  };
  window.confirmDeleteUser = confirmDeleteUser;
  window.setFilterSearch = setFilterSearch;
  window.setFilterMode = setFilterMode;
  window.setFilterAi = setFilterAi;
  window.switchAdminMobileTab = switchAdminMobileTab;
  window.switchUserDetailTab = switchUserDetailTab;
  window.loadUserTrades = loadUserTrades;
  window.setTradeFilterMode = setTradeFilterMode;
  window.setTradeFilterStatus = setTradeFilterStatus;
  window.filterUserTradesList = filterUserTradesList;

  // Support Tickets Window Exports
  window.switchAdminSection = switchAdminSection;
  window.fetchAdminTickets = fetchAdminTickets;
  window.setTicketFilterStatus = setTicketFilterStatus;
  window.setTicketSearch = setTicketSearch;
  window.selectAdminTicket = selectAdminTicket;
  window.backToTicketList = backToTicketList;
  window.runAiDevBot = runAiDevBot;
  window.approveTicket = approveTicket;
  window.reopenTicket = reopenTicket;
  window.deleteTicketPrompt = deleteTicketPrompt;

  // Initial fetch on DOM ready
  document.addEventListener("DOMContentLoaded", () => {
    fetchAdminUsers(false);
    fetchAdminTickets(true);

    if(window.adminUsersInterval) clearInterval(window.adminUsersInterval); window.adminUsersInterval = setInterval(async () => {
      // Skip if already polling or if the admin modal is not visible
      if (isPolling) return;
      const modal = document.getElementById("adminUserModal");
      if (modal && modal.classList.contains("hidden")) return;
      isPolling = true;
      try { 
        await fetchAdminUsers(true); 
        if (adminCurrentSection === "tickets") {
          await fetchAdminTickets(true);
        }
      } finally { isPolling = false; }
    }, 3000);
  });




})();



















