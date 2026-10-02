@echo off
title Kalshi AI Trader (Auto-Restart)
color 0A
cd /d "%~dp0"

echo ==================================================
echo      KALSHI AI TRADER - CONTINUOUS DAEMON
echo ==================================================
echo Runs the watchdog in this window. It keeps the web server, the
echo background worker and the ngrok tunnel running and restarts any
echo of them that crash. Close this window or run stop_server.bat to stop.
echo (start_btc_server.vbs does the same thing without a window.)
echo.

".venv\Scripts\python.exe" server_watchdog.py
echo.
echo Watchdog exited (another copy may already be running - see server_watchdog.log).
pause
