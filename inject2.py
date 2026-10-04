import re

html_path = r'C:\Users\Vill3\Desktop\ShadowTraderAi\static\saas_dashboard.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# Fix the emoji and add balance HTML
old_ui = r'''<div class="w-7 h-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center shrink-0 text-xs font-bold mt-0.5">
                                ??
                            </div>
                            <div class="flex flex-col w-full">
                                <span class="text-xs font-semibold text-white tracking-tight">Transfer Funds Between Exchanges</span>
                                <span class="text-[10px] text-gray-400 leading-snug mt-0.5 mb-2">Move cash instantly between your Main Kalshi Wallet and Kalshi Crypto Wallet.</span>'''

new_ui = r'''<div class="w-7 h-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center shrink-0 mt-0.5">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path></svg>
                            </div>
                            <div class="flex flex-col w-full">
                                <span class="text-xs font-semibold text-white tracking-tight flex items-center justify-between">
                                    <span>Transfer Funds</span>
                                    <button onclick="refreshWalletBalances()" class="w-5 h-5 flex items-center justify-center bg-white/5 hover:bg-white/10 rounded-md transition-colors" title="Refresh Balances"><svg class="w-3 h-3 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg></button>
                                </span>
                                
                                <!-- Balance display cards -->
                                <div class="grid grid-cols-2 gap-2 mt-2 mb-3">
                                    <div class="bg-black/40 border border-white/5 rounded-lg p-2 flex flex-col">
                                        <span class="text-[9px] text-gray-500 font-bold uppercase tracking-wider mb-0.5">Main Wallet</span>
                                        <span id="wallet-main-bal" class="text-xs font-mono font-bold text-white tracking-tight">$--.--</span>
                                    </div>
                                    <div class="bg-black/40 border border-white/5 rounded-lg p-2 flex flex-col">
                                        <span class="text-[9px] text-gray-500 font-bold uppercase tracking-wider mb-0.5">Crypto Wallet</span>
                                        <span id="wallet-crypto-bal" class="text-xs font-mono font-bold text-white tracking-tight">$--.--</span>
                                    </div>
                                </div>
'''

if '??' in html:
    new_html = html.replace(old_ui, new_ui)
    if new_html != html:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(new_html)
        print("Patched UI successfully.")
    else:
        print("Failed to replace string.")
else:
    print("Already patched or ?? not found.")
