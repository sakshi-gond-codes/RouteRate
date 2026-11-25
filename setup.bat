@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title RouteRate - Setup

echo.
echo  ============================================================
echo    RouteRate - Voice Rate Deck Engine : one-click setup
echo  ============================================================
echo   Needs: Python 3.12+ and a running MySQL 8 server.
echo.

rem ---- 1. Find Python 3.12 or newer -------------------------------------
set "PYCMD="
for %%P in ("py -3.12" "py -3.13" "py -3" "python" "python3") do (
  if not defined PYCMD (
    %%~P -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
    if !errorlevel! equ 0 set "PYCMD=%%~P"
  )
)
if not defined PYCMD (
  echo [ERROR] Python 3.12 or newer was not found.
  echo         Download it from https://www.python.org/downloads/
  echo         and tick "Add python.exe to PATH" during installation.
  goto :fail
)
echo [1/6] Python found:
%PYCMD% --version

rem ---- 2. Virtual environment -------------------------------------------
if exist ".venv\Scripts\python.exe" ( 
  echo [2/6] Virtual environment already exists.
) else (
  echo [2/6] Creating virtual environment in .venv ...
  %PYCMD% -m venv .venv
  if errorlevel 1 goto :fail
)
set "VPY=.venv\Scripts\python.exe"

rem ---- 3. Packages --------------------------------------------------------
echo [3/6] Installing Python packages. The first run can take a few minutes...
"%VPY%" -m pip install --upgrade pip --disable-pip-version-check --quiet
if errorlevel 1 goto :fail
"%VPY%" -m pip install -r requirements.txt --disable-pip-version-check
if errorlevel 1 goto :fail

rem ---- 4. MySQL connection and database ---------------------------------
echo.
echo [4/6] MySQL database
"%VPY%" scripts\configure.py
if errorlevel 1 goto :fail

rem ---- 5. Tables ------------------------------------------------------------
echo.
echo [5/6] Creating tables with Django migrations ...
"%VPY%" manage.py migrate --noinput
if errorlevel 1 goto :fail

rem ---- 6. Demo data ---------------------------------------------------------
echo.
echo [6/6] Loading demo data (fictional vendors, rate decks, LCR runs, rate sheets) ...
"%VPY%" manage.py seed_demo --if-empty
if errorlevel 1 goto :fail

echo.
echo  ============================================================
echo    Setup complete!
echo    Double-click start.bat to run RouteRate.
echo    Log in as admin, analyst or viewer. Password: RouteRate@123
echo  ============================================================
echo.
pause
exit /b 0

:fail
echo.
echo [ERROR] Setup did not finish. Read the message above, fix the problem,
echo         then run setup.bat again. It is safe to run it more than once.
echo.
pause
exit /b 1
