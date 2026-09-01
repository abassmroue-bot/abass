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
    echo First run: creating a virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
pip install -q -e ".[dev]"

if not exist .env (
    copy .env.example .env >nul
    echo.
    echo Created .env from .env.example -- add your ANTHROPIC_API_KEY, then run this again.
    echo (Get one at https://console.anthropic.com)
    exit /b 1
)

set MODE=%1
if "%MODE%"=="" set MODE=text

if "%MODE%"=="text" (
    python -m trillion.main
) else if "%MODE%"=="voice" (
    python -m trillion.voice_main
) else if "%MODE%"=="heartbeat" (
    python -m trillion.heartbeat_main
) else (
    echo Usage: run.bat [text^|voice^|heartbeat]  ^(default: text^)
    exit /b 1
)
