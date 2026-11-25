@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title RouteRate - reset demo data

if not exist ".venv\Scripts\python.exe" (
  echo Run setup.bat first.
  pause
  exit /b 1
)
echo This deletes ALL vendors, rate decks, LCR runs and rate sheets in the database
echo and loads the demo data again.
set /p "ANSWER=Type YES to continue: "
if /i not "%ANSWER%"=="YES" (
  echo Cancelled. Nothing was changed.
  pause
  exit /b 0
)
".venv\Scripts\python.exe" manage.py seed_demo --reset
pause
