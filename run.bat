@echo off
REM ===================================================================
REM  Syringe Pump Automation - double-click launcher (Windows)
REM  First run sets up the environment. Every run after just opens it.
REM ===================================================================

cd /d "%~dp0"

REM -- First time: create the virtual environment if it isn't there --
if not exist ".venv\Scripts\pythonw.exe" (
    echo First-time setup, this takes a minute...
    py -3 -m venv .venv
    if errorlevel 1 python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install pyserial
)

REM -- Launch the UI with no console window --
start "" ".venv\Scripts\pythonw.exe" "UI\app.py"
