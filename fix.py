
import re
with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

bad_str = """toast.className = \fex items-center gap-3 w-full max-w-sm p-3.5 rounded-[24px] shadow-[0_10px_40px_rgba(0,0,0,0.6)] backdrop-blur-xl border \\ transition-all duration-500 ease-out translate-y-[-150%] opacity-0\\;"""
good_str = "toast.className = `flex items-center gap-3 w-full max-w-sm p-3.5 rounded-[24px] shadow-[0_10px_40px_rgba(0,0,0,0.6)] backdrop-blur-xl border ${bg} transition-all duration-500 ease-out translate-y-[-150%] opacity-0`;"

content = content.replace("toast.className = \fex", "toast.className = `flex")
content = content.replace("backdrop-blur-xl border \\ transition-all", "backdrop-blur-xl border ${bg} transition-all")
content = content.replace("opacity-0\\;", "opacity-0`;")
content = content.replace("toast.innerHTML = \\", "toast.innerHTML = `")
content = content.replace("</div>\\;", "</div>`;")
content = content.replace("??", "?") # Emojis were broken

with open("static/saas_dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)

