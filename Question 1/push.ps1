$env:PATH = "C:\Users\ub02-glab-024\AppData\Local\MinGit\cmd;" + $env:PATH
Set-Location "C:\Users\ub02-glab-024\Desktop\DMW LAB EXAM\Data-Mining-and-Warehouse"
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "Staging and Pushing Question 1 to GitHub:" -ForegroundColor Cyan
Write-Host "https://github.com/nagnishal/Data-Mining-and-Warehouse.git" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
git add "Question 1" README.md
git commit -m "feat(question1): Add complete Annapurna Stores Data Warehouse solution, pipeline, and reports"
git push origin main
