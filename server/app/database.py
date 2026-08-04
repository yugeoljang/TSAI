"""SQLite 异步连接与初始化。

启动时自动建表（schema.sql）并写入种子数据（如为空库）。
所有路由通过 get_db() 获取连接。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from .config import BASE_DIR, settings

SCHEMA_PATH = BASE_DIR / "app" / "schema.sql"

# 全局连接（uvicorn 单 worker 本地运行足够；如需多进程可改为每请求连接）
_db: aiosqlite.Connection | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def get_db() -> aiosqlite.Connection:
    """FastAPI 依赖注入用。返回共享连接。"""
    global _db
    if _db is None:
        await init_db()
    assert _db is not None
    return _db


async def init_db() -> None:
    """建表并（首次）写入种子数据。"""
    global _db
    settings.db_file.parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(str(settings.db_file))
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA foreign_keys = ON")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    await _db.executescript(schema_sql)
    await _db.commit()

    await _seed_if_empty(_db)


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


# ============================================================
# 种子数据：3 供应商 / 8+ 模型 / 3 活动（演示用，全部含来源）
# ============================================================
async def _seed_if_empty(db: aiosqlite.Connection) -> None:
    cur = await db.execute("SELECT COUNT(*) FROM provider")
    count = (await cur.fetchone())[0]
    if count > 0:
        return

    now = _now_iso()
    providers = [
        ("deepseek", "DeepSeek", "OPENAI_COMPATIBLE",
         "https://www.deepseek.com", "https://api-docs.deepseek.com/quick_start/pricing/", 1, now, now),
        ("siliconflow", "SiliconFlow", "OPENAI_COMPATIBLE",
         "https://siliconflow.cn", "https://docs.siliconflow.cn/cn/userguide/quickstart", 1, now, now),
        ("openai", "OpenAI", "OPENAI_COMPATIBLE",
         "https://openai.com", "https://openai.com/api/pricing/", 1, now, now),
    ]
    await db.executemany(
        "INSERT INTO provider(id,name,protocol_type,official_url,pricing_url,enabled,created_at,updated_at)"
        " VALUES(?,?,?,?,?,?,?,?)",
        providers,
    )

    # 模型目录（upstream_model_id 为供应商真实模型名）
    models = [
        # DeepSeek
        ("deepseek-chat", "deepseek", "deepseek-chat", "DeepSeek Chat", 64000,
         "https://api-docs.deepseek.com/quick_start/pricing/", "2026-07-29"),
        ("deepseek-reasoner", "deepseek", "deepseek-reasoner", "DeepSeek Reasoner", 64000,
         "https://api-docs.deepseek.com/quick_start/pricing/", "2026-07-29"),
        # SiliconFlow
        ("sf-qwen-72b", "siliconflow", "Qwen/Qwen2.5-72B-Instruct", "Qwen2.5-72B-Instruct", 131072,
         "https://docs.siliconflow.cn/cn/userguide/quickstart", "2026-07-29"),
        ("sf-deepseek-v3", "siliconflow", "deepseek-ai/DeepSeek-V3", "DeepSeek-V3 (SF)", 64000,
         "https://docs.siliconflow.cn/cn/userguide/quickstart", "2026-07-29"),
        # OpenAI
        ("openai-gpt-4o", "openai", "gpt-4o", "GPT-4o", 128000,
         "https://openai.com/api/pricing/", "2026-07-29"),
        ("openai-gpt-4o-mini", "openai", "gpt-4o-mini", "GPT-4o mini", 128000,
         "https://openai.com/api/pricing/", "2026-07-29"),
        ("openai-gpt-4.1", "openai", "gpt-4.1", "GPT-4.1", 1047576,
         "https://openai.com/api/pricing/", "2026-07-29"),
        ("openai-gpt-4.1-mini", "openai", "gpt-4.1-mini", "GPT-4.1 mini", 1047576,
         "https://openai.com/api/pricing/", "2026-07-29"),
    ]
    await db.executemany(
        "INSERT INTO model_catalog_entry(id,provider_id,upstream_model_id,display_name,context_window,"
        "capabilities,enabled,source_url,verified_at) VALUES(?,?,?,?,?,?,1,?,?)",
        [(m[0], m[1], m[2], m[3], m[4], None, m[5], m[6]) for m in models],
    )

    # 价格快照（CNY，每百万 tokens；价格缺失为 NULL 不为 0）
    prices = [
        ("price-1", "deepseek", "deepseek-chat", "CNY", 1.0, 8.0,
         "https://api-docs.deepseek.com/quick_start/pricing/", "2026-07-29", "2026-07-29"),
        ("price-2", "deepseek", "deepseek-reasoner", "CNY", 4.0, 16.0,
         "https://api-docs.deepseek.com/quick_start/pricing/", "2026-07-29", "2026-07-29"),
        ("price-3", "siliconflow", "sf-qwen-72b", "CNY", 4.13, 4.13,
         "https://docs.siliconflow.cn/cn/userguide/quickstart", "2026-07-29", "2026-07-29"),
        ("price-4", "openai", "openai-gpt-4o", "USD", 2.5, 10.0,
         "https://openai.com/api/pricing/", "2026-07-29", "2026-07-29"),
        ("price-5", "openai", "openai-gpt-4o-mini", "USD", 0.15, 0.6,
         "https://openai.com/api/pricing/", "2026-07-29", "2026-07-29"),
        ("price-6", "openai", "openai-gpt-4.1", "USD", 2.0, 8.0,
         "https://openai.com/api/pricing/", "2026-07-29", "2026-07-29"),
        ("price-7", "openai", "openai-gpt-4.1-mini", "USD", 0.4, 1.6,
         "https://openai.com/api/pricing/", "2026-07-29", "2026-07-29"),
    ]
    await db.executemany(
        "INSERT INTO price_snapshot(id,provider_id,model_catalog_entry_id,currency,"
        "input_price_per_million_tokens,output_price_per_million_tokens,source_url,"
        "effective_from,verified_at,is_current) VALUES(?,?,?,?,?,?,?,?,?,1)",
        prices,
    )

    # 活动（3 条演示，含来源和有效期）
    promos = [
        ("promo-1", "deepseek", "DeepSeek 重磅升级", "price_change",
         "DeepSeek-V3 上线，输入价格大幅降低。",
         "https://api-docs.deepseek.com/quick_start/pricing/",
         "2026-07-01T00:00:00Z", "2026-12-31T23:59:59Z", "verified", "2026-07-29", now),
        ("promo-2", "siliconflow", "SiliconFlow 新用户赠送额度", "credit",
         "注册即送 14 元额度，可用于所有开源模型调用。",
         "https://docs.siliconflow.cn/cn/userguide/quickstart",
         "2026-06-01T00:00:00Z", "2026-09-30T23:59:59Z", "verified", "2026-07-29", now),
        ("promo-3", "openai", "GPT-4.1 系列发布", "price_change",
         "GPT-4.1 相比 GPT-4o 降价并提升上下文能力。",
         "https://openai.com/api/pricing/",
         "2026-04-01T00:00:00Z", "2026-05-01T00:00:00Z", "verified", "2026-07-29", now),
    ]
    await db.executemany(
        "INSERT INTO promotion(id,provider_id,title,type,description,source_url,starts_at,ends_at,"
        "status,verified_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        promos,
    )

    await db.commit()


async def check_db_health() -> bool:
    """健康检查：能否成功查询。"""
    try:
        db = await get_db()
        cur = await db.execute("SELECT 1")
        await cur.fetchone()
        return True
    except Exception:
        return False
