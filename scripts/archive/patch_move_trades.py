import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract Recent Trades block
recent_trades_match = re.search(r'(        <!-- Recent Trades -->.*?</div>\n        </div>)\n\n    </main>', content, re.DOTALL)
if recent_trades_match:
    recent_trades_block = recent_trades_match.group(1)
    
    # Remove from bottom
    content = content.replace(recent_trades_block + '\n\n', '')
    
    # Insert before SaaS Configuration
    content = content.replace('        <!-- SaaS Configuration -->', recent_trades_block + '\n\n        <!-- SaaS Configuration -->')
    
    with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
        f.write(content)
else:
    print("Could not find Recent Trades block")
