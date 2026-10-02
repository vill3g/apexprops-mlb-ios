import re

new_body = """            <p class="text-gray-300 text-sm leading-relaxed">
                We've just deployed a massive overhaul to the AUTO execution engine, introducing a 6-Pillar God-Tier architecture designed to maximize win-rate and preserve capital.
            </p>
            
            <ul class="space-y-3 mt-4">
                <li class="flex items-start gap-3">
                    <i class="fas fa-calculator text-green-400 mt-1 flex-shrink-0"></i>
                    <div>
                        <span class="block text-sm font-semibold text-white">Universal EV Gate & Kelly Sizing</span>
                        <span class="block text-xs text-gray-400 mt-0.5">Strict expected value math is now enforced. The bot dynamically sizes up on massive edge and strictly blocks negative EV trades.</span>
                    </div>
                </li>
                <li class="flex items-start gap-3">
                    <i class="fas fa-bullseye text-blue-400 mt-1 flex-shrink-0"></i>
                    <div>
                        <span class="block text-sm font-semibold text-white">"Sweet Spot" Contract Pricing</span>
                        <span class="block text-xs text-gray-400 mt-0.5">The engine now hunts for asymmetric risk/reward, refusing to overpay for premiums above 62&cent; without 78%+ institutional conviction.</span>
                    </div>
                </li>
                <li class="flex items-start gap-3">
                    <i class="fas fa-filter text-purple-400 mt-1 flex-shrink-0"></i>
                    <div>
                        <span class="block text-sm font-semibold text-white">Strike Pin (Dead-Zone) Filter</span>
                        <span class="block text-xs text-gray-400 mt-0.5">Unpredictable 50/50 coin-flips when the market is pinned near the strike under low volatility are now actively bypassed.</span>
                    </div>
                </li>
                <li class="flex items-start gap-3">
                    <i class="fas fa-shield-alt text-red-400 mt-1 flex-shrink-0"></i>
                    <div>
                        <span class="block text-sm font-semibold text-white">Structural Stop-Losses</span>
                        <span class="block text-xs text-gray-400 mt-0.5">Eliminated whipsaw selling. Trailing stops are now driven by physical spot action breaking the 15m EMA-21, not synthetic bid noise.</span>
                    </div>
                </li>
            </ul>"""

def patch_html(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace Version
    content = content.replace("v2.1_update_alert", "v3.0_god_tier_alert")

    # Replace Headers
    content = content.replace(
        '<h3 class="text-xl font-bold text-white tracking-tight">System Update</h3>',
        '<h3 class="text-xl font-bold text-white tracking-tight">Auto 3.0 Engine Deployed</h3>'
    )
    content = content.replace(
        '<p class="text-xs text-blue-400 font-medium">Kalshi AI Trader Upgrades</p>',
        '<p class="text-xs text-green-400 font-medium">God-Tier 6-Pillar Blueprint</p>'
    )

    # Replace Body
    pattern = re.compile(r'<p class="text-gray-300 text-sm leading-relaxed">.*?</ul>', re.DOTALL)
    content = pattern.sub(new_body, content)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

patch_html(r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html")
patch_html(r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\index.html")

print("Successfully updated release notes modals!")
