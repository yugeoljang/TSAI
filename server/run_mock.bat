@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" mock_upstream.py %*
) else if exist "..\.tools\python312\python.exe" (
    "..\.tools\python312\python.exe" mock_upstream.py %*
) else (
    python mock_upstream.py %*
)

endlocal
