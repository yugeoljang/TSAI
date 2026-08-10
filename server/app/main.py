"""FastAPI 应用入口。

组装顺序：
1. lifespan：启动时 init_db()（建表+种子），关闭时 close_db()
2. 中间件：RequestIdMiddleware（注入/回传 request_id + 日志脱敏）
3. CORS：允许 settings.cors_origin_list
4. 异常处理：GatewayError / HTTPException / RequestValidationError / 兜底 Exception
5. 路由：health / android_compat / gateway / providers / groups / catalog / requests
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .database import close_db, init_db
from .errors import GatewayError, gateway_error_handler, http_exception_handler, unhandled_exception_handler, validation_exception_handler
from .middleware import RequestIdMiddleware
from .routers import android_compat, catalog, gateway, groups, health, providers, requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库，关闭时释放连接。"""
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="Personal Gateway Plus",
    version="0.1.0",
    description="个人 API 网关 —— 多供应商聚合、故障切换、价格追踪",
    lifespan=lifespan,
)

# --- 中间件（注册顺序：后注册的先执行，但 CORS 需最外层） ---
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id", "X-Upstream"],
)

# --- 异常处理 ---
app.add_exception_handler(GatewayError, gateway_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# --- 路由 ---
app.include_router(health.router)
app.include_router(android_compat.router)
app.include_router(gateway.router)
app.include_router(providers.router)
app.include_router(groups.router)
app.include_router(catalog.router)
app.include_router(requests.router)


@app.get("/", tags=["system"])
async def root() -> dict:
    """根路径，返回服务基本信息。"""
    return {"name": "Personal Gateway Plus", "version": "0.1.0", "docs": "/docs"}
