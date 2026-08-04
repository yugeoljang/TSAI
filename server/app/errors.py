"""统一错误格式与全局异常处理。

所有错误响应使用 ErrorEnvelope 结构：
    {"error": {"code", "type", "message", "requestId", "details"}}
错误类型 type 对应 openapi.yaml 中 ErrorEnvelope.type 枚举。
"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class GatewayError(Exception):
    """业务错误基类，携带 HTTP 状态码与错误类型。"""

    def __init__(
        self,
        status_code: int = 400,
        error_type: str = "validation_error",
        message: str = "",
        details: list[dict] | None = None,
    ) -> None:
        self.status_code = status_code
        self.error_type = error_type
        self.message = message
        self.details = details or []
        super().__init__(message)


class NotFoundError(GatewayError):
    def __init__(self, message: str = "资源不存在") -> None:
        super().__init__(404, "not_found", message)


class ConflictError(GatewayError):
    def __init__(self, message: str = "资源冲突") -> None:
        super().__init__(409, "conflict", message)


class AllUpstreamsFailedError(GatewayError):
    def __init__(self, message: str = "所有上游均不可用") -> None:
        super().__init__(502, "all_upstreams_failed", message)


class StreamNotSupportedError(GatewayError):
    def __init__(self, message: str = "当前版本不支持流式响应，请使用 stream=false") -> None:
        super().__init__(400, "stream_not_supported", message)


def _envelope(
    status_code: int,
    error_type: str,
    message: str,
    request_id: str | None,
    details: list[dict] | None = None,
) -> dict[str, Any]:
    err: dict[str, Any] = {
        "code": status_code,
        "type": error_type,
        "message": message,
    }
    if request_id:
        err["requestId"] = request_id
    if details:
        err["details"] = details
    return {"error": err}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


async def gateway_error_handler(request: Request, exc: GatewayError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(exc.status_code, exc.error_type, exc.message, _request_id(request), exc.details),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    error_type_map = {
        400: "validation_error",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(
            exc.status_code,
            error_type_map.get(exc.status_code, "internal_error"),
            str(exc.detail),
            _request_id(request),
        ),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_envelope(
            422,
            "validation_error",
            "请求参数校验失败",
            _request_id(request),
            [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()],
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # 不把异常细节暴露给客户端，避免泄露内部信息（含密钥）
    return JSONResponse(
        status_code=500,
        content=_envelope(
            500,
            "internal_error",
            "服务器内部错误",
            _request_id(request),
        ),
    )
