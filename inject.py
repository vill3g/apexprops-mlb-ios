import re

html_path = r'C:\Users\Vill3\Desktop\ShadowTraderAi\static\saas_dashboard.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

wallet_ui = '''
                <!-- Wallet Operations Section -->
                <div class="mt-6 mb-2 flex items-center justify-between px-1">
                    <span class="text-[11px] font-bold text-gray-300 uppercase tracking-wider">Wallet Operations</span>
                </div>
                <div class="bg-black/20 border border-white/5 rounded-2xl overflow-hidden divide-y divide-white/5">
                    
                    <!-- Row: Exchange Transfer -->
                    <div class="p-3.5 flex flex-col gap-3">
                        <div class="flex items-start gap-2.5 min-w-0">
                            <div class="w-7 h-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center shrink-0 text-xs font-bold mt-0.5">
                                ??
                            </div>
                            <div class="flex flex-col w-full">
                                <span class="text-xs font-semibold text-white tracking-tight">Transfer Funds Between Exchanges</span>
                                <span class="text-[10px] text-gray-400 leading-snug mt-0.5 mb-2">Move cash instantly between your Main Kalshi Wallet and Kalshi Crypto Wallet.</span>
                                
                                <div class="flex items-center gap-2 mb-2 w-full">
                                    <select id="transfer-direction" class="flex-1 bg-black/40 border border-white/10 rounded-xl px-2 py-2 text-xs font-semibold text-white outline-none focus:border-cyan-500">
                                        <option value="main_to_crypto">Main -> Crypto Wallet</option>
                                        <option value="crypto_to_main">Crypto -> Main Wallet</option>
                                    </select>
                                </div>
                                <div class="flex items-center gap-2 w-full">
                                    <div class="flex items-center bg-black/40 border border-white/10 rounded-xl px-2.5 py-1.5 focus-within:border-cyan-500 transition-all flex-1">
                                        <span class="text-xs text-gray-400 font-bold mr-1">$</span>
                                        <input type="number" id="transfer-amount" placeholder="0.00" min="0.01" step="0.01" class="w-full bg-transparent text-left font-mono font-bold text-white text-xs outline-none">
                                    </div>
                                    <button onclick="executeWalletTransfer()" id="transfer-btn" class="px-4 py-1.5 bg-emerald-500 hover:bg-emerald-400 active:scale-95 text-black font-bold text-xs rounded-xl transition-all whitespace-nowrap">
                                        Transfer
                                    </button>
                                </div>
                                <div id="transfer-status" class="text-[10px] mt-2 hidden rounded p-1.5 font-semibold"></div>
                            </div>
                        </div>
                    </div>

                </div>
'''

new_html = re.sub(
    r'(Orders are validated automatically against your cash balance before submission\.\s*</div>)',
    r'\1\n' + wallet_ui,
    html
)

if new_html != html:
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(new_html)
    print("Injected wallet UI successfully.")
else:
    print("Could not find target block!")
