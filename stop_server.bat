@echo off
title Stopping AI Trader and Sports Predictions...
echo ===================================================
echo   Stopping AI Trader, Sports Bridge and Tunnels...
echo ===================================================

echo Stopping watchdog first (so nothing gets restarted)...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*server_watchdog.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo Stopping launcher, web server, sports bridge and background worker...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*launch_desktop.py*' -or $_.CommandLine -like '*worker.py*' -or $_.CommandLine -like '*remote_tunnel.py*' -or $_.CommandLine -like '*backend.main:app*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8058,8057,28056 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

echo Stopping ngrok tunnels...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq 'ngrok.exe' -or $_.CommandLine -like '*ngrok.exe*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo.
echo [OK] All AI Trader and Sports Bridge processes have been stopped.
ping 127.0.0.1 -n 2 >nul
