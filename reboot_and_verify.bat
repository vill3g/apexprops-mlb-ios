@echo off
title AI Trader and Sports Predictions - Full Reboot
color 0B
cd /d "%~dp0"

echo ===================================================
echo   AI TRADER AND SPORTS PREDICTIONS - FULL REBOOT
echo ===================================================
echo.

echo [1/4] Stopping servers, workers and ngrok tunnels...
call "%~dp0stop_server.bat" >nul
taskkill /f /im ngrok.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8057 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8058 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)
echo   Done.
echo.

echo [2/4] Starting Unified Watchdog...
wscript "%~dp0start_btc_server.vbs"
echo   Watchdog launched in the background. It will start BOTH servers and BOTH tunnels.
echo.

echo [3/4] Waiting for local servers to come up (up to ~80s)...
set "LOCAL_OK=0"
for /L %%i in (1,1,40) do (
    powershell -NoProfile -NonInteractive -Command "try { $r1 = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8058/api/health' -TimeoutSec 2; $r2 = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8057/api/health' -TimeoutSec 10; if ($r1.StatusCode -eq 200 -and $r2.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" <NUL >nul 2>&1
    if not errorlevel 1 (
        set "LOCAL_OK=1"
        goto :local_done
    )
    ping 127.0.0.1 -n 3 >nul
)
:local_done
if "%LOCAL_OK%"=="1" (
    echo   [OK] Local servers are responding on ports 8058 and 8057.
) else (
    echo   [WARN] Local servers did not respond within 80s - check server_watchdog.log.
)
echo.

echo [4/4] Waiting for Ngrok tunnels to come online (up to ~90s)...
set "REMOTE_OK=0"
for /L %%i in (1,1,30) do (
    powershell -NoProfile -NonInteractive -Command "try { $r1 = Invoke-WebRequest -UseBasicParsing -Uri 'https://moneyprinter.ngrok.app/api/health' -TimeoutSec 4; $r2 = Invoke-WebRequest -UseBasicParsing -Uri 'https://mlb-predictz.ngrok.app/api/health' -TimeoutSec 4; if ($r1.StatusCode -eq 200 -and $r2.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" <NUL >nul 2>&1
    if not errorlevel 1 (
        set "REMOTE_OK=1"
        goto :remote_done
    )
    ping 127.0.0.1 -n 4 >nul
)
:remote_done

echo.
echo ===================================================
if "%REMOTE_OK%"=="1" (
    echo   [SUCCESS] Both ngrok apps are LIVE and responding.
    echo ===================================================
    start "" "https://moneyprinter.ngrok.app/"
    start "" "https://mlb-predictz.ngrok.app/"
) else (
    if "%LOCAL_OK%"=="1" (
        echo   [PARTIAL] Servers are up locally, but tunnels are not responding yet.
        start "" "http://127.0.0.1:8058/"
        start "" "http://127.0.0.1:8057/"
    ) else (
        echo   [FAILED] Nothing is responding yet. Check server_watchdog.log.
    )
    echo ===================================================
)
echo.
