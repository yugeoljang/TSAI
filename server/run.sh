#!/usr/bin/env bash
# Personal Gateway Plus 一键启动（macOS / Linux）
# 首次运行会创建虚拟环境并安装依赖。
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "[初始化] 创建虚拟环境..."
    python3 -m venv .venv
    echo "[初始化] 安装依赖..."
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
fi

if [ ! -f ".env" ]; then
    echo "[初始化] 未发现 .env，从 .env.example 复制..."
    cp .env.example .env
    echo "[提示] 请编辑 .env 填入 GATEWAY_MASTER_KEY 后重新运行，或留空使用临时密钥调试。"
fi

echo "[启动] Personal Gateway Plus 后端 ..."
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
