import re

with open("static/js/dashboard.js", "r", encoding="utf-8") as f:
    code = f.read()

pattern = r"""                    const priceEl = document\.getElementById\('live-btc-price'\);
                    if \(priceEl\) \{
                        const newPriceText = '\$' \+ parseFloat\(tData\.price\)\.toLocaleString\(undefined, \{minimumFractionDigits: 2, maximumFractionDigits: 2\}\);
                        if \(priceEl\.innerText !== newPriceText\) \{
                            priceEl\.innerText = newPriceText;
                            priceEl\.classList\.remove\('animate-pulse'\);
                            priceEl\.classList\.remove\('animate-price-flash'\);
                            void priceEl\.offsetWidth; // trigger reflow
                            priceEl\.classList\.add\('animate-price-flash'\);
                        \}
                    \}"""

replacement = """                    const priceEl = document.getElementById('live-btc-price');
                    if (priceEl) {
                        const newPrice = parseFloat(tData.price);
                        const newPriceText = '$' + newPrice.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                        if (priceEl.innerText !== newPriceText) {
                            let oldPriceText = priceEl.innerText.replace('$', '').replace(/,/g, '');
                            let oldPrice = parseFloat(oldPriceText);
                            priceEl.innerText = newPriceText;
                            
                            priceEl.classList.remove('animate-pulse', 'animate-price-flash', 'text-green-400', 'text-red-400', 'text-white');
                            void priceEl.offsetWidth; // trigger reflow
                            
                            if (!isNaN(oldPrice)) {
                                if (newPrice > oldPrice) {
                                    priceEl.classList.add('text-green-400', 'animate-price-flash');
                                } else if (newPrice < oldPrice) {
                                    priceEl.classList.add('text-red-400', 'animate-price-flash');
                                } else {
                                    priceEl.classList.add('text-white', 'animate-price-flash');
                                }
                            } else {
                                priceEl.classList.add('text-white', 'animate-price-flash');
                            }
                            
                            // Remove color after flash
                            setTimeout(() => {
                                priceEl.classList.remove('text-green-400', 'text-red-400');
                                priceEl.classList.add('text-white');
                            }, 500);
                        }
                    }"""

new_code = re.sub(pattern, replacement, code, flags=re.DOTALL)

with open("static/js/dashboard.js", "w", encoding="utf-8") as f:
    f.write(new_code)
print("Updated dashboard.js to include green/red price flash!")
