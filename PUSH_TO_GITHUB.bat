@echo off
set "PATH=C:\Users\ub02-glab-024\AppData\Local\MinGit\cmd;%PATH%"
cd /d "C:\Users\ub02-glab-024\Desktop\DMW LAB EXAM\Data-Mining-and-Warehouse"

echo ================================================================
echo Pushing Question 2 to GitHub:
echo https://github.com/nagnishal/Data-Mining-and-Warehouse.git
echo ================================================================
echo.

git push origin main

echo.
if %ERRORLEVEL% EQU 0 (
    echo ================================================================
    echo SUCCESS: Question 2 was pushed to GitHub successfully!
    echo ================================================================
) else (
    echo ================================================================
    echo NOTE: If GitHub asks for a password, enter your GitHub
    echo Personal Access Token (PAT).
    echo ================================================================
)
echo.
pause
