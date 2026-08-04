@echo off
REM Personal Gateway Plus 一键启动（Windows）
REM 首次运行会创建虚拟环境并安装依赖。
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [初始化] 创建虚拟环境...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败，请确认已安装 Python 3.12+。
        exit /b 1
    )
    echo [初始化] 安装依赖...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败。
        exit /b 1
    )
)

if not exist ".env" (
    echo [初始化] 未发现 .env，从 .env.example 复制...
    copy ".env.example" ".env" >nul
    echo [提示] 请编辑 .env 填入 GATEWAY_MASTER_KEY 后重新运行，或留空使用临时密钥调试。
)

echo [启动] Personal Gateway Plus 后端 ...
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
endlocal
