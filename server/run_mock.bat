@echo off
REM Personal Gateway Plus 模拟上游启动脚本（Windows）
REM 零依赖，无需安装任何包。双击即可运行。
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" mock_upstream.py %*
) else if exist "..\.tools\python312\python.exe" (
    "..\.tools\python312\python.exe" mock_upstream.py %*
) else (
    python mock_upstream.py %*
)
pause
