@echo off
REM IndieGala Auto-Spin Bot Runner for Windows

REM Load environment variables from .env file if it exists
if exist .env (
    for /f "delims=" %%x in (.env) do (set "%%x")
)

python spin_wheel.py %*
