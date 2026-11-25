@echo off
rem Dice Lab launcher — Windows
rem Starts server/dice-server.py on 0.0.0.0:7373, prints the Tailscale IP,
rem and opens the default browser. Simulation only: never enables live betting.
setlocal EnableExtensions
cd /d "%~dp0"

if "%DICE_PORT%"=="" set "DICE_PORT=7373"
set "PY=python"
where python >nul 2>&1
if errorlevel 1 set "PY=py -3"

where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Python 3.9+ not found. Install Python and try again.
    pause
    exit /b 1
  )
)

set "TSIP="
for /f "usebackq delims=" %%I in (`tailscale ip -4 2^>nul`) do (
  set "TSIP=%%I"
  goto :gotip
)
:gotip

echo.
echo   Dice Lab
echo   Local     : http://localhost:%DICE_PORT%/
if defined TSIP (
  echo   Tailscale : http://%TSIP%:%DICE_PORT%/
) else (
  echo   Tailscale : [not found - run "tailscale ip -4" after logging in]
)
echo.

echo Starting server in a separate window...
start "Dice Lab Server" %PY% server\dice-server.py
timeout /t 2 /nobreak >nul
start "" "http://localhost:%DICE_PORT%/"
echo Server window is running. Close it to stop Dice Lab.
endlocal
