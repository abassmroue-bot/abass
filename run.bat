@echo off
REM One-command launcher for Windows: sets up Trillion on first run, then starts it.
REM
REM Usage:
REM   run.bat            (text chat, default)
REM   run.bat voice      (push-to-talk voice)
REM   run.bat heartbeat  (the background proactive loop)
setlocal
cd /d "%~dp0"

if not exist .venv (
    echo Creating a virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo FAILED to create the virtual environment. Is Python installed and on PATH?
        echo Try running "python --version" in this window to check.
        pause
        exit /b 1
    )
)

echo Activating the virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo.
    echo FAILED to activate the virtual environment. The .venv folder may be
    echo incomplete -- try deleting the .venv folder and running this again.
    pause
    exit /b 1
)

echo Installing dependencies -- this can take a minute the first time...
pip install -e ".[dev]"
if errorlevel 1 (
    echo.
    echo FAILED to install dependencies. See the error message above for why.
    pause
    exit /b 1
)

if not exist .env (
    copy .env.example .env >nul
    echo.
    echo Created .env from .env.example -- add your ANTHROPIC_API_KEY, then run this again.
    echo (Get one at https://console.anthropic.com)
    pause
    exit /b 1
)

set MODE=%1
if "%MODE%"=="" set MODE=text

echo.
echo Starting Trillion (%MODE% mode)...
echo.

if "%MODE%"=="text" (
    python -m trillion.main
) else if "%MODE%"=="voice" (
    python -m trillion.voice_main
) else if "%MODE%"=="heartbeat" (
    python -m trillion.heartbeat_main
) else (
    echo Usage: run.bat [text^|voice^|heartbeat]  ^(default: text^)
    pause
    exit /b 1
)

echo.
echo Trillion has stopped.
pause >nul
