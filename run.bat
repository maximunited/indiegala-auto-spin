@echo off
REM IndieGala Auto-Spin Bot Runner for Windows
REM Usage: Run this script from the project directory
REM   cd %USERPROFILE%\Projects\indiegala-auto-spin
REM   run.bat

REM Load environment variables from .env file if it exists
if exist .env (
    for /f "delims=" %%x in (.env) do (set "%%x")
)

python spin_wheel.py %*
