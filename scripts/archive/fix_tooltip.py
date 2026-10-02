import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

bad_block = """  <!-- Accuracy Hover Tooltip Panel -->
  <div id="accuracyTooltip" class="fixed hidden pointer-events-auto z-[99999] bg-slate-950/95 border border-cyan-500/50 rounded-2xl p-3.5 shadow-2xl backdrop-blur-md text-xs font-mono text-white max-w-xs transition-opacity duration-150 animate-in fade-in duration-150"></div>"""

good_block = """  <!-- Global Sleek Tooltip -->
  <div id="tooltip" class="fixed hidden pointer-events-none z-[99999] bg-slate-950/95 border border-cyan-500/50 rounded-xl p-2.5 shadow-2xl backdrop-blur-md text-xs font-mono text-white max-w-xs transition-opacity duration-150"></div>

  <!-- Accuracy Hover Tooltip Panel -->
  <div id="accuracyTooltip" class="fixed hidden pointer-events-auto z-[99999] bg-slate-950/95 border border-cyan-500/50 rounded-2xl p-3.5 shadow-2xl backdrop-blur-md text-xs font-mono text-white max-w-xs transition-opacity duration-150 animate-in fade-in duration-150"></div>"""

if bad_block in html:
    html = html.replace(bad_block, good_block)
    with open('static/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Added global tooltip element!")
else:
    print("Could not find block")
