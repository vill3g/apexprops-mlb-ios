@echo off
title Stopping BTC 15M Kalshi AI Trader...
echo ===================================================
echo   Stopping Kalshi AI Trader and Remote Tunnel...
echo ===================================================

echo Stopping Cloudflare Tunnel...
taskkill /F /IM cloudflared.exe 2>nul

echo Stopping Python server and watchdog processes...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8056" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a 2>nul
)

wmic process where "CommandLine like '%%server_watchdog.py%%'" call terminate 2>nul
wmic process where "CommandLine like '%%remote_tunnel.py%%'" call terminate 2>nul

echo.
echo [OK] All Kalshi AI Trader server and tunnel processes have been stopped.
ping 127.0.0.1 -n 3 >nul
