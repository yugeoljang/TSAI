"""供应商与上游 API 管理（骨架，前缀 /api/admin）。

🚧 CRUD 实现由 C 类任务完成。本骨架注册所有端点并返回 501 占位，
   C 任务填充数据库读写逻辑。注意：
   - 上游 API Key 写入时用 security.encrypt_api_key 加密，响应只返回 last_four
   - baseUrl 校验 HTTPS（localhost 演示除外）
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..schemas import ProviderCreate, ProviderUpdate, UpstreamCreate, UpstreamUpdate

router = APIRouter(prefix="/api/admin", tags=["providers"])


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


# ============================================================
# 供应商
# ============================================================
@router.get("/providers")
async def list_providers(request: Request):
    # 🚧 C 任务：查 provider 表
    return _not_implemented(request, "供应商列表")


@router.post("/providers", status_code=201)
async def create_provider(request: Request, body: ProviderCreate):
    # 🚧 C 任务：INSERT provider
    return _not_implemented(request, "新增供应商")


@router.get("/providers/{provider_id}")
async def get_provider(request: Request, provider_id: str):
    return _not_implemented(request, "供应商详情")


@router.patch("/providers/{provider_id}")
async def update_provider(
    request: Request, provider_id: str, body: ProviderUpdate
):
    return _not_implemented(request, "编辑供应商")


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(request: Request, provider_id: str):
    return _not_implemented(request, "删除供应商")


# ============================================================
# 上游 API
# ============================================================
@router.get("/upstreams")
async def list_upstreams(request: Request):
    # 🚧 C 任务：查 upstream_endpoint，响应只含 apiKeyLastFour
    return _not_implemented(request, "上游列表")


@router.post("/upstreams", status_code=201)
async def create_upstream(request: Request, body: UpstreamCreate):
    # 🚧 C 任务：encrypt_api_key(body.apiKey) -> 存库
    return _not_implemented(request, "新增上游")


@router.get("/upstreams/{upstream_id}")
async def get_upstream(request: Request, upstream_id: str):
    return _not_implemented(request, "上游详情")


@router.patch("/upstreams/{upstream_id}")
async def update_upstream(
    request: Request, upstream_id: str, body: UpstreamUpdate
):
    # 🚧 C 任务：body.apiKey 非空时加密更新，否则保持
    return _not_implemented(request, "编辑上游")


@router.delete("/upstreams/{upstream_id}", status_code=204)
async def delete_upstream(request: Request, upstream_id: str):
    return _not_implemented(request, "删除上游")
