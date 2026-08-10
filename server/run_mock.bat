@echo off
REM Personal Gateway Plus 模拟上游启动脚本（Windows）
REM 零依赖，无需安装任何包。双击即可运行。
cd /d "%~dp0"
python mock_upstream.py %*
pause
