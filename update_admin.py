import re

with open('static/admin_mobile.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add toggles
toggles_html = """
                    <!-- Missing Toggles -->
                    <div class="flex items-center justify-between p-3 border-t border-slate-800">
                        <div>
                            <div class="text-xs font-bold text-white">Dynamic ATR Risk</div>
                            <div class="text-[10px] text-slate-400">Auto-adjust TP/SL by volatility</div>
                        </div>
                        <label class="ios-switch">
                            <input type="checkbox" id="ed_atr_risk_enabled">
                            <span class="ios-slider"></span>
                        </label>
                    </div>
                    <div class="flex items-center justify-between p-3 border-t border-slate-800">
                        <div>
                            <div class="text-xs font-bold text-white">One-Click Trading</div>
                            <div class="text-[10px] text-slate-400">Skip confirm prompts</div>
                        </div>
                        <label class="ios-switch">
                            <input type="checkbox" id="ed_one_click_trade">
                            <span class="ios-slider"></span>
                        </label>
                    </div>
                    <div class="flex items-center justify-between p-3 border-t border-slate-800">
                        <div>
                            <div class="text-xs font-bold text-white">Re-entry after Stop Loss</div>
                            <div class="text-[10px] text-slate-400">Allow a 2nd try if stopped out</div>
                        </div>
                        <label class="ios-switch">
                            <input type="checkbox" id="ed_reentry_after_stop_loss">
                            <span class="ios-slider"></span>
                        </label>
                    </div>
                    <div class="flex items-center justify-between p-3 border-t border-slate-800">
                        <div>
                            <div class="text-xs font-bold text-white">One-Shot AI</div>
                            <div class="text-[10px] text-slate-400">Halt after 1st trade of interval</div>
                        </div>
                        <label class="ios-switch">
                            <input type="checkbox" id="ed_one_shot_ai">
                            <span class="ios-slider"></span>
                        </label>
                    </div>
"""
html = html.replace('<!-- Kelly Criterion Sizing -->', toggles_html + '\n                    <!-- Kelly Criterion Sizing -->')

# 2. Add input fields
inputs_html = """
                    <!-- Missing Inputs -->
                    <div>
                        <label class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Target Asset</label>
                        <input type="text" id="ed_target_asset" placeholder="e.g. BTC,ETH,SOL" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Model Choice</label>
                        <select id="ed_model_choice" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-indigo-500">
                            <option value="XGBOOST">XGBOOST</option>
                            <option value="RANDOM_FOREST">RANDOM_FOREST</option>
                            <option value="LOGISTIC_REGRESSION">LOGISTIC_REGRESSION</option>
                            <option value="RL_AGENT">RL_AGENT</option>
                        </select>
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Max Daily Trades</label>
                            <input type="number" id="ed_max_daily_trades" step="1" min="1" max="500" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-indigo-500">
                        </div>
                        <div>
                            <label class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Min Edge Cents</label>
                            <input type="number" id="ed_min_edge_cents" step="0.5" min="0" max="25" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-indigo-500">
                        </div>
                        <div>
                            <label class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Trail Act. Pct</label>
                            <input type="number" id="ed_trailing_stop_activation_pct" step="5" min="5" max="500" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-indigo-500">
                        </div>
                        <div>
                            <label class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Trail Dist. Pct</label>
                            <input type="number" id="ed_trailing_stop_distance_pct" step="5" min="5" max="100" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-indigo-500">
                        </div>
                        <div>
                            <label class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">2nd Entry Ask (0-1)</label>
                            <input type="number" id="ed_second_entry_max_ask" step="0.01" min="0" max="1" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-indigo-500">
                        </div>
                    </div>
"""
html = html.replace('<!-- Section: Trading Strategy & Styles -->', '<!-- Section: Trading Strategy & Styles -->\n              <div class="space-y-2 mt-4"><div class="bg-slate-900 border border-slate-800 rounded-xl p-3.5 space-y-3">' + inputs_html + '</div></div>')

# 3. Add to populate logic
populate_html = """
            document.getElementById('ed_atr_risk_enabled').checked = !!user.atr_risk_enabled;
            document.getElementById('ed_one_click_trade').checked = !!user.one_click_trade;
            document.getElementById('ed_reentry_after_stop_loss').checked = !!user.reentry_after_stop_loss;
            document.getElementById('ed_one_shot_ai').checked = !!user.one_shot_ai;
            document.getElementById('ed_target_asset').value = user.target_asset || '';
            document.getElementById('ed_model_choice').value = user.model_choice || 'XGBOOST';
            document.getElementById('ed_max_daily_trades').value = user.max_daily_trades || 50;
            document.getElementById('ed_min_edge_cents').value = user.min_edge_cents || 4.0;
            document.getElementById('ed_trailing_stop_activation_pct').value = user.trailing_stop_activation_pct || 25;
            document.getElementById('ed_trailing_stop_distance_pct').value = user.trailing_stop_distance_pct || 15;
            document.getElementById('ed_second_entry_max_ask').value = user.second_entry_max_ask || 0.65;
"""
html = html.replace("document.getElementById('ed_use_kelly_criterion').checked = !!user.use_kelly_criterion;", 
"document.getElementById('ed_use_kelly_criterion').checked = !!user.use_kelly_criterion;\n" + populate_html)

# 4. Add to payload logic
payload_html = """
                atr_risk_enabled: document.getElementById('ed_atr_risk_enabled').checked,
                one_click_trade: document.getElementById('ed_one_click_trade').checked,
                reentry_after_stop_loss: document.getElementById('ed_reentry_after_stop_loss').checked,
                one_shot_ai: document.getElementById('ed_one_shot_ai').checked,
                target_asset: document.getElementById('ed_target_asset').value || null,
                model_choice: document.getElementById('ed_model_choice').value || null,
                max_daily_trades: parseInt(document.getElementById('ed_max_daily_trades').value) || null,
                min_edge_cents: parseFloat(document.getElementById('ed_min_edge_cents').value) || null,
                trailing_stop_activation_pct: parseFloat(document.getElementById('ed_trailing_stop_activation_pct').value) || null,
                trailing_stop_distance_pct: parseFloat(document.getElementById('ed_trailing_stop_distance_pct').value) || null,
                second_entry_max_ask: parseFloat(document.getElementById('ed_second_entry_max_ask').value) || null,
"""
html = html.replace("use_kelly_criterion: document.getElementById('ed_use_kelly_criterion').checked,", 
"use_kelly_criterion: document.getElementById('ed_use_kelly_criterion').checked,\n" + payload_html)

with open('static/admin_mobile.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated static/admin_mobile.html")
