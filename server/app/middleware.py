"""请求 ID 中间件与日志脱敏。

- 每个请求生成唯一 request_id（优先使用客户端 X-Request-Id 头）。
- 注入到 request.state.request_id，供错误处理与路由记录使用。
- 在响应头返回 X-Request-Id。
- 日志脱敏：本中间件不记录请求体；上游 Authorization/Key 脱敏在 security.py 提供。
"""
from __future__ import annotations

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("gateway")

# 脱敏头名集合（小写）
_SENSITIVE_HEADERS = {"authorization", "x-api-key", "api-key", "cookie"}


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        request.state.request_id = request_id

        # 脱敏记录访问日志（不含请求体与敏感头）
        safe_headers = {
            k: "***" if k.lower() in _SENSITIVE_HEADERS else v
            for k, v in request.headers.items()
        }
        logger.info(
            "req_start id=%s method=%s path=%s headers=%s",
            request_id,
            request.method,
            request.url.path,
            safe_headers,
        )

        response: Response = await call_next(request)
        response_request_id = getattr(request.state, "request_id", request_id)
        response.headers["X-Request-Id"] = response_request_id
        logger.info("req_end id=%s status=%s", response_request_id, response.status_code)
        return response
