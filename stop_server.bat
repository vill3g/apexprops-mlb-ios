@echo off
title Stopping BTC 15M Kalshi AI Trader...
echo ===================================================
echo   Stopping Kalshi AI Trader, worker and tunnel...
echo ===================================================

echo Stopping watchdog first (so nothing gets restarted)...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*server_watchdog.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo Stopping launcher, web server and background worker...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*launch_desktop.py*' -or $_.CommandLine -like '*worker.py*' -or $_.CommandLine -like '*remote_tunnel.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8058,28056 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

echo Stopping this app's ngrok tunnel only (other ngrok tunnels keep running)...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq 'ngrok.exe' -and $_.CommandLine -like '*moneyprinter.ngrok.app*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"


echo.
echo [OK] All Kalshi AI Trader processes have been stopped.
ping 127.0.0.1 -n 3 >nul
