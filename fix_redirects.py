import os

base_dir = r"C:\Users\Vill3\Desktop\ShadowTraderAi\static"

for root, dirs, files in os.walk(base_dir):
    for file in files:
        if file.endswith(".html") or file.endswith(".js"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            content = content.replace("window.location.replace('/admin')", "window.location.replace('./admin_mobile.html')")
            content = content.replace("window.location.href = '/admin'", "window.location.href = './admin_mobile.html'")
            
            content = content.replace("window.location.replace('/saas_dashboard.html')", "window.location.replace('./saas_dashboard.html')")
            content = content.replace("window.location.href = '/saas_dashboard.html'", "window.location.href = './saas_dashboard.html'")
            
            content = content.replace("window.location.replace('/login.html')", "window.location.replace('./login.html')")
            content = content.replace("window.location.href = '/login.html'", "window.location.href = './login.html'")
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
print("Redirects fixed!")
