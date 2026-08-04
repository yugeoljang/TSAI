"""OpenAI 兼容中转入口（骨架）。

POST /v1/chat/completions
- model 字段填分组 routeKey
- 仅支持 stream=false（true 返回 400 stream_not_supported）
- 按分组成员优先级顺序尝试上游：连接失败/超时/429/5xx 切换，400/422 不切换
- 成功响应头返回 X-Upstream（最终上游名称）

🚧 路由转发逻辑由 B 类任务实现。本骨架注册端点并校验 stream=false，
   返回 501 占位以便联调，B 任务填充 httpx 调用与故障切换。
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..errors import StreamNotSupportedError
from ..schemas import ChatCompletionRequest

router = APIRouter(tags=["gateway"])


@router.post("/v1/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
) -> JSONResponse:
    # 初版仅支持非流式
    if body.stream:
        raise StreamNotSupportedError()

    # 🚧 B 任务：实现分组路由 + httpx 上游转发 + 故障切换
    # 流程：
    #   1. 按 body.model(routeKey) 查 api_group 及启用成员（priority_rank 升序）
    #   2. 逐个尝试上游：解密 apiKey -> POST {baseUrl}/v1/chat/completions
    #      - 连接失败/超时/429/5xx -> 记录 route_attempt，切换下一上游
    #      - 400/422 -> 不切换，直接返回（client_error）
    #      - 200 -> 记录 success，透传响应
    #   3. 全部失败 -> 抛 AllUpstreamsFailedError
    #   4. 响应头 X-Upstream 返回最终上游 displayName
    #   5. gateway_request + route_attempt 写库（供 requests 端点查询）
    return JSONResponse(
        status_code=501,
        content={
            "error": {
                "code": 501,
                "type": "internal_error",
                "message": "中转路由逻辑尚未实现（B 类任务），骨架已就绪",
                "requestId": getattr(request.state, "request_id", None),
            }
        },
        headers={"X-Request-Id": getattr(request.state, "request_id", "")},
    )
