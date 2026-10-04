import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# I will extract the updateActivePositionHud function and replace it.
pattern = re.compile(r'function updateActivePositionHud\(s\)\s*\{.*?\n        \}\n', re.DOTALL)
match = pattern.search(html)

if match:
    old_func = match.group(0)
    
    # I will create a new function
    new_func = '''function updateActivePositionHud(s) {
            const container = document.getElementById('activePositionHud');
            if (!container) return;

            let openTrades = (s.recent_trades || []).filter(t => String(t.status || '').toUpperCase() === 'OPEN');
            
            // Filter by universe
            const sportsAssetsList = ['NFL', 'MLB', 'NHL', 'NBA', 'SOCCER', 'UFC', 'TENNIS'];
            openTrades = openTrades.filter(t => {
                const asset = String(t.asset || '').toUpperCase();
                const isSport = sportsAssetsList.includes(asset);
                return (window.currentUniverse === 'SPORTS') ? isSport : !isSport;
            });
            
            // Audio trigger on newly opened trade
            if (openTrades.length > previousOpenTradeCount && previousOpenTradeCount === 0) {
                soundEngine.play('order_fill');
            }
            previousOpenTradeCount = openTrades.length;

            if (openTrades.length === 0) {
                const statusText = window.currentUniverse === 'SPORTS' ? 'SPORTS (NFL, MLB, ETC)' : '10 ASSETS (BTC, ETH, GOLD, ETC)';
                container.innerHTML = 
                    <div class="bg-[#0e1626]/95 border-t border-cyan-500/20 px-4 py-3 shadow-md flex items-center justify-between">
                        <div class="flex items-center gap-2.5">
                            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                            <span class="text-[10px] font-bold uppercase tracking-wider text-gray-400">Position Scanner:</span>
                            <span class="text-[10px] font-mono text-emerald-400 font-bold">READY · Bot Scanning Active</span>
                        </div>
                        <span class="text-[9px] font-mono text-gray-400 uppercase tracking-widest"> · </span>
                    </div>
                ;
                return;
            }

            const assetOrder = { 'BTC': 1, 'ETH': 2, 'GOLD': 3, 'EURUSD': 4, 'GBPUSD': 5, 'USDJPY': 6, 'AUDUSD': 7, 'NDQ': 8, 'SOL': 9, 'DOGE': 10 };
            const sortedOpen = [...openTrades].sort((a, b) => {
                const aAsset = String(a.asset || 'OTHER').toUpperCase();
                const bAsset = String(b.asset || 'OTHER').toUpperCase();
                return (assetOrder[aAsset] || 99) - (assetOrder[bAsset] || 99);
            });

            let totalOpenPnl = 0;
            let rowsHtml = '';

            sortedOpen.forEach(t => {
                let asset = String(t.asset || '').toUpperCase();
                if (!asset || asset === 'NONE') {
                    const tk = String(t.ticker || '').toUpperCase();
                    if (tk.includes('BTC')) asset = 'BTC';
                    else if (tk.includes('ETH')) asset = 'ETH';
                    else if (tk.includes('GOLD')) asset = 'GOLD';
                    else if (tk.includes('EURUSD')) asset = 'EURUSD';
                    else if (tk.includes('GBPUSD')) asset = 'GBPUSD';
                    else if (tk.includes('USDJPY')) asset = 'USDJPY';
                    else if (tk.includes('AUDUSD')) asset = 'AUDUSD';
                    else if (tk.includes('NDQ')) asset = 'NDQ';
                    else if (tk.includes('SOL')) asset = 'SOL';
                    else if (tk.includes('DOGE')) asset = 'DOGE';
                    else asset = 'UNKNOWN';
                }

                const isSport = sportsAssetsList.includes(asset);
                const side = String(t.side || 'YES').toUpperCase();
                const sideClass = side === 'YES' ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' : 'text-rose-400 bg-rose-500/10 border-rose-500/20';
                
                let pnlVal = 0;
                let curPrice = null;
                if (asset === window.currentAsset) {
                    curPrice = (side === 'YES') ? window.lastYesBid : window.lastNoBid;
                }
                
                let pnlClass = 'text-gray-300';
                let pnlStr = '---';
                if (curPrice !== null && t.entry_price) {
                    pnlVal = (curPrice - (t.entry_price * 100)) * (t.contracts || 0);
                    if (pnlVal > 0) { pnlClass = 'text-emerald-400'; pnlStr = '+$' + pnlVal.toFixed(2); }
                    else if (pnlVal < 0) { pnlClass = 'text-rose-400'; pnlStr = '-$' + Math.abs(pnlVal).toFixed(2); }
                    else { pnlStr = '.00'; }
                    totalOpenPnl += pnlVal;
                }

                let assetBadgeClass = 'bg-orange-500/20 text-orange-400 border-orange-500/40';
                if (asset === 'ETH') assetBadgeClass = 'bg-blue-500/20 text-blue-400 border-blue-500/40';
                if (asset === 'GOLD') assetBadgeClass = 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40';
                if (['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'].includes(asset)) assetBadgeClass = 'bg-green-500/20 text-green-400 border-green-500/40';
                if (asset === 'NDQ') assetBadgeClass = 'bg-purple-500/20 text-purple-400 border-purple-500/40';
                if (isSport) assetBadgeClass = 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40';

                let entryCost = ((t.entry_price || 0) * 100 * (t.contracts || 0)).toFixed(2);
                let leverage = t.leverage || '1';
                
                let infoHtml = '';
                if (isSport) {
                    infoHtml = 
                        <div class="hidden sm:flex flex-col">
                            <span class="text-[9px] text-gray-500 uppercase">Matchup</span>
                            <span class="text-xs font-mono font-bold text-gray-200"></span>
                        </div>
                        <div class="hidden md:flex flex-col">
                            <span class="text-[9px] text-gray-500 uppercase">Wager</span>
                            <span class="text-xs font-mono font-bold text-gray-200">{entryCost}</span>
                        </div>
                    ;
                } else {
                    infoHtml = 
                        <div class="hidden sm:flex flex-col">
                            <span class="text-[9px] text-gray-500 uppercase">Mark Price</span>
                            <span class="text-xs font-mono font-bold text-gray-200"></span>
                        </div>
                        <div class="hidden md:flex flex-col">
                            <span class="text-[9px] text-gray-500 uppercase">Leverage</span>
                            <span class="text-xs font-mono font-bold text-gray-200">x</span>
                        </div>
                    ;
                }

                rowsHtml += 
                    <div class="flex items-center justify-between p-2 lg:p-3 border-b border-white/5 hover:bg-white/5 transition-colors cursor-pointer" onclick="openTradeDetails('')">
                        <div class="flex items-center gap-3 w-1/4 sm:w-auto">
                            <span class="px-1.5 py-0.5 rounded text-[10px] font-black tracking-wider border "></span>
                            <div class="flex flex-col">
                                <span class="text-xs font-bold text-white tracking-tight flex items-center gap-1.5">
                                    <span class="px-1.5 py-[1px] rounded-[3px] border text-[9px] font-black tracking-widest "></span>
                                    <span> CTs</span>
                                </span>
                                <span class="text-[10px] font-mono text-gray-400 uppercase mt-0.5"></span>
                            </div>
                        </div>
                        
                        
                        
                        <div class="hidden lg:flex flex-col">
                            <span class="text-[9px] text-gray-500 uppercase">Entry</span>
                            <span class="text-xs font-mono font-bold text-gray-200"></span>
                        </div>
                        
                        <div class="flex flex-col text-right min-w-[70px]">
                            <span class="text-[9px] text-gray-500 uppercase">Unrealized PnL</span>
                            <span class="text-sm font-black tabular-nums "></span>
                        </div>
                    </div>
                ;
            });

            container.innerHTML = 
                <div class="bg-[#0e1626] border-t border-cyan-500/20 shadow-md">
                    <div class="flex items-center justify-between px-3 lg:px-4 py-2 border-b border-white/5 bg-black/20">
                        <div class="flex items-center gap-2.5">
                            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                            <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Active ()</span>
                        </div>
                        <div class="flex items-center gap-3">
                            <span class="text-[10px] text-gray-400 uppercase tracking-widest">Total PnL:</span>
                            <span class="text-sm font-black tabular-nums ">
                                
                            </span>
                        </div>
                    </div>
                    <div class="flex flex-col max-h-[160px] lg:max-h-[220px] overflow-y-auto">
                        
                    </div>
                </div>
            ;
        }
'''
    html = html.replace(old_func, new_func)

    with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Replaced active position hud")
else:
    print("Could not find updateActivePositionHud")
