@echo off
title Kalshi AI Trader - Daily Backup Setup
cd /d "%~dp0"
echo Creating a Windows scheduled task that backs up your data every day at 3:30 AM
echo (backups go to the "backups" folder here; the newest 14 are kept).
echo.
schtasks /Create /F /SC DAILY /ST 03:30 /TN "Kalshi AI Trader Backup" /TR "\"%~dp0.venv\Scripts\python.exe\" \"%~dp0scripts\backup_data.py\""
if errorlevel 1 (
    echo.
    echo [ERROR] Could not create the scheduled task.
    pause
    exit /b 1
)
echo.
echo Running a first backup now...
".venv\Scripts\python.exe" scripts\backup_data.py
echo.
echo Done. Backups contain your .env secrets - keep the backups folder private.
pause
