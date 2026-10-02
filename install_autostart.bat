@echo off
title Kalshi AI Trader - Start at Login
cd /d "%~dp0"
echo Adding "Kalshi AI Trader" to your Windows Startup folder. At every login it runs
echo start_btc_server.vbs, which starts the watchdog (server + worker + ngrok) with no window.
echo.
powershell -NoProfile -Command "$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'Kalshi AI Trader.lnk'; $s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk); $s.TargetPath = '%~dp0start_btc_server.vbs'; $s.WorkingDirectory = '%~dp0'; $s.Save(); Write-Host ('Created ' + $lnk)"
echo.
echo To undo: delete "Kalshi AI Trader" from the Startup folder (Win+R, type shell:startup).
echo If you already had another startup shortcut for this app, delete the old one so it
echo only starts once (the watchdog ignores a second copy, but one entry is cleaner).
pause
