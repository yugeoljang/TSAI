"""API Key 加密 / 解密：AES-256-GCM。

主密钥来自环境变量 GATEWAY_MASTER_KEY（见 config.py）。
密文存储格式：nonce(12B) + ciphertext + tag(16B)，整体再 base64 编码为字符串存库。
明文 Key 永不返回到响应、日志或错误中。
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import settings

# 12 字节 nonce（GCM 推荐）
_NONCE_SIZE = 12


def _get_aesgcm() -> AESGCM:
    return AESGCM(settings.master_key_bytes)


def encrypt_api_key(plaintext: str) -> str:
    """加密明文 API Key，返回 base64 字符串。"""
    if not plaintext:
        raise ValueError("API Key 不能为空")
    nonce = os.urandom(_NONCE_SIZE)
    aesgcm = _get_aesgcm()
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_api_key(encrypted: str) -> str:
    """解密 API Key，返回明文。仅在真正转发上游时调用。"""
    raw = base64.b64decode(encrypted)
    nonce, ciphertext = raw[:_NONCE_SIZE], raw[_NONCE_SIZE:]
    aesgcm = _get_aesgcm()
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


def last_four(plaintext: str) -> str:
    """返回明文 Key 后四位，用于界面脱敏展示。"""
    return plaintext[-4:] if len(plaintext) >= 4 else plaintext


def mask_for_log(value: str | None) -> str:
    """日志脱敏：Key 只显示前两位和后两位。"""
    if not value:
        return "<empty>"
    if len(value) <= 8:
        return "<redacted>"
    return f"{value[:2]}***{value[-2:]}"
