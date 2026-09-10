@echo off
title BTC 15M Kalshi AI Trader
cd /d "%~dp0"
python launch_desktop.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Launcher encountered an issue.
    pause
)
