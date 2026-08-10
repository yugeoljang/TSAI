"""配置加载：统一从环境变量 / .env 读取，缺省值保证本地可立即启动。"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv

# server/ 目录即为 BASE_DIR
BASE_DIR = Path(__file__).resolve().parent.parent


def _load() -> None:
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        load_dotenv(env_file)


_load()


class Settings:
    """全局配置单例。初版单用户、本地运行，配置项保持精简。"""

    # --- API Key 加密主密钥 ---
    # 32 字节十六进制（64 字符）。留空时生成进程内随机密钥并警告（重启后无法解密旧数据）。
    master_key_hex: str = os.getenv("GATEWAY_MASTER_KEY", "").strip()

    # --- 服务监听 ---
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))

    # --- 数据库 ---
    database_path: str = os.getenv("DATABASE_PATH", "data/gateway.db")

    # --- 超时 ---
    request_total_timeout_seconds: int = int(
        os.getenv("REQUEST_TOTAL_TIMEOUT_SECONDS", "30")
    )
    upstream_timeout_seconds: int = int(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "15"))

    # --- CORS ---
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")

    def __init__(self) -> None:
        self._ephemeral_master_key: bytes | None = None
        self._master_key_warning_printed = False

    # --- 派生属性 ---
    @property
    def db_file(self) -> Path:
        return BASE_DIR / self.database_path

    @property
    def master_key_bytes(self) -> bytes:
        """返回 32 字节主密钥；缺失时生成临时密钥并打印警告。"""
        if self.master_key_hex:
            try:
                key = bytes.fromhex(self.master_key_hex)
                if len(key) == 32:
                    return key
            except ValueError:
                pass
        if self._ephemeral_master_key is None:
            self._ephemeral_master_key = secrets.token_bytes(32)
        if not self._master_key_warning_printed:
            reason = "格式无效" if self.master_key_hex else "未配置"
            print(
                f"[警告] GATEWAY_MASTER_KEY {reason}，使用本进程固定的临时密钥。"
                "重启后已加密的 API Key 将无法解密，仅供本地调试！",
                file=sys.stderr,
            )
            self._master_key_warning_printed = True
        return self._ephemeral_master_key

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
