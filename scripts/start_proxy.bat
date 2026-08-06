@echo off
REM Start the Responses Bridge (Chat Completions <-> Responses API).
REM Double-click to run, or run:  python proxy.py
setlocal
where python >nul 2>nul
if %errorlevel%==0 (
  set "PY=python"
) else (
  set "PY=py"
)
"%PY%" "%~dp0proxy.py"
pause
