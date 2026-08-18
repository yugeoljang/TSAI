"""Web 模型目录、价格快照和活动管理接口。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter

from ..database import get_db
from ..errors import ConflictError, GatewayError, NotFoundError
from ..schemas import (
    ModelCatalogCreate,
    ModelCatalogEntry,
    ModelCatalogUpdate,
    PriceSnapshot,
    PriceSnapshotCreate,
    Promotion,
    PromotionCreate,
    PromotionUpdate,
)

router = APIRouter(prefix="/api/admin", tags=["catalog"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _require_iso(value: str | None, field_name: str) -> datetime:
    parsed = _parse_iso(value)
    if parsed is None:
        raise GatewayError(422, "validation_error", f"{field_name} 必须是有效的 ISO8601 日期时间")
    return parsed


def _validate_source_url(value: str | None, field_name: str = "sourceUrl") -> None:
    parsed = urlparse(value or "")
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise GatewayError(422, "validation_error", f"{field_name} 必须是有效的 HTTP(S) 来源地址")


async def _require_provider(db, provider_id: str) -> None:
    cur = await db.execute("SELECT 1 FROM provider WHERE id=?", (provider_id,))
    if await cur.fetchone() is None:
        raise NotFoundError(f"供应商 {provider_id} 不存在")


async def _require_model(db, model_id: str):
    cur = await db.execute("SELECT * FROM model_catalog_entry WHERE id=?", (model_id,))
    row = await cur.fetchone()
    if row is None:
        raise NotFoundError(f"模型 {model_id} 不存在")
    return row


def _model_dto(row) -> ModelCatalogEntry:
    return ModelCatalogEntry(
        id=row["id"], providerId=row["provider_id"], upstreamModelId=row["upstream_model_id"],
        displayName=row["display_name"], contextWindow=row["context_window"], enabled=bool(row["enabled"]),
        sourceUrl=row["source_url"], verifiedAt=row["verified_at"],
    )


def _price_dto(row) -> PriceSnapshot:
    return PriceSnapshot(
        id=row["id"], providerId=row["provider_id"], modelCatalogEntryId=row["model_catalog_entry_id"],
        currency=row["currency"], inputPricePerMillionTokens=row["input_price_per_million_tokens"],
        outputPricePerMillionTokens=row["output_price_per_million_tokens"], sourceUrl=row["source_url"],
        effectiveFrom=row["effective_from"], verifiedAt=row["verified_at"], isCurrent=bool(row["is_current"]),
    )


def _promotion_lifecycle(row, now: datetime | None = None) -> str:
    status = row["status"]
    if status == "draft":
        return "draft"
    if status == "expired":
        return "expired"
    current = now or datetime.now(timezone.utc)
    starts = _parse_iso(row["starts_at"])
    ends = _parse_iso(row["ends_at"])
    if starts is not None and current < starts:
        return "upcoming"
    if ends is not None and current > ends:
        return "expired"
    return "active"


def _promotion_dto(row, now: datetime | None = None) -> Promotion:
    lifecycle = _promotion_lifecycle(row, now)
    return Promotion(
        id=row["id"], providerId=row["provider_id"], title=row["title"], type=row["type"],
        description=row["description"], sourceUrl=row["source_url"], startsAt=row["starts_at"],
        endsAt=row["ends_at"], active=lifecycle == "active", status=row["status"],
        lifecycleStatus=lifecycle, verifiedAt=row["verified_at"],
    )


def _validate_promotion(values: dict) -> None:
    starts = _parse_iso(values.get("startsAt"))
    ends = _parse_iso(values.get("endsAt"))
    if values.get("startsAt") and starts is None:
        raise GatewayError(422, "validation_error", "startsAt 必须是有效的 ISO8601 日期时间")
    if values.get("endsAt") and ends is None:
        raise GatewayError(422, "validation_error", "endsAt 必须是有效的 ISO8601 日期时间")
    if starts is not None and ends is not None and starts >= ends:
        raise GatewayError(422, "validation_error", "活动结束时间必须晚于开始时间")
    if values.get("status") == "verified":
        for field, label in (("sourceUrl", "来源地址"), ("startsAt", "开始时间"),
                             ("endsAt", "结束时间"), ("verifiedAt", "核验时间")):
            if not values.get(field):
                raise GatewayError(422, "validation_error", f"已验证活动必须填写{label}")
        _validate_source_url(values.get("sourceUrl"))
        _require_iso(values.get("verifiedAt"), "verifiedAt")
    elif values.get("sourceUrl"):
        _validate_source_url(values.get("sourceUrl"))
    if values.get("verifiedAt"):
        _require_iso(values.get("verifiedAt"), "verifiedAt")


@router.get("/models", response_model=list[ModelCatalogEntry])
async def list_models(providerId: str | None = None, includeDisabled: bool = False,
                      keyword: str | None = None) -> list[ModelCatalogEntry]:
    db = await get_db()
    clauses: list[str] = []
    params: list = []
    if not includeDisabled:
        clauses.append("enabled = 1")
    if providerId:
        clauses.append("provider_id = ?")
        params.append(providerId)
    if keyword:
        clauses.append("(display_name LIKE ? OR upstream_model_id LIKE ?)")
        term = f"%{keyword.strip()}%"
        params.extend([term, term])
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    cur = await db.execute("SELECT * FROM model_catalog_entry" + where + " ORDER BY provider_id, display_name", params)
    return [_model_dto(row) for row in await cur.fetchall()]


@router.post("/models", response_model=ModelCatalogEntry, status_code=201)
async def create_model(body: ModelCatalogCreate) -> ModelCatalogEntry:
    _validate_source_url(body.sourceUrl)
    _require_iso(body.verifiedAt, "verifiedAt")
    db = await get_db()
    await _require_provider(db, body.providerId)
    model_id = uuid.uuid4().hex
    try:
        await db.execute(
            "INSERT INTO model_catalog_entry(id,provider_id,upstream_model_id,display_name,context_window,"
            "capabilities,enabled,source_url,verified_at) VALUES(?,?,?,?,?,NULL,?,?,?)",
            (model_id, body.providerId, body.upstreamModelId.strip(), body.displayName.strip(), body.contextWindow,
             1 if body.enabled else 0, body.sourceUrl, body.verifiedAt),
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise ConflictError("同一供应商下不能重复添加相同的上游模型 ID") from exc
    return _model_dto(await _require_model(db, model_id))


@router.patch("/models/{model_id}", response_model=ModelCatalogEntry)
async def update_model(model_id: str, body: ModelCatalogUpdate) -> ModelCatalogEntry:
    db = await get_db()
    await _require_model(db, model_id)
    fields: list[str] = []
    params: list = []
    for attr, column in (("upstreamModelId", "upstream_model_id"), ("displayName", "display_name"),
                         ("contextWindow", "context_window"), ("sourceUrl", "source_url"),
                         ("verifiedAt", "verified_at")):
        value = getattr(body, attr)
        if value is not None:
            if attr == "sourceUrl":
                _validate_source_url(value)
            if attr == "verifiedAt":
                _require_iso(value, "verifiedAt")
            fields.append(f"{column} = ?")
            params.append(value.strip() if isinstance(value, str) else value)
    if body.enabled is not None:
        fields.append("enabled = ?")
        params.append(1 if body.enabled else 0)
    if fields:
        params.append(model_id)
        try:
            await db.execute(f"UPDATE model_catalog_entry SET {', '.join(fields)} WHERE id=?", params)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            raise ConflictError("更新后会造成模型 ID 重复") from exc
    return _model_dto(await _require_model(db, model_id))


@router.delete("/models/{model_id}", status_code=204, response_model=None)
async def delete_model(model_id: str) -> None:
    db = await get_db()
    await _require_model(db, model_id)
    await db.execute("DELETE FROM model_catalog_entry WHERE id=?", (model_id,))
    await db.commit()


@router.get("/prices", response_model=list[PriceSnapshot])
async def list_prices(providerId: str | None = None, modelCatalogEntryId: str | None = None,
                      currentOnly: bool = True) -> list[PriceSnapshot]:
    db = await get_db()
    clauses: list[str] = []
    params: list = []
    if currentOnly:
        clauses.append("is_current = 1")
    if providerId:
        clauses.append("provider_id = ?")
        params.append(providerId)
    if modelCatalogEntryId:
        clauses.append("model_catalog_entry_id = ?")
        params.append(modelCatalogEntryId)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    cur = await db.execute(
        "SELECT * FROM price_snapshot" + where
        + " ORDER BY model_catalog_entry_id, is_current DESC, effective_from DESC, verified_at DESC, id DESC", params)
    return [_price_dto(row) for row in await cur.fetchall()]


@router.get("/prices/history/{model_id}", response_model=list[PriceSnapshot])
async def price_history(model_id: str) -> list[PriceSnapshot]:
    db = await get_db()
    await _require_model(db, model_id)
    return await list_prices(modelCatalogEntryId=model_id, currentOnly=False)


@router.post("/prices", response_model=PriceSnapshot, status_code=201)
async def create_price(body: PriceSnapshotCreate) -> PriceSnapshot:
    _validate_source_url(body.sourceUrl)
    _require_iso(body.effectiveFrom, "effectiveFrom")
    _require_iso(body.verifiedAt, "verifiedAt")
    db = await get_db()
    model = await _require_model(db, body.modelCatalogEntryId)
    price_id = uuid.uuid4().hex
    try:
        await db.execute("BEGIN IMMEDIATE")
        await db.execute("UPDATE price_snapshot SET is_current=0 WHERE model_catalog_entry_id=? AND is_current=1",
                         (body.modelCatalogEntryId,))
        await db.execute(
            "INSERT INTO price_snapshot(id,provider_id,model_catalog_entry_id,currency,"
            "input_price_per_million_tokens,output_price_per_million_tokens,source_url,effective_from,"
            "verified_at,is_current) VALUES(?,?,?,?,?,?,?,?,?,1)",
            (price_id, model["provider_id"], body.modelCatalogEntryId, body.currency.upper(),
             body.inputPricePerMillionTokens, body.outputPricePerMillionTokens, body.sourceUrl,
             body.effectiveFrom, body.verifiedAt),
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise ConflictError(f"新增价格快照失败：{exc}") from exc
    cur = await db.execute("SELECT * FROM price_snapshot WHERE id=?", (price_id,))
    return _price_dto(await cur.fetchone())


@router.delete("/prices/{price_id}", status_code=204, response_model=None)
async def delete_price(price_id: str) -> None:
    db = await get_db()
    cur = await db.execute("SELECT * FROM price_snapshot WHERE id=?", (price_id,))
    row = await cur.fetchone()
    if row is None:
        raise NotFoundError(f"价格快照 {price_id} 不存在")
    await db.execute("DELETE FROM price_snapshot WHERE id=?", (price_id,))
    if bool(row["is_current"]):
        cur = await db.execute(
            "SELECT id FROM price_snapshot WHERE model_catalog_entry_id=? "
            "ORDER BY effective_from DESC, verified_at DESC, id DESC LIMIT 1", (row["model_catalog_entry_id"],))
        previous = await cur.fetchone()
        if previous is not None:
            await db.execute("UPDATE price_snapshot SET is_current=1 WHERE id=?", (previous["id"],))
    await db.commit()


@router.get("/promotions", response_model=list[Promotion])
async def list_promotions(providerId: str | None = None, activeOnly: bool = False,
                          lifecycleStatus: str | None = None) -> list[Promotion]:
    db = await get_db()
    sql = "SELECT * FROM promotion"
    params: list[str] = []
    if providerId:
        sql += " WHERE provider_id = ?"
        params.append(providerId)
    sql += " ORDER BY created_at DESC, id"
    cur = await db.execute(sql, params)
    now = datetime.now(timezone.utc)
    results = [_promotion_dto(row, now) for row in await cur.fetchall()]
    if activeOnly:
        results = [item for item in results if item.active]
    if lifecycleStatus:
        if lifecycleStatus not in ("draft", "upcoming", "active", "expired"):
            raise GatewayError(422, "validation_error", "lifecycleStatus 无效")
        results = [item for item in results if item.lifecycleStatus == lifecycleStatus]
    return results


@router.post("/promotions", response_model=Promotion, status_code=201)
async def create_promotion(body: PromotionCreate) -> Promotion:
    values = body.model_dump()
    _validate_promotion(values)
    db = await get_db()
    await _require_provider(db, body.providerId)
    promotion_id = uuid.uuid4().hex
    await db.execute(
        "INSERT INTO promotion(id,provider_id,title,type,description,source_url,starts_at,ends_at,status,"
        "verified_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (promotion_id, body.providerId, body.title.strip(), body.type, body.description, body.sourceUrl,
         body.startsAt, body.endsAt, body.status, body.verifiedAt, _now_iso()),
    )
    await db.commit()
    cur = await db.execute("SELECT * FROM promotion WHERE id=?", (promotion_id,))
    return _promotion_dto(await cur.fetchone())


@router.patch("/promotions/{promotion_id}", response_model=Promotion)
async def update_promotion(promotion_id: str, body: PromotionUpdate) -> Promotion:
    db = await get_db()
    cur = await db.execute("SELECT * FROM promotion WHERE id=?", (promotion_id,))
    existing = await cur.fetchone()
    if existing is None:
        raise NotFoundError(f"活动 {promotion_id} 不存在")
    current = {"providerId": existing["provider_id"], "title": existing["title"], "type": existing["type"],
               "description": existing["description"], "sourceUrl": existing["source_url"],
               "startsAt": existing["starts_at"], "endsAt": existing["ends_at"],
               "status": existing["status"], "verifiedAt": existing["verified_at"]}
    patch = body.model_dump(exclude_unset=True)
    current.update(patch)
    _validate_promotion(current)
    if body.providerId is not None:
        await _require_provider(db, body.providerId)
    mapping = {"providerId": "provider_id", "title": "title", "type": "type", "description": "description",
               "sourceUrl": "source_url", "startsAt": "starts_at", "endsAt": "ends_at",
               "status": "status", "verifiedAt": "verified_at"}
    if patch:
        fields = [f"{mapping[key]} = ?" for key in patch]
        params = [patch[key] for key in patch] + [promotion_id]
        await db.execute(f"UPDATE promotion SET {', '.join(fields)} WHERE id=?", params)
        await db.commit()
    cur = await db.execute("SELECT * FROM promotion WHERE id=?", (promotion_id,))
    return _promotion_dto(await cur.fetchone())


@router.delete("/promotions/{promotion_id}", status_code=204, response_model=None)
async def delete_promotion(promotion_id: str) -> None:
    db = await get_db()
    cur = await db.execute("SELECT 1 FROM promotion WHERE id=?", (promotion_id,))
    if await cur.fetchone() is None:
        raise NotFoundError(f"活动 {promotion_id} 不存在")
    await db.execute("DELETE FROM promotion WHERE id=?", (promotion_id,))
    await db.commit()
