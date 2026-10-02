import re

with open('static/js/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

patch = """
          cdPill.style.color = `rgb(${r}, ${g}, ${b})`;
          cdPill.style.borderColor = `rgba(${r}, ${g}, ${b}, 0.75)`;
          cdPill.style.backgroundColor = `rgba(${r}, ${g}, ${b}, 0.14)`;
          cdPill.style.boxShadow = `0 0 10px rgba(${r}, ${g}, ${b}, 0.3)`;
          
          const cdText = document.getElementById("btcCountdown");
          const cdBar = document.getElementById("btcCountdownBar");
          if (cdText) cdText.style.color = `rgb(${r}, ${g}, ${b})`;
          if (cdBar) {
              cdBar.style.backgroundColor = `rgb(${r}, ${g}, ${b})`;
              cdBar.style.boxShadow = `0 0 8px rgba(${r}, ${g}, ${b}, 0.6)`;
          }
"""

content = re.sub(r'cdPill\.style\.color = `rgb\(\$\{r\}, \$\{g\}, \$\{b\}\)`;\s*cdPill\.style\.borderColor = `rgba\(\$\{r\}, \$\{g\}, \$\{b\}, 0\.75\)`;\s*cdPill\.style\.backgroundColor = `rgba\(\$\{r\}, \$\{g\}, \$\{b\}, 0\.14\)`;\s*cdPill\.style\.boxShadow = `0 0 10px rgba\(\$\{r\}, \$\{g\}, \$\{b\}, 0\.3\)`;', patch.strip(), content)

with open('static/js/app.js', 'w', encoding='utf-8') as f:
    f.write(content)
