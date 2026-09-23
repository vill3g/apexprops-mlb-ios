with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

idx_start = c.find('setInterval(loadDashboard, 1000);') + len('setInterval(loadDashboard, 1000);')
idx_end = c.find('    async function saveUserConfig()', idx_start)

# We want to replace the garbage in between with just double newlines
if idx_start > len('setInterval(loadDashboard, 1000);') and idx_end != -1:
    c_new = c[:idx_start] + "\n\n" + c[idx_end:]
    with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
        f.write(c_new)
    print("Cleanup successful.")
else:
    print("Could not find the bounds.")
