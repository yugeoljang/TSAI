"""模型 / 价格 / 活动查询（骨架，前缀 /api/admin）。

对应 openapi.yaml：
  - GET /api/admin/models        模型目录列表（可按 providerId 过滤）
  - GET /api/admin/prices        价格快照列表（可按 providerId 过滤）
  - GET /api/admin/promotions    活动列表（可按 providerId、activeOnly 过滤）

🚧 查询实现由 C 类任务完成。本骨架注册所有端点并返回 501 占位。
   注意：
   - models/prices 查询返回对应 DTO，价格缺失为 NULL
   - promotions 的 active 字段：根据当前时间是否在 [starts_at, ends_at] 区间内
     且 status='verified' 来推导；activeOnly=true 时只返回有效活动
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/admin", tags=["catalog"])


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


@router.get("/models")
async def list_models(
    request: Request,
    providerId: str | None = Query(default=None),
):
    # 🚧 C 任务：查 model_catalog_entry，按 providerId 可选过滤
    return _not_implemented(request, "模型目录列表")


@router.get("/prices")
async def list_prices(
    request: Request,
    providerId: str | None = Query(default=None),
):
    # 🚧 C 任务：查 price_snapshot，按 providerId 可选过滤
    return _not_implemented(request, "价格快照列表")


@router.get("/promotions")
async def list_promotions(
    request: Request,
    providerId: str | None = Query(default=None),
    activeOnly: bool = Query(default=False),
):
    # 🚧 C 任务：查 promotion 表
    #   active 推导：status='verified' 且当前时间在 [starts_at, ends_at] 区间内
    #   activeOnly=true 时只返回 active=True 的记录
    return _not_implemented(request, "活动列表")
