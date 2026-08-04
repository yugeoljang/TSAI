"""Android 兼容查询接口（无 /api/admin 前缀）。

字段名严格对齐现有 Kotlin data class，确保 E3（Android 接入）无需修改客户端 DTO：
- GET /providers              → AndroidProvider 列表
- GET /providers/{id}         → AndroidProvider 详情
- GET /providers/{id}/channels → AndroidChannel 列表
- GET /models?providerId=     → AndroidLlmModel 列表
- GET /news?providerId=&type= → AndroidPriceNews 列表

数据来自 database.py 写入的种子数据；后续 C 任务实现 CRUD 后数据源不变。
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..database import get_db
from ..errors import NotFoundError
from ..schemas import (
    AndroidChannel,
    AndroidLlmModel,
    AndroidPriceNews,
    AndroidProvider,
)

router = APIRouter(tags=["android-compat"])


def _build_channels(row) -> list[AndroidChannel]:
    """从 provider 行的 official_url / pricing_url 构造渠道列表。"""
    channels: list[AndroidChannel] = []
    pid = row["id"]
    official = row["official_url"]
    pricing = row["pricing_url"]
    if official:
        channels.append(
            AndroidChannel(
                id=f"{pid}-official",
                name="官网",
                type="website",
                link=official,
                description=None,
            )
        )
    if pricing:
        channels.append(
            AndroidChannel(
                id=f"{pid}-pricing",
                name="定价",
                type="pricing",
                link=pricing,
                description=None,
            )
        )
    return channels


def _to_provider(row) -> AndroidProvider:
    return AndroidProvider(
        id=row["id"],
        name=row["name"],
        logoUrl=None,
        websiteUrl=row["official_url"] or "",
        region="global",
        channels=_build_channels(row),
        apiBaseUrl=None,
        apiKey=None,  # 永不返回真实 Key
        chatModel=None,
        supportsOpenAiChat=row["protocol_type"] == "OPENAI_COMPATIBLE",
    )


@router.get("/providers", response_model=list[AndroidProvider])
async def list_providers() -> list[AndroidProvider]:
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM provider WHERE enabled=1 ORDER BY id"
    )
    rows = await cur.fetchall()
    return [_to_provider(r) for r in rows]


@router.get("/providers/{provider_id}", response_model=AndroidProvider)
async def get_provider(provider_id: str) -> AndroidProvider:
    db = await get_db()
    cur = await db.execute("SELECT * FROM provider WHERE id=?", (provider_id,))
    row = await cur.fetchone()
    if row is None:
        raise NotFoundError(f"供应商 {provider_id} 不存在")
    return _to_provider(row)


@router.get(
    "/providers/{provider_id}/channels", response_model=list[AndroidChannel]
)
async def get_provider_channels(provider_id: str) -> list[AndroidChannel]:
    db = await get_db()
    cur = await db.execute("SELECT * FROM provider WHERE id=?", (provider_id,))
    row = await cur.fetchone()
    if row is None:
        raise NotFoundError(f"供应商 {provider_id} 不存在")
    return _build_channels(row)


@router.get("/models", response_model=list[AndroidLlmModel])
async def list_models(
    providerId: str | None = Query(default=None),
) -> list[AndroidLlmModel]:
    """模型目录 + 当前价格（LEFT JOIN price_snapshot）。

    价格缺失为 NULL（不为 0），与 LlmModel 可空字段一致。
    """
    db = await get_db()
    sql = (
        "SELECT m.id, m.provider_id, m.display_name, m.context_window, "
        "       p.currency, p.input_price_per_million_tokens, "
        "       p.output_price_per_million_tokens, p.source_url AS price_source_url, "
        "       p.verified_at AS price_verified_at "
        "FROM model_catalog_entry m "
        "LEFT JOIN price_snapshot p "
        "  ON p.model_catalog_entry_id = m.id AND p.is_current = 1 "
        "WHERE m.enabled = 1 "
    )
    params: tuple = ()
    if providerId:
        sql += "AND m.provider_id = ? "
        params = (providerId,)
    sql += "ORDER BY m.provider_id, m.id"

    cur = await db.execute(sql, params)
    rows = await cur.fetchall()
    return [
        AndroidLlmModel(
            id=r["id"],
            providerId=r["provider_id"],
            name=r["display_name"],
            contextWindow=r["context_window"],
            inputPricePerMillionTokens=r["input_price_per_million_tokens"],
            outputPricePerMillionTokens=r["output_price_per_million_tokens"],
            currency=r["currency"] or "USD",
            tier="standard",
            priceSourceUrl=r["price_source_url"],
            updatedAt=r["price_verified_at"],
            priceNote=None,
        )
        for r in rows
    ]


@router.get("/news", response_model=list[AndroidPriceNews])
async def list_news(
    providerId: str | None = Query(default=None),
    type: str | None = Query(default=None),
) -> list[AndroidPriceNews]:
    """价格与优惠通知，字段对齐 PriceNews.kt。"""
    db = await get_db()
    clauses: list[str] = []
    params: list[str] = []
    if providerId:
        clauses.append("provider_id = ?")
        params.append(providerId)
    if type:
        clauses.append("type = ?")
        params.append(type)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    cur = await db.execute(
        f"SELECT id, provider_id, title, description, type, source_url, "
        f"starts_at, ends_at, created_at "
        f"FROM promotion {where} ORDER BY created_at DESC",
        params,
    )
    rows = await cur.fetchall()
    return [
        AndroidPriceNews(
            id=r["id"],
            providerId=r["provider_id"],
            title=r["title"],
            summary=r["description"],
            type=r["type"],
            link=r["source_url"],
            validFrom=r["starts_at"],
            validUntil=r["ends_at"],
            createdAt=r["created_at"],
        )
        for r in rows
    ]
