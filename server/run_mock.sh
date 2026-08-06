#!/usr/bin/env sh
# Personal Gateway Plus 模拟上游启动脚本（macOS / Linux）
# 零依赖，无需安装任何包。
cd "$(dirname "$0")"
exec python3 mock_upstream.py "$@"
