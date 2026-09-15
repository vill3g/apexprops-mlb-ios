import re

def rewrite():
    file_path = 'static/index.html'
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # We will declare kalshiFixedSize right after kalshiCurrentPriceEst
    if 'let kalshiFixedSize =' not in html:
        html = html.replace(
            'let kalshiCurrentPriceEst = 0.65;',
            'let kalshiCurrentPriceEst = 0.65;\n    let kalshiFixedSize = 35.00;'
        )

    # 1. Rewrite updateKalshiEstCostDisplay
    old_display = re.search(r'function updateKalshiEstCostDisplay\(\) \{.*?\n    \}', html, re.DOTALL).group(0)
    new_display = """function updateKalshiEstCostDisplay() {
      const sizeInput = document.getElementById("kalshiSizeInput");
      const ctInput = document.getElementById("kalshiContractsInput");
      if (!sizeInput || !ctInput) return;
      
      const dynamicCt = Math.max(1, Math.round(kalshiFixedSize / kalshiCurrentPriceEst));
      kalshiCurrentContracts = dynamicCt; // Keep synced for other UI elements
      
      if (document.activeElement !== ctInput) {
        ctInput.value = dynamicCt;
      }
      if (document.activeElement !== sizeInput) {
        sizeInput.value = kalshiFixedSize.toFixed(2);
      }
    }"""
    html = html.replace(old_display, new_display)

    # 2. Rewrite updateKalshiSize
    old_size = re.search(r'function updateKalshiSize.*?saveKalshiContractsCount\(ct\);\s*\}', html, re.DOTALL).group(0)
    new_size = """function updateKalshiSize(val) {
      let size = parseFloat(val);
      if (isNaN(size) || size <= 0) size = kalshiCurrentPriceEst;
      kalshiFixedSize = size;
      
      const dynamicCt = Math.max(1, Math.round(kalshiFixedSize / kalshiCurrentPriceEst));
      kalshiCurrentContracts = dynamicCt;
      
      const ctInput = document.getElementById("kalshiContractsInput");
      if (ctInput) ctInput.value = dynamicCt;
      
      updateKalshiPayoutCalculator();
      saveAiMaxCap(kalshiFixedSize);
    }"""
    html = html.replace(old_size, new_size)

    # 3. Rewrite updateKalshiContracts
    old_ct = re.search(r'async function updateKalshiContracts.*?saveKalshiContractsCount\(ct\);\s*\}', html, re.DOTALL).group(0)
    new_ct = """async function updateKalshiContracts(val) {
      let ct = parseInt(val, 10);
      if (isNaN(ct) || ct < 1) ct = 1;
      kalshiCurrentContracts = ct;
      kalshiFixedSize = ct * kalshiCurrentPriceEst;
      
      const sizeInput = document.getElementById("kalshiSizeInput");
      if (sizeInput) sizeInput.value = kalshiFixedSize.toFixed(2);
      
      updateKalshiPayoutCalculator();
      saveAiMaxCap(kalshiFixedSize);
    }"""
    html = html.replace(old_ct, new_ct)

    # Add the saveAiMaxCap function right after
    if 'async function saveAiMaxCap' not in html:
        new_ct_block = new_ct + """\n\n    async function saveAiMaxCap(maxCapVal) {
      try {
        const aiSetStr = localStorage.getItem("kalshiAiSettings");
        if (aiSetStr) {
          const aiSet = JSON.parse(aiSetStr);
          aiSet.maxCap = maxCapVal;
          localStorage.setItem("kalshiAiSettings", JSON.stringify(aiSet));
          
          const apiBase = getKalshiApiBase();
          await fetch(`${apiBase}/api/btc/trade/ai_settings`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(aiSet)
          }).catch(()=>{});
        }
      } catch (err) {
        console.warn("Failed to persist maxCap:", err);
      }
    }"""
        html = html.replace(new_ct, new_ct_block)

    # 4. Patch backend polling so it doesn't overwrite our contracts count!
    # In polling, we don't want `kalshiCurrentContracts = data.max_contracts` to ruin our fixed size!
    # Find `kalshiCurrentContracts = parseInt(data.max_contracts) || 1;`
    poll_override = 'kalshiCurrentContracts = parseInt(data.max_contracts) || 1;'
    if poll_override in html:
        html = html.replace(poll_override, '// Ignored max_contracts from polling to preserve dynamic size logic')

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html)

if __name__ == '__main__':
    rewrite()
    print("Rewritten Kalshi size logic successfully!")
