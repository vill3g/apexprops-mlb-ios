file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\admin_users.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """  function getAdminAuthHeaders() {
    const headers = { "Content-Type": "application/json" };
    const saasToken = localStorage.getItem("saas_token");
    if (saasToken) {
      headers["Authorization"] = `Bearer ${saasToken}`;
    }
  }"""

replacement = """  function getAdminAuthHeaders() {
    const headers = { "Content-Type": "application/json" };
    const saasToken = localStorage.getItem("saas_token");
    if (saasToken) {
      headers["Authorization"] = `Bearer ${saasToken}`;
    }
    return headers;
  }"""

# Try a more forgiving regex replace to handle indentation differences
import re
pattern = re.compile(r'headers\["Authorization"\] = `Bearer \$\{saasToken\}`;[\s\r\n]*\}[\s\r\n]*(?![\s\r\n]*return)')
content = pattern.sub('headers["Authorization"] = `Bearer ${saasToken}`;\n    }\n    return headers;\n', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("admin_users.js patched!")
