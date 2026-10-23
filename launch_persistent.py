import subprocess
import sys
import os

app_dir = r"C:\Users\Vill3\Desktop\kalshi-ai-trader"
python_exe = os.path.join(app_dir, ".venv", "Scripts", "python.exe")
watchdog = os.path.join(app_dir, "server_watchdog.py")

# Launch via PowerShell Start-Process with CREATE_BREAKAWAY_FROM_JOB or CIM
ps_cmd = f"Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{{CommandLine = '\"{python_exe}\" \"{watchdog}\" --restart'}}"
res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
print("CIM Output:", res.stdout.strip())
print("CIM Error:", res.stderr.strip())
