import re

with open('static/js/dashboard.js', 'r', encoding='utf-8') as f:
    js = f.read()

# 1. Remove the broken logic from inside the template string
broken_part = """
                            let resultRow = "";
                            if (t.status !== "OPEN") {
                                let resText = "N/A";
                                let resColor = "text-gray-500";
                                if (t.official_result === "YES") {
                                    resText = "YES ABOVE";
                                    resColor = "text-emerald-400";
                                } else if (t.official_result === "NO") {
                                    resText = "NO BELOW";
                                    resColor = "text-rose-400";
                                } else if (t.exit_reason) {
                                    resText = "CLOSED EARLY";
                                    resColor = "text-amber-400";
                                }
                                resultRow = `
                                <div class="flex items-center gap-1.5 mt-0.5 mb-1">
                                    <span class="text-[9px] font-bold text-gray-500 uppercase">Result</span>
                                    <span class="text-[9px] font-black ${resColor}">${resText}</span>
                                </div>`;
                            } else {
                                resultRow = `
                                <div class="flex items-center gap-1.5 mt-0.5 mb-1">
                                    <span class="text-[9px] font-bold text-gray-500 uppercase">Result</span>
                                    <span class="text-[9px] font-black text-amber-500 animate-pulse">PENDING...</span>
                                </div>`;
                            }
"""
js = js.replace(broken_part, "")

# 2. Insert the logic BEFORE `htmlString += \``
logic = """
                            let resultRow = "";
                            if (t.status !== "OPEN") {
                                let resText = "N/A";
                                let resColor = "text-gray-500";
                                if (t.official_result === "YES") {
                                    resText = "YES ABOVE";
                                    resColor = "text-emerald-400";
                                } else if (t.official_result === "NO") {
                                    resText = "NO BELOW";
                                    resColor = "text-rose-400";
                                } else if (t.exit_reason) {
                                    resText = "CLOSED EARLY";
                                    resColor = "text-amber-400";
                                }
                                resultRow = `<div class="flex items-center gap-1.5 mt-0.5 mb-1">
                                    <span class="text-[9px] font-bold text-gray-500 uppercase">Result</span>
                                    <span class="text-[9px] font-black ${resColor}">${resText}</span>
                                </div>`;
                            } else {
                                resultRow = `<div class="flex items-center gap-1.5 mt-0.5 mb-1">
                                    <span class="text-[9px] font-bold text-gray-500 uppercase">Result</span>
                                    <span class="text-[9px] font-black text-amber-500 animate-pulse">PENDING...</span>
                                </div>`;
                            }
                            
                            const tradeJsonSafe = btoa(encodeURIComponent(JSON.stringify(t)));
                            htmlString += `"""

target_insertion = """                            const tradeJsonSafe = btoa(encodeURIComponent(JSON.stringify(t)));
                            htmlString += `"""
                            
js = js.replace(target_insertion, logic)

with open('static/js/dashboard.js', 'w', encoding='utf-8') as f:
    f.write(js)
    
print("Fixed JS syntax error!")
