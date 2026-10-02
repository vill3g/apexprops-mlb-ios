import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

# Fix tailwind css tag
c = re.sub(r'<script src="https://cdn\.tailwindcss\.com">.*?</script>', '<script src="https://cdn.tailwindcss.com"></script>', c, flags=re.DOTALL)

# Fix tradingview tag
c = re.sub(r'<script type="text/javascript" src="https://s3\.tradingview\.com/tv\.js">.*?</script>', '<script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>', c, flags=re.DOTALL)

# Fix tailwind config tag
good_tailwind = """<script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            'kalshi-blue': '#0052FF',
            'kalshi-green': '#00ff88',
            'kalshi-red': '#ff4444',
            'kalshi-dark': '#0b0f19',
            'kalshi-border': '#1e293b'
          }
        }
      }
    }
  </script>"""

c = re.sub(r'<script>\s*tailwind\.config.*?</script>', good_tailwind, c, flags=re.DOTALL)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
