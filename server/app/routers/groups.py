"""API 分组与成员管理（骨架，前缀 /api/admin）。

🚧 CRUD 实现由 C 类任务完成。本骨架注册所有端点并返回 501 占位。
   注意：
   - routeKey 全局唯一，重复返回 409 conflict
   - members.order 单事务内更新 priority_rank
   - 成员响应需联表 upstream_endpoint 返回 upstreamDisplayName
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..schemas import (
    ApiGroupCreate,
    ApiGroupMemberCreate,
    ApiGroupMemberUpdate,
    ApiGroupUpdate,
    ReorderRequest,
)

router = APIRouter(prefix="/api/admin", tags=["groups"])


def _not_implemented(request: Request, feature: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={
            "error": {
                "code": 501,
                "type": "internal_error",
                "message": f"{feature} 尚未实现（C 类任务），骨架已就绪",
                "requestId": getattr(request.state, "request_id", None),
            }
        },
    )


@router.get("/groups")
async def list_groups(request: Request):
    return _not_implemented(request, "分组列表")


@router.post("/groups", status_code=201)
async def create_group(request: Request, body: ApiGroupCreate):
    # 🚧 C 任务：routeKey 唯一约束冲突 -> ConflictError
    return _not_implemented(request, "创建分组")


@router.get("/groups/{group_id}")
async def get_group(request: Request, group_id: str):
    # 🚧 C 任务：返回 ApiGroupDetail（含 members）
    return _not_implemented(request, "分组详情")


@router.patch("/groups/{group_id}")
async def update_group(
    request: Request, group_id: str, body: ApiGroupUpdate
):
    return _not_implemented(request, "编辑分组")


@router.delete("/groups/{group_id}", status_code=204)
async def delete_group(request: Request, group_id: str):
    return _not_implemented(request, "删除分组")


@router.post("/groups/{group_id}/members", status_code=201)
async def add_member(
    request: Request, group_id: str, body: ApiGroupMemberCreate
):
    # 🚧 C 任务：priorityRank 不传则追加到末尾（max+1）
    return _not_implemented(request, "添加分组成员")


@router.put("/groups/{group_id}/members/order")
async def reorder_members(
    request: Request, group_id: str, body: ReorderRequest
):
    # 🚧 C 任务：单事务内按 orderedMemberIds 重排 priority_rank
    return _not_implemented(request, "调整成员顺序")


@router.patch("/groups/{group_id}/members/{member_id}")
async def update_member(
    request: Request,
    group_id: str,
    member_id: str,
    body: ApiGroupMemberUpdate,
):
    return _not_implemented(request, "编辑成员")


@router.delete("/groups/{group_id}/members/{member_id}", status_code=204)
async def delete_member(
    request: Request, group_id: str, member_id: str
):
    return _not_implemented(request, "移除成员")
