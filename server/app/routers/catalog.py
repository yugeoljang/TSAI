"""模型 / 价格 / 活动查询（前缀 /api/admin)。

对应 openapi.yaml:
  - GET /api/admin/models        模型目录列表（可按 providerId 过滤）
  - GET /api/admin/prices        价格快照列表（可按 providerId 过滤）
  - GET /api/admin/promotions    活动列表（可按 providerId、activeOnly 过滤）

实现要点：
  - models/prices 查询返回对应 DTO,价格缺失为 NULL
  - promotions 的 active 字段：根据当前时间是否在 [starts_at, ends_at] 区间内
    且 status='verified' 来推导;activeOnly=true 时只返回有效活动
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query

from ..database import get_db
from ..schemas import ModelCatalogEntry, PriceSnapshot, Promotion

router = APIRouter(prefix="/api/admin", tags=["catalog"])


def _parse_iso(value: str | None) -> datetime | None:
    """宽松解析 ISO8601 字符串为 UTC datetime;失败返回 None。"""
    if not value:
        return None
    try:
        # 兼容带 Z 和不带 Z 的格式
        cleaned = value.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        return None


@router.get("/models", response_model=list[ModelCatalogEntry])
async def list_models(
    providerId: str | None = Query(default=None),
) -> list[ModelCatalogEntry]:
    """模型目录列表，可按 providerId 过滤。仅返回 enabled=1 的记录。"""
    db = await get_db()
    sql = (
        "SELECT id, provider_id, upstream_model_id, display_name, "
        "       context_window, enabled, source_url, verified_at "
        "FROM model_catalog_entry WHERE enabled = 1"
    )
    params: tuple = ()
    if providerId:
        sql += " AND provider_id = ?"
        params = (providerId,)
    sql += " ORDER BY provider_id, id"

    cur = await db.execute(sql, params)
    rows = await cur.fetchall()
    return [
        ModelCatalogEntry(
            id=r["id"],
            providerId=r["provider_id"],
            upstreamModelId=r["upstream_model_id"],
            displayName=r["display_name"],
            contextWindow=r["context_window"],
            enabled=bool(r["enabled"]),
            sourceUrl=r["source_url"],
            verifiedAt=r["verified_at"],
        )
        for r in rows
    ]


@router.get("/prices", response_model=list[PriceSnapshot])
async def list_prices(
    providerId: str | None = Query(default=None),
) -> list[PriceSnapshot]:
    """价格快照列表，可按 providerId 过滤。仅返回 is_current=1 的当前价格。"""
    db = await get_db()
    sql = (
        "SELECT id, provider_id, model_catalog_entry_id, currency, "
        "       input_price_per_million_tokens, output_price_per_million_tokens, "
        "       source_url, effective_from, verified_at "
        "FROM price_snapshot WHERE is_current = 1"
    )
    params: tuple = ()
    if providerId:
        sql += " AND provider_id = ?"
        params = (providerId,)
    sql += " ORDER BY provider_id, model_catalog_entry_id"

    cur = await db.execute(sql, params)
    rows = await cur.fetchall()
    return [
        PriceSnapshot(
            id=r["id"],
            providerId=r["provider_id"],
            modelCatalogEntryId=r["model_catalog_entry_id"],
            currency=r["currency"],
            inputPricePerMillionTokens=r["input_price_per_million_tokens"],
            outputPricePerMillionTokens=r["output_price_per_million_tokens"],
            sourceUrl=r["source_url"],
            effectiveFrom=r["effective_from"],
            verifiedAt=r["verified_at"],
        )
        for r in rows
    ]


@router.get("/promotions", response_model=list[Promotion])
async def list_promotions(
    providerId: str | None = Query(default=None),
    activeOnly: bool = Query(default=False),
) -> list[Promotion]:
    """活动列表，可按 providerId、activeOnly 过滤。

    active 字段推导:status='verified' 且当前 UTC 时间在 [starts_at, ends_at] 区间内。
    activeOnly=true 时只返回 active=True 的活动。
    """
    db = await get_db()
    sql = (
        "SELECT id, provider_id, title, type, description, source_url, "
        "       starts_at, ends_at, status, verified_at "
        "FROM promotion"
    )
    params: list[str] = []
    where_parts: list[str] = []
    if providerId:
        where_parts.append("provider_id = ?")
        params.append(providerId)
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    sql += " ORDER BY created_at DESC, id"

    cur = await db.execute(sql, params)
    rows = await cur.fetchall()

    now = datetime.now(timezone.utc)
    results: list[Promotion] = []
    for r in rows:
        starts = _parse_iso(r["starts_at"])
        ends = _parse_iso(r["ends_at"])
        # active 推导：status=verified 且当前时间在有效期内
        is_active = r["status"] == "verified"
        if is_active and starts is not None and now < starts:
            is_active = False
        if is_active and ends is not None and now > ends:
            is_active = False
        if activeOnly and not is_active:
            continue
        results.append(
            Promotion(
                id=r["id"],
                providerId=r["provider_id"],
                title=r["title"],
                type=r["type"],
                description=r["description"],
                sourceUrl=r["source_url"],
                startsAt=r["starts_at"],
                endsAt=r["ends_at"],
                active=is_active,
                verifiedAt=r["verified_at"],
            )
        )
    return results
