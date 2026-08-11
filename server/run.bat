@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE="
set "PYTHON_ARGS="

if exist "..\.tools\python312\python.exe" set "PYTHON_EXE=..\.tools\python312\python.exe"
if not defined PYTHON_EXE where py >nul 2>nul && set "PYTHON_EXE=py" && set "PYTHON_ARGS=-3"
if not defined PYTHON_EXE where python >nul 2>nul && set "PYTHON_EXE=python"

if not defined PYTHON_EXE (
    echo [ERROR] Python 3.12 or newer was not found.
    echo Install Python and enable "Add Python to PATH".
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [SETUP] Creating the virtual environment...
    "%PYTHON_EXE%" %PYTHON_ARGS% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        exit /b 1
    )

    echo [SETUP] Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        exit /b 1
    )
)

if not exist ".env" (
    echo [SETUP] Creating .env from .env.example...
    copy /y ".env.example" ".env" >nul
    echo [NOTICE] Set GATEWAY_MASTER_KEY in .env before saving real API keys.
)

echo [START] Personal Gateway Plus backend
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
endlocal
