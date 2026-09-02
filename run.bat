@echo off
REM One-command launcher for Windows: sets up Trillion on first run, then starts it.
REM
REM Usage:
REM   run.bat            (text chat, default)
REM   run.bat voice      (push-to-talk voice)
REM   run.bat heartbeat  (the background proactive loop)
setlocal
cd /d "%~dp0"

if exist .venv goto :activate

echo Creating a virtual environment...
python -m venv .venv
if errorlevel 1 goto :venv_failed

:activate
echo Activating the virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 goto :activate_failed

echo Installing dependencies -- this can take a minute the first time...
pip install -e ".[dev]"
if errorlevel 1 goto :pip_failed

if exist .env goto :run

copy .env.example .env >nul
echo.
echo Created .env from .env.example -- add your ANTHROPIC_API_KEY, then run this again.
echo Get one at https://console.anthropic.com
pause
exit /b 1

:run
set MODE=%1
if "%MODE%"=="" set MODE=text

echo.
echo Starting Trillion in %MODE% mode...
echo.

if "%MODE%"=="text" goto :run_text
if "%MODE%"=="voice" goto :run_voice
if "%MODE%"=="heartbeat" goto :run_heartbeat

echo Usage: run.bat [text or voice or heartbeat]  (default: text)
pause
exit /b 1

:run_text
python -m trillion.main
goto :done

:run_voice
python -m trillion.voice_main
goto :done

:run_heartbeat
python -m trillion.heartbeat_main
goto :done

:venv_failed
echo.
echo FAILED to create the virtual environment. Is Python installed and on PATH?
pause
exit /b 1

:activate_failed
echo.
echo FAILED to activate the virtual environment. Try deleting the .venv folder and running this again.
pause
exit /b 1

:pip_failed
echo.
echo FAILED to install dependencies. See the error message above for why.
pause
exit /b 1

:done
echo.
echo Trillion has stopped.
pause
