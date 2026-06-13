@echo off
REM ===================================================================
REM  Syringe Pump Automation - double-click launcher (Windows)
REM  First run sets up the environment. Every run after just opens it.
REM ===================================================================

cd /d "%~dp0"

REM -- Pull the latest code. If it fails (offline, no git, local edits), --
REM -- just keep going and launch whatever version is already here.      --
REM -- Public repo: force the anonymous HTTPS URL so pull never prompts  --
REM -- for a password, and disable any credential prompt as a backstop.  --
where git >nul 2>&1 && (
    git remote set-url origin https://github.com/Ray-Research-Group/pump-automation.git
    set GIT_TERMINAL_PROMPT=0
    git -c credential.helper= pull origin prod
)

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
