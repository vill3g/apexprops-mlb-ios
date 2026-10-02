@echo off
title Kalshi AI Trader - Reboot & Verify
color 0B
cd /d "%~dp0"

rem --- Keep the desktop shortcut pointed at this script (harmless if it already exists) ---
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_reboot_shortcut.ps1" >nul 2>&1

echo ===================================================
echo   KALSHI AI TRADER - FULL REBOOT
echo ===================================================
echo.

echo [1/4] Stopping server, worker and ngrok tunnel...
call "%~dp0stop_server.bat" >nul
echo   Done.
echo.

echo [2/4] Starting watchdog (server + worker + ngrok tunnel)...
wscript "%~dp0start_btc_server.vbs"
echo   Watchdog launched in the background.
echo.

echo [3/4] Waiting for the local server to come up (up to ~80s)...
set "LOCAL_OK=0"
for /L %%i in (1,1,40) do (
    powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8058/api/health' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set "LOCAL_OK=1"
        goto :local_done
    )
    timeout /t 2 >nul
)
:local_done
if "%LOCAL_OK%"=="1" (
    echo   [OK] Local server is responding on port 8058.
) else (
    echo   [WARN] Local server did not respond within 80s - check server_watchdog.log.
)
echo.

echo [4/4] Waiting for https://moneyprinter.ngrok.app to come online (up to ~90s)...
set "REMOTE_OK=0"
for /L %%i in (1,1,30) do (
    powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'https://moneyprinter.ngrok.app/api/health' -TimeoutSec 4; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set "REMOTE_OK=1"
        goto :remote_done
    )
    timeout /t 3 >nul
)
:remote_done

echo.
echo ===================================================
if "%REMOTE_OK%"=="1" (
    echo   [SUCCESS] moneyprinter.ngrok.app is LIVE and responding.
    echo ===================================================
    start "" "https://moneyprinter.ngrok.app/"
) else (
    if "%LOCAL_OK%"=="1" (
        echo   [PARTIAL] Server is up locally, but moneyprinter.ngrok.app
        echo   did not respond yet. Ngrok can take a bit longer on a fresh
        echo   reboot - check REMOTE_ACCESS_URL.txt on the Desktop in a
        echo   minute, or just run this shortcut again.
    ) else (
        echo   [FAILED] Nothing is responding yet. Check server_watchdog.log
        echo   in this folder for errors, or try running this shortcut again.
    )
    echo ===================================================
)
echo.
pause
