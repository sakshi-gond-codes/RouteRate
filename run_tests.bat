@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title RouteRate - tests

if not exist ".venv\Scripts\python.exe" (
  echo Run setup.bat first.
  pause
  exit /b 1
)
echo Running the automated test suite. Django creates a temporary test database in MySQL.
".venv\Scripts\python.exe" manage.py test --noinput
pause
