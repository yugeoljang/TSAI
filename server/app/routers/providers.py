"""供应商与上游 API 管理（前缀 /api/admin）。

实现要点：
  - 上游 API Key 写入时用 security.encrypt_api_key 加密，响应只返回 last_four
  - baseUrl 校验 HTTPS（localhost 演示除外）
  - 外键级联：删除 provider 自动清理关联的 upstream / model 等
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter

from ..database import get_db
from ..errors import ConflictError, GatewayError, NotFoundError
from ..schemas import (
    Provider,
    ProviderCreate,
    ProviderUpdate,
    UpstreamCreate,
    UpstreamEndpoint,
    UpstreamUpdate,
)
from ..security import encrypt_api_key, last_four

router = APIRouter(prefix="/api/admin", tags=["providers"])


# ============================================================
# 辅助函数
# ============================================================
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_https_url(url: str) -> None:
    """校验 baseUrl：必须 HTTPS；localhost / 127.0.0.1 允许 HTTP（演示用）。"""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    is_local = host in ("localhost", "127.0.0.1")
    if parsed.scheme == "https":
        return
    if parsed.scheme == "http" and is_local:
        return
    raise GatewayError(
        400,
        "validation_error",
        f"baseUrl 必须是有效的 HTTPS 地址（localhost 演示除外）：{url}",
    )


def _provider_row_to_dto(r) -> Provider:
    return Provider(
        id=r["id"],
        name=r["name"],
        protocolType=r["protocol_type"],
        officialUrl=r["official_url"],
        pricingUrl=r["pricing_url"],
        enabled=bool(r["enabled"]),
        createdAt=r["created_at"],
        updatedAt=r["updated_at"],
    )


def _upstream_row_to_dto(r) -> UpstreamEndpoint:
    """数据库行转 DTO；注意响应只含 apiKeyLastFour，绝不返回密文。"""
    return UpstreamEndpoint(
        id=r["id"],
        providerId=r["provider_id"],
        displayName=r["display_name"],
        baseUrl=r["base_url"],
        apiKeyLastFour=r["api_key_last_four"],
        defaultModel=r["default_model"],
        enabled=bool(r["enabled"]),
        timeoutMs=r["timeout_ms"],
        createdAt=r["created_at"],
        updatedAt=r["updated_at"],
    )


async def _check_provider_exists(db, provider_id: str) -> None:
    cur = await db.execute("SELECT 1 FROM provider WHERE id=?", (provider_id,))
    if (await cur.fetchone()) is None:
        raise NotFoundError(f"供应商 {provider_id} 不存在")


# ============================================================
# 供应商
# ============================================================
@router.get("/providers", response_model=list[Provider])
async def list_providers() -> list[Provider]:
    db = await get_db()
    cur = await db.execute("SELECT * FROM provider ORDER BY id")
    rows = await cur.fetchall()
    return [_provider_row_to_dto(r) for r in rows]


@router.post("/providers", response_model=Provider, status_code=201)
async def create_provider(body: ProviderCreate) -> Provider:
    db = await get_db()
    pid = uuid.uuid4().hex
    now = _now_iso()
    try:
        await db.execute(
            "INSERT INTO provider(id,name,protocol_type,official_url,pricing_url,"
            "enabled,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                pid,
                body.name,
                "OPENAI_COMPATIBLE",
                body.officialUrl,
                body.pricingUrl,
                1 if body.enabled else 0,
                now,
                now,
            ),
        )
        await db.commit()
    except Exception as exc:  # 唯一约束等
        raise ConflictError(f"新增供应商失败：{exc}") from exc

    cur = await db.execute("SELECT * FROM provider WHERE id=?", (pid,))
    row = await cur.fetchone()
    assert row is not None
    return _provider_row_to_dto(row)


@router.get("/providers/{provider_id}", response_model=Provider)
async def get_provider(provider_id: str) -> Provider:
    db = await get_db()
    cur = await db.execute("SELECT * FROM provider WHERE id=?", (provider_id,))
    row = await cur.fetchone()
    if row is None:
        raise NotFoundError(f"供应商 {provider_id} 不存在")
    return _provider_row_to_dto(row)


@router.patch("/providers/{provider_id}", response_model=Provider)
async def update_provider(
    provider_id: str, body: ProviderUpdate
) -> Provider:
    db = await get_db()
    cur = await db.execute("SELECT * FROM provider WHERE id=?", (provider_id,))
    if (await cur.fetchone()) is None:
        raise NotFoundError(f"供应商 {provider_id} 不存在")

    fields: list[str] = []
    params: list = []
    if body.name is not None:
        fields.append("name = ?")
        params.append(body.name)
    if body.officialUrl is not None:
        fields.append("official_url = ?")
        params.append(body.officialUrl)
    if body.pricingUrl is not None:
        fields.append("pricing_url = ?")
        params.append(body.pricingUrl)
    if body.enabled is not None:
        fields.append("enabled = ?")
        params.append(1 if body.enabled else 0)

    if fields:
        fields.append("updated_at = ?")
        params.append(_now_iso())
        params.append(provider_id)
        await db.execute(
            f"UPDATE provider SET {', '.join(fields)} WHERE id=?",
            params,
        )
        await db.commit()

    cur = await db.execute("SELECT * FROM provider WHERE id=?", (provider_id,))
    row = await cur.fetchone()
    assert row is not None
    return _provider_row_to_dto(row)


@router.delete("/providers/{provider_id}", status_code=204, response_model=None)
async def delete_provider(provider_id: str) -> None:
    db = await get_db()
    cur = await db.execute("SELECT 1 FROM provider WHERE id=?", (provider_id,))
    if (await cur.fetchone()) is None:
        raise NotFoundError(f"供应商 {provider_id} 不存在")
    await db.execute("DELETE FROM provider WHERE id=?", (provider_id,))
    await db.commit()
    return None


# ============================================================
# 上游 API
# ============================================================
@router.get("/upstreams", response_model=list[UpstreamEndpoint])
async def list_upstreams() -> list[UpstreamEndpoint]:
    db = await get_db()
    cur = await db.execute("SELECT * FROM upstream_endpoint ORDER BY id")
    rows = await cur.fetchall()
    return [_upstream_row_to_dto(r) for r in rows]


@router.post("/upstreams", response_model=UpstreamEndpoint, status_code=201)
async def create_upstream(body: UpstreamCreate) -> UpstreamEndpoint:
    _validate_https_url(body.baseUrl)
    db = await get_db()
    await _check_provider_exists(db, body.providerId)

    uid = uuid.uuid4().hex
    now = _now_iso()
    encrypted = encrypt_api_key(body.apiKey)
    last4 = last_four(body.apiKey)
    try:
        await db.execute(
            "INSERT INTO upstream_endpoint("
            "id,provider_id,display_name,base_url,encrypted_api_key,"
            "api_key_last_four,default_model,enabled,timeout_ms,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                uid,
                body.providerId,
                body.displayName,
                body.baseUrl,
                encrypted,
                last4,
                body.defaultModel,
                1 if body.enabled else 0,
                body.timeoutMs,
                now,
                now,
            ),
        )
        await db.commit()
    except NotFoundError:
        raise
    except Exception as exc:
        raise ConflictError(f"新增上游失败：{exc}") from exc

    cur = await db.execute("SELECT * FROM upstream_endpoint WHERE id=?", (uid,))
    row = await cur.fetchone()
    assert row is not None
    return _upstream_row_to_dto(row)


@router.get("/upstreams/{upstream_id}", response_model=UpstreamEndpoint)
async def get_upstream(upstream_id: str) -> UpstreamEndpoint:
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM upstream_endpoint WHERE id=?", (upstream_id,)
    )
    row = await cur.fetchone()
    if row is None:
        raise NotFoundError(f"上游 {upstream_id} 不存在")
    return _upstream_row_to_dto(row)


@router.patch("/upstreams/{upstream_id}", response_model=UpstreamEndpoint)
async def update_upstream(
    upstream_id: str, body: UpstreamUpdate
) -> UpstreamEndpoint:
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM upstream_endpoint WHERE id=?", (upstream_id,)
    )
    if (await cur.fetchone()) is None:
        raise NotFoundError(f"上游 {upstream_id} 不存在")

    fields: list[str] = []
    params: list = []
    if body.displayName is not None:
        fields.append("display_name = ?")
        params.append(body.displayName)
    if body.baseUrl is not None:
        _validate_https_url(body.baseUrl)
        fields.append("base_url = ?")
        params.append(body.baseUrl)
    if body.apiKey is not None and body.apiKey.strip():
        # 仅当传入非空 apiKey 时才加密更新，否则保持原值
        fields.append("encrypted_api_key = ?")
        params.append(encrypt_api_key(body.apiKey))
        fields.append("api_key_last_four = ?")
        params.append(last_four(body.apiKey))
    if body.defaultModel is not None:
        fields.append("default_model = ?")
        params.append(body.defaultModel)
    if body.enabled is not None:
        fields.append("enabled = ?")
        params.append(1 if body.enabled else 0)
    if body.timeoutMs is not None:
        fields.append("timeout_ms = ?")
        params.append(body.timeoutMs)

    if fields:
        fields.append("updated_at = ?")
        params.append(_now_iso())
        params.append(upstream_id)
        await db.execute(
            f"UPDATE upstream_endpoint SET {', '.join(fields)} WHERE id=?",
            params,
        )
        await db.commit()

    cur = await db.execute(
        "SELECT * FROM upstream_endpoint WHERE id=?", (upstream_id,)
    )
    row = await cur.fetchone()
    assert row is not None
    return _upstream_row_to_dto(row)


@router.delete("/upstreams/{upstream_id}", status_code=204, response_model=None)
async def delete_upstream(upstream_id: str) -> None:
    db = await get_db()
    cur = await db.execute(
        "SELECT 1 FROM upstream_endpoint WHERE id=?", (upstream_id,)
    )
    if (await cur.fetchone()) is None:
        raise NotFoundError(f"上游 {upstream_id} 不存在")
    await db.execute("DELETE FROM upstream_endpoint WHERE id=?", (upstream_id,))
    await db.commit()
    return None
