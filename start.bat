@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title RouteRate - server

set "VPY=.venv\Scripts\python.exe"
set "PORT=8000"

if not exist "%VPY%" (
  echo RouteRate is not installed yet. Double-click setup.bat first.
  pause
  exit /b 1
)
if not exist ".env" (
  echo The .env settings file is missing. Double-click setup.bat first.
  pause
  exit /b 1
)

echo Checking the database ...
"%VPY%" manage.py migrate --noinput >nul
if errorlevel 1 (
  echo.
  echo [ERROR] Could not connect to MySQL. Make sure the MySQL service is running
  echo         and the login in .env is correct, then try again.
  pause
  exit /b 1
)

echo.
echo  RouteRate is running at  http://127.0.0.1:%PORT%/
echo  Keep this window open while you use the app. Press Ctrl+C to stop it.
echo.
rem Open the browser a few seconds after the server starts
start "" /b cmd /c "timeout /t 4 /nobreak >nul & start "" http://127.0.0.1:%PORT%/"
"%VPY%" manage.py runserver 127.0.0.1:%PORT%
pause
