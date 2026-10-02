import re

js_path = "static/js/admin_users.js"
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

# Make the balance block a flex column or ensure it doesn't overlap
pattern = r'<div class="flex gap-1 items-center">\s*<input type="text" id="edit_paper_balance"([^>]+)>\s*<button type="button" id="btn_quick_reset_balance"([^>]+)>([^<]+)</button>'

def replacement(match):
    input_tag = f'<input type="text" id="edit_paper_balance"{match.group(1)}>'
    button_tag = f'<button type="button" id="btn_quick_reset_balance"{match.group(2)}>{match.group(3)}</button>'
    
    return f"""<div class="flex flex-col sm:flex-row gap-1.5 sm:gap-1 items-start sm:items-center">
                  <div class="flex w-full gap-1">
                      {input_tag}
                      {button_tag}
                  </div>"""

js = re.sub(pattern, replacement, js)

with open(js_path, "w", encoding="utf-8") as f:
    f.write(js)
print("Updated admin_users.js layout!")
