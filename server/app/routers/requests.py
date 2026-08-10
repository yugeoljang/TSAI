"""网关请求记录和路由尝试链查询。"""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..database import get_db
from ..errors import NotFoundError
from ..schemas import GatewayRequest, RouteAttempt

router = APIRouter(prefix="/api/admin", tags=["requests"])


def _request_row_to_dto(row) -> GatewayRequest:
    return GatewayRequest(
        requestId=row["request_id"],
        routeKey=row["route_key"],
        startedAt=row["started_at"],
        endedAt=row["ended_at"],
        finalStatus=row["final_status"],
        finalUpstreamDisplayName=row["final_upstream_display"],
        attemptCount=row["attempt_count"],
    )


def _attempt_row_to_dto(row) -> RouteAttempt:
    return RouteAttempt(
        requestId=row["request_id"],
        attemptIndex=row["attempt_index"],
        upstreamEndpointId=row["upstream_endpoint_id"],
        upstreamDisplayName=row["upstream_display_name"],
        upstreamModelName=row["upstream_model_name"],
        startedAt=row["started_at"],
        endedAt=row["ended_at"],
        resultCategory=row["result_category"],
        upstreamStatusCode=row["upstream_status_code"],
        durationMs=row["duration_ms"],
        sanitizedError=row["sanitized_error"],
        retryable=bool(row["retryable"]),
    )


@router.get("/requests", response_model=list[GatewayRequest])
async def list_requests(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[GatewayRequest]:
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM gateway_request ORDER BY started_at DESC LIMIT ?",
        (limit,),
    )
    return [_request_row_to_dto(row) for row in await cur.fetchall()]


@router.get("/requests/{request_id}", response_model=GatewayRequest)
async def get_request(request_id: str) -> GatewayRequest:
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM gateway_request WHERE request_id=?",
        (request_id,),
    )
    row = await cur.fetchone()
    if row is None:
        raise NotFoundError(f"请求 {request_id} 不存在")
    return _request_row_to_dto(row)


@router.get(
    "/requests/{request_id}/attempts",
    response_model=list[RouteAttempt],
)
async def list_attempts(request_id: str) -> list[RouteAttempt]:
    db = await get_db()
    cur = await db.execute(
        "SELECT 1 FROM gateway_request WHERE request_id=?",
        (request_id,),
    )
    if await cur.fetchone() is None:
        raise NotFoundError(f"请求 {request_id} 不存在")

    cur = await db.execute(
        "SELECT * FROM route_attempt WHERE request_id=? "
        "ORDER BY attempt_index ASC, id ASC",
        (request_id,),
    )
    return [_attempt_row_to_dto(row) for row in await cur.fetchall()]
