file_path = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\database\models.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()
if "\\nCREATE TABLE" in content:
    content = content.replace("\\nCREATE TABLE", "\nCREATE TABLE")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        print("Fixed literal slash-n")
else:
    print("No literal slash-n")
