import psutil

for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmd = ' '.join(proc.info['cmdline'] or [])
        if '8058' in cmd or 'backend.main' in cmd:
            print(f"Killing PID {proc.info['pid']}: {cmd[:80]}")
            proc.kill()
    except Exception as e:
        pass
print("Done finding/killing 8058 processes.")
