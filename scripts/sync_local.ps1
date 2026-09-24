# 로컬 PC(Windows)에서 Drive 동기화 폴더 전체를 색인하고 GitHub에 올린다.
# 사용법: powershell -ExecutionPolicy Bypass -File scripts\sync_local.ps1 -LectureDir "G:\내 드라이브\강의안\01_강의관련"
param(
  [string]$LectureDir = $env:LECTURE_DIR
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
Set-Location (Join-Path $PSScriptRoot "..")
if (-not $LectureDir) { throw "-LectureDir 로 01_강의관련 폴더 경로를 지정하세요" }
git pull --ff-only
python kg/build.py --src "$LectureDir"
python kg/query.py stats
git add graph data
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) { Write-Host "변경 없음"; exit 0 }
git commit -m "강의안 지식그래프 갱신 ($(Get-Date -Format yyyy-MM-dd))"
git push
