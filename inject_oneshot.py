with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''<span class="text-slate-300 text-[10px] sm:text-xs cursor-help flex items-center gap-1">\u26a1 Force Trade on PASS</span>
                      <label class="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" id="settingIgnorePass" class="sr-only peer">'''

replacement = target + '''
                      </label>
                    </div>
                    <div class="flex items-center justify-between px-1.5 py-1 rounded-lg bg-slate-900 border border-slate-800">
                      <span class="text-slate-300 text-[10px] sm:text-xs cursor-help flex items-center gap-1">\U0001f3af 1-Shot AI Trade</span>
                      <label class="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" id="settingOneShotAiStartTrade" class="sr-only peer">'''

text = text.replace(target, replacement)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(text)
print("Injected oneShotAiStartTrade!")
