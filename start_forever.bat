@echo off
title Kalshi AI Trader (Auto-Restart)
color 0A

echo ==================================================
echo      KALSHI AI TRADER - CONTINUOUS DAEMON
echo ==================================================
echo This script will automatically restart the bot if 
echo it ever crashes or disconnects.
echo.

:loop
echo [%time%] Starting server (HTTP)...
call .venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8056 --no-access-log
echo.
echo [%time%] CRITICAL: Server stopped or crashed!
echo Restarting automatically in 5 seconds...
timeout /t 5 >nul
goto loop
