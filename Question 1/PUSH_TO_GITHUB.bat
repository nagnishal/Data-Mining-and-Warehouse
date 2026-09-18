@echo off
set "PATH=C:\Users\ub02-glab-024\AppData\Local\MinGit\cmd;%PATH%"
cd /d "C:\Users\ub02-glab-024\Desktop\DMW LAB EXAM\Data-Mining-and-Warehouse"

echo ================================================================
echo Staging and Pushing Question 1 to GitHub:
echo https://github.com/nagnishal/Data-Mining-and-Warehouse.git
echo ================================================================
echo.

git add "Question 1" README.md
git commit -m "feat(question1): Add complete Annapurna Stores Data Warehouse solution, pipeline, and reports"
git push origin main

echo.
if %ERRORLEVEL% EQU 0 (
    echo ================================================================
    echo SUCCESS: Question 1 was pushed to GitHub successfully!
    echo ================================================================
) else (
    echo ================================================================
    echo NOTE: If GitHub asks for a password, enter your GitHub
    echo Personal Access Token (PAT).
    echo ================================================================
)
echo.
pause
