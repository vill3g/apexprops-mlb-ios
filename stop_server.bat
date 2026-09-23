@echo off
title Stopping BTC 15M Kalshi AI Trader...
echo ===================================================
echo   Stopping Kalshi AI Trader and Remote Tunnel...
echo ===================================================

echo Stopping Cloudflare Tunnel...
taskkill /F /IM cloudflared.exe 2>nul

echo Stopping Python server and watchdog processes...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8056,28056 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*server_watchdog.py*' -or $_.CommandLine -like '*remote_tunnel.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo.
echo [OK] All Kalshi AI Trader server and tunnel processes have been stopped.
ping 127.0.0.1 -n 3 >nul
