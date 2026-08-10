"""API 分组与成员管理（前缀 /api/admin）。

实现要点：
  - routeKey 全局唯一，重复返回 409 conflict
  - members.order 单事务内更新 priority_rank
  - 成员响应需联表 upstream_endpoint 返回 upstreamDisplayName
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from ..database import get_db
from ..errors import ConflictError, GatewayError, NotFoundError
from ..schemas import (
    ApiGroup,
    ApiGroupCreate,
    ApiGroupDetail,
    ApiGroupMember,
    ApiGroupMemberCreate,
    ApiGroupMemberUpdate,
    ApiGroupUpdate,
    ReorderRequest,
)

router = APIRouter(prefix="/api/admin", tags=["groups"])


# ============================================================
# 辅助函数
# ============================================================
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _group_row_to_dto(r) -> ApiGroup:
    return ApiGroup(
        id=r["id"],
        name=r["name"],
        routeKey=r["route_key"],
        routingPolicy=r["routing_policy"],
        maxAttempts=r["max_attempts"],
        enabled=bool(r["enabled"]),
        createdAt=r["created_at"],
        updatedAt=r["updated_at"],
    )


def _member_row_to_dto(r) -> ApiGroupMember:
    return ApiGroupMember(
        id=r["id"],
        groupId=r["group_id"],
        upstreamEndpointId=r["upstream_endpoint_id"],
        upstreamDisplayName=r["upstream_display_name"],
        upstreamModelName=r["upstream_model_name"],
        priorityRank=r["priority_rank"],
        enabled=bool(r["enabled"]),
    )


async def _check_group_exists(db, group_id: str) -> None:
    cur = await db.execute("SELECT 1 FROM api_group WHERE id=?", (group_id,))
    if (await cur.fetchone()) is None:
        raise NotFoundError(f"分组 {group_id} 不存在")


async def _check_upstream_exists(db, upstream_id: str) -> None:
    cur = await db.execute(
        "SELECT 1 FROM upstream_endpoint WHERE id=?", (upstream_id,)
    )
    if (await cur.fetchone()) is None:
        raise NotFoundError(f"上游 {upstream_id} 不存在")


async def _fetch_members(db, group_id: str) -> list[ApiGroupMember]:
    """联表 upstream_endpoint 取 upstreamDisplayName，按 priority_rank 升序。"""
    cur = await db.execute(
        "SELECT m.id, m.group_id, m.upstream_endpoint_id, "
        "       u.display_name AS upstream_display_name, "
        "       m.upstream_model_name, m.priority_rank, m.enabled "
        "FROM api_group_member m "
        "LEFT JOIN upstream_endpoint u ON u.id = m.upstream_endpoint_id "
        "WHERE m.group_id = ? "
        "ORDER BY m.priority_rank ASC, m.id ASC",
        (group_id,),
    )
    rows = await cur.fetchall()
    return [_member_row_to_dto(r) for r in rows]


# ============================================================
# 分组 CRUD
# ============================================================
@router.get("/groups", response_model=list[ApiGroup])
async def list_groups() -> list[ApiGroup]:
    db = await get_db()
    cur = await db.execute("SELECT * FROM api_group ORDER BY id")
    rows = await cur.fetchall()
    return [_group_row_to_dto(r) for r in rows]


@router.post("/groups", response_model=ApiGroup, status_code=201)
async def create_group(body: ApiGroupCreate) -> ApiGroup:
    db = await get_db()
    gid = uuid.uuid4().hex
    now = _now_iso()
    try:
        await db.execute(
            "INSERT INTO api_group(id,name,route_key,routing_policy,"
            "max_attempts,enabled,created_at,updated_at) "
            "VALUES(?,?,?,'ORDERED_FAILOVER',?,?,?,?)",
            (gid, body.name, body.routeKey,
             body.maxAttempts,
             1 if body.enabled else 0, now, now),
        )
        await db.commit()
    except Exception as exc:  # routeKey 唯一约束冲突等
        raise ConflictError(f"创建分组失败（routeKey 可能重复）：{exc}") from exc

    cur = await db.execute("SELECT * FROM api_group WHERE id=?", (gid,))
    row = await cur.fetchone()
    assert row is not None
    return _group_row_to_dto(row)


@router.get("/groups/{group_id}", response_model=ApiGroupDetail)
async def get_group(group_id: str) -> ApiGroupDetail:
    db = await get_db()
    cur = await db.execute("SELECT * FROM api_group WHERE id=?", (group_id,))
    row = await cur.fetchone()
    if row is None:
        raise NotFoundError(f"分组 {group_id} 不存在")
    group = _group_row_to_dto(row)
    members = await _fetch_members(db, group_id)
    return ApiGroupDetail(**group.model_dump(), members=members)


@router.patch("/groups/{group_id}", response_model=ApiGroup)
async def update_group(
    group_id: str, body: ApiGroupUpdate
) -> ApiGroup:
    db = await get_db()
    cur = await db.execute("SELECT * FROM api_group WHERE id=?", (group_id,))
    if (await cur.fetchone()) is None:
        raise NotFoundError(f"分组 {group_id} 不存在")

    fields: list[str] = []
    params: list = []
    if body.name is not None:
        fields.append("name = ?")
        params.append(body.name)
    if body.maxAttempts is not None:
        fields.append("max_attempts = ?")
        params.append(body.maxAttempts)
    if body.enabled is not None:
        fields.append("enabled = ?")
        params.append(1 if body.enabled else 0)

    if fields:
        fields.append("updated_at = ?")
        params.append(_now_iso())
        params.append(group_id)
        await db.execute(
            f"UPDATE api_group SET {', '.join(fields)} WHERE id=?",
            params,
        )
        await db.commit()

    cur = await db.execute("SELECT * FROM api_group WHERE id=?", (group_id,))
    row = await cur.fetchone()
    assert row is not None
    return _group_row_to_dto(row)


@router.delete("/groups/{group_id}", status_code=204, response_model=None)
async def delete_group(group_id: str) -> None:
    db = await get_db()
    cur = await db.execute("SELECT 1 FROM api_group WHERE id=?", (group_id,))
    if (await cur.fetchone()) is None:
        raise NotFoundError(f"分组 {group_id} 不存在")
    await db.execute("DELETE FROM api_group WHERE id=?", (group_id,))
    await db.commit()
    return None


# ============================================================
# 成员管理
# ============================================================
@router.post(
    "/groups/{group_id}/members",
    response_model=ApiGroupMember,
    status_code=201,
)
async def add_member(
    group_id: str, body: ApiGroupMemberCreate
) -> ApiGroupMember:
    db = await get_db()
    await _check_group_exists(db, group_id)
    await _check_upstream_exists(db, body.upstreamEndpointId)

    mid = uuid.uuid4().hex
    now = _now_iso()

    # priorityRank 不传则追加到末尾（当前最大值 + 1）
    if body.priorityRank is None:
        cur = await db.execute(
            "SELECT COALESCE(MAX(priority_rank), 0) FROM api_group_member "
            "WHERE group_id = ?",
            (group_id,),
        )
        max_rank = (await cur.fetchone())[0]
        rank = max_rank + 1
    else:
        rank = body.priorityRank

    try:
        await db.execute(
            "INSERT INTO api_group_member("
            "id,group_id,upstream_endpoint_id,upstream_model_name,"
            "priority_rank,enabled,created_at) VALUES(?,?,?,?,?,?,?)",
            (mid, group_id, body.upstreamEndpointId, body.upstreamModelName,
             rank, 1 if body.enabled else 0, now),
        )
        await db.commit()
    except Exception as exc:  # UNIQUE(group_id, priority_rank) 冲突等
        raise ConflictError(
            f"添加成员失败（优先级 {rank} 可能已被占用）：{exc}"
        ) from exc

    members = await _fetch_members(db, group_id)
    for m in members:
        if m.id == mid:
            return m
    raise GatewayError(500, "internal_error", "成员已插入但无法查回")


@router.put(
    "/groups/{group_id}/members/order",
    response_model=list[ApiGroupMember],
)
async def reorder_members(
    group_id: str, body: ReorderRequest
) -> list[ApiGroupMember]:
    """单事务内按 orderedMemberIds 重排 priority_rank（从 1 开始）。

    列表顺序即为新优先级顺序。不在列表中的成员保持原值不变。
    """
    db = await get_db()
    await _check_group_exists(db, group_id)

    if not body.orderedMemberIds:
        return await _fetch_members(db, group_id)

    # 单事务内批量更新，保证顺序一致性。
    # sqlite3 默认 isolation_level 下，首条 DML 自动开启隐式事务，
    # 中间不 commit 则全部在同一事务中，最后统一 commit，出错 rollback。
    try:
        for index, member_id in enumerate(body.orderedMemberIds, start=1):
            cur = await db.execute(
                "UPDATE api_group_member SET priority_rank = ? "
                "WHERE id = ? AND group_id = ?",
                (index, member_id, group_id),
            )
            if cur.rowcount == 0:
                raise NotFoundError(
                    f"成员 {member_id} 不属于分组 {group_id}"
                )
        await db.commit()
    except NotFoundError:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        raise GatewayError(
            500, "internal_error", f"重排序失败：{exc}"
        ) from exc

    return await _fetch_members(db, group_id)


@router.patch(
    "/groups/{group_id}/members/{member_id}",
    response_model=ApiGroupMember,
)
async def update_member(
    group_id: str,
    member_id: str,
    body: ApiGroupMemberUpdate,
) -> ApiGroupMember:
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM api_group_member WHERE id=? AND group_id=?",
        (member_id, group_id),
    )
    if (await cur.fetchone()) is None:
        raise NotFoundError(f"成员 {member_id} 不属于分组 {group_id}")

    fields: list[str] = []
    params: list = []
    if body.upstreamModelName is not None:
        fields.append("upstream_model_name = ?")
        params.append(body.upstreamModelName)
    if body.priorityRank is not None:
        fields.append("priority_rank = ?")
        params.append(body.priorityRank)
    if body.enabled is not None:
        fields.append("enabled = ?")
        params.append(1 if body.enabled else 0)

    if fields:
        params.append(member_id)
        params.append(group_id)
        try:
            await db.execute(
                f"UPDATE api_group_member SET {', '.join(fields)} "
                "WHERE id = ? AND group_id = ?",
                params,
            )
            await db.commit()
        except Exception as exc:  # UNIQUE(group_id, priority_rank)
            raise ConflictError(
                f"编辑成员失败（优先级可能已被占用）：{exc}"
            ) from exc

    members = await _fetch_members(db, group_id)
    for m in members:
        if m.id == member_id:
            return m
    raise NotFoundError(f"成员 {member_id} 不属于分组 {group_id}")


@router.delete(
    "/groups/{group_id}/members/{member_id}",
    status_code=204,
    response_model=None,
)
async def delete_member(group_id: str, member_id: str) -> None:
    db = await get_db()
    cur = await db.execute(
        "SELECT 1 FROM api_group_member WHERE id=? AND group_id=?",
        (member_id, group_id),
    )
    if (await cur.fetchone()) is None:
        raise NotFoundError(f"成员 {member_id} 不属于分组 {group_id}")
    await db.execute(
        "DELETE FROM api_group_member WHERE id=? AND group_id=?",
        (member_id, group_id),
    )
    await db.commit()
    return None
