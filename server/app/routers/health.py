"""健康检查端点。

GET /health 返回服务状态与数据库连通性，供启动验证与监控使用。
"""
from __future__ import annotations

from fastapi import APIRouter

from ..database import check_db_health
from ..schemas import HealthStatus

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    db_ok = await check_db_health()
    return HealthStatus(
        status="ok",
        database="ok" if db_ok else "error",
        version="0.1.0",
    )
