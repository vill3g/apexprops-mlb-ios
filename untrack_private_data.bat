@echo off
title Kalshi AI Trader - Stop tracking private data in git
cd /d "%~dp0"
echo This removes private files (user database, user folders, tokens, QR code) from git
echo tracking. The files stay on your disk; .gitignore keeps them out of future commits.
echo.
git rm --cached -r --ignore-unmatch --quiet "backend/data/*.db" "backend/data/*.db-wal" "backend/data/*.db-shm" backend/data/users token.txt .local_token static/assets/server_qr.png data/guests
echo.
echo Files now staged for removal from git:
git diff --cached --name-status
echo.
set /p CONFIRM=Commit these removals now? (Y/N): 
if /I "%CONFIRM%"=="Y" (
    git commit -m "Stop tracking private runtime data"
    echo.
    echo Committed. If this repo is on GitHub, push as usual. Old commits still contain
    echo these files, so treat anything that was in them as exposed.
) else (
    echo Not committed. Run: git commit -m "Stop tracking private runtime data"
)
pause
