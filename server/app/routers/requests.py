"""网关路由记录查询（骨架，前缀 /api/admin）。

对应 openapi.yaml：
  - GET /api/admin/requests                 最近网关请求列表（分页 limit）
  - GET /api/admin/requests/{requestId}     单个请求详情
  - GET /api/admin/requests/{requestId}/attempts  该请求的路由尝试链

数据由 B 任务（中转转发）在每次请求后写入 gateway_request + route_attempt。
本端点只读查询，供管理后台展示请求历史与故障切换轨迹。

🚧 查询实现由 C 类任务完成。本骨架注册所有端点并返回 501 占位。
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from ..errors import NotFoundError

router = APIRouter(prefix="/api/admin", tags=["requests"])


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


@router.get("/requests")
async def list_requests(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
):
    # 🚧 C 任务：查 gateway_request，按 started_at DESC，LIMIT limit
    return _not_implemented(request, "网关请求列表")


@router.get("/requests/{request_id}")
async def get_request(request: Request, request_id: str):
    # 🚧 C 任务：查 gateway_request 单条，不存在抛 NotFoundError
    return _not_implemented(request, "网关请求详情")


@router.get("/requests/{request_id}/attempts")
async def list_attempts(request: Request, request_id: str):
    # 🚧 C 任务：先确认 request_id 存在（否则 NotFoundError），
    #   再查 route_attempt 按 attempt_index 升序
    return _not_implemented(request, "路由尝试链")
