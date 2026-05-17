@echo off
set PYTHONUTF8=1
REM IndieGala Auto-Spin Bot Runner for Windows
REM Usage: Run this script from the project directory
REM   cd %USERPROFILE%\Projects\indiegala-auto-spin
REM   run.bat

REM Load environment variables from .env file if it exists
if exist .env (
    for /f "delims=" %%x in (.env) do (set "%%x")
)

if not exist "%~dp0venv\Scripts\activate.bat" (
    echo Setting up virtual environment...
    python -m venv "%~dp0venv"
    call "%~dp0venv\Scripts\activate.bat"
    pip install -r "%~dp0requirements.txt"
) else (
    call "%~dp0venv\Scripts\activate.bat"
)

python spin_wheel.py %*
