@echo off
title BTC 15M Ngrok Tunnel
cd /d "%~dp0"
.\.venv\Scripts\python.exe remote_tunnel.py
pause
