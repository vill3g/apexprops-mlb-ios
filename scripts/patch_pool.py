filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\auto_executor\executor.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("ProcessPoolExecutor", "ThreadPoolExecutor")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("Patched ProcessPoolExecutor to ThreadPoolExecutor")
