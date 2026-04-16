@echo off
chcp 65001 >nul
cd /d %~dp0

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"

echo Starting Stock Analysis Web App...
echo.
echo Python : %PYTHON_EXE%
echo URL    : http://127.0.0.1:5001
echo.
echo Tip: install dependencies manually if this is the first run.
echo Example: pip install -r requirements.txt
echo.

%PYTHON_EXE% quick_start.py
pause
