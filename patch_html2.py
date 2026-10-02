file_path = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add hidden file input right after the avatar
old_avatar = '<div id="socialYourAvatar" class="w-9 h-9 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center font-black text-white text-xs shadow-[0_0_12px_rgba(6,182,212,0.4)]">--</div>'

new_avatar = """<div id="socialYourAvatar" class="w-9 h-9 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center font-black text-white text-xs shadow-[0_0_12px_rgba(6,182,212,0.4)] cursor-pointer hover:ring-2 hover:ring-cyan-400 transition-all bg-cover bg-center" onclick="document.getElementById('profilePicInput').click()" title="Change Profile Picture">--</div>
                          <input type="file" id="profilePicInput" accept="image/*" class="hidden" onchange="uploadProfilePic(event)">"""

if "profilePicInput" not in content:
    content = content.replace(old_avatar, new_avatar)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Injected HTML input")
else:
    print("HTML input already there")
