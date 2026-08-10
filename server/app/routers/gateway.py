"""OpenAI 兼容中转入口。

POST /v1/chat/completions
- model 字段填分组 routeKey
- 仅支持 stream=false（true 返回 400 stream_not_supported）
- 按分组成员优先级顺序尝试上游：连接失败/超时/429/5xx 切换，400/422 不切换
- 成功响应头返回 X-Upstream（最终上游名称）

"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..database import get_db
from ..errors import StreamNotSupportedError
from ..schemas import ChatCompletionRequest
from ..services.gateway_service import create_gateway_request, route_chat_completion, utc_now

router = APIRouter(tags=["gateway"])


@router.post("/v1/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
) -> JSONResponse:
    # 初版仅支持非流式
    if body.stream:
        raise StreamNotSupportedError()

    request_id = getattr(request.state, "request_id")
    db = await get_db()
    request_id = await create_gateway_request(db, request_id, body.model, utc_now())
    request.state.request_id = request_id
    result = await route_chat_completion(
        db,
        request_id=request_id,
        route_key=body.model,
        payload=body.model_dump(),
    )

    headers = {"X-Request-Id": request_id}
    if result.upstream_name:
        headers["X-Upstream"] = result.upstream_name
    return JSONResponse(
        status_code=result.status_code,
        content=result.body,
        headers=headers,
    )
