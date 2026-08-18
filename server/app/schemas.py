"""Pydantic 请求 / 响应模型，严格对齐 contracts/openapi.yaml 的 schema 定义。

字段名、可空性、默认值均与 OpenAPI 契约一致；Android 兼容 DTO 字段名严格对齐
现有 Kotlin data class（ModelProvider.kt / LlmModel.kt / PriceNews.kt / Channel.kt）。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# ============================================================
# 统一错误
# ============================================================
class ErrorDetail(BaseModel):
    code: int
    type: str
    message: str
    requestId: str | None = None
    details: list[dict] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


# ============================================================
# 供应商
# ============================================================
class Provider(BaseModel):
    id: str
    name: str
    protocolType: str = "OPENAI_COMPATIBLE"
    officialUrl: str | None = None
    pricingUrl: str | None = None
    enabled: bool = True
    createdAt: str
    updatedAt: str


class ProviderCreate(BaseModel):
    name: str
    officialUrl: str | None = None
    pricingUrl: str | None = None
    enabled: bool = True


class ProviderUpdate(BaseModel):
    name: str | None = None
    officialUrl: str | None = None
    pricingUrl: str | None = None
    enabled: bool | None = None


# ============================================================
# 上游 API（API Key 加密保存，响应仅返回后四位）
# ============================================================
class UpstreamEndpoint(BaseModel):
    id: str
    providerId: str
    displayName: str
    baseUrl: str
    apiKeyLastFour: str
    defaultModel: str | None = None
    enabled: bool = True
    timeoutMs: int = 15000
    createdAt: str
    updatedAt: str


class UpstreamCreate(BaseModel):
    providerId: str
    displayName: str
    baseUrl: str
    apiKey: str = Field(description="写入时加密保存，永不回显")
    defaultModel: str | None = None
    enabled: bool = True
    timeoutMs: int = Field(default=15000, ge=100, le=120000)


class UpstreamUpdate(BaseModel):
    displayName: str | None = None
    baseUrl: str | None = None
    apiKey: str | None = Field(default=None, description="可选；不传则保持原 Key")
    defaultModel: str | None = None
    enabled: bool | None = None
    timeoutMs: int | None = Field(default=None, ge=100, le=120000)


# ============================================================
# 模型 / 价格 / 活动
# ============================================================
class ModelCatalogEntry(BaseModel):
    id: str
    providerId: str
    upstreamModelId: str
    displayName: str
    contextWindow: int | None = None
    enabled: bool = True
    sourceUrl: str | None = None
    verifiedAt: str | None = None


class ModelCatalogCreate(BaseModel):
    providerId: str = Field(min_length=1)
    upstreamModelId: str = Field(min_length=1)
    displayName: str = Field(min_length=1)
    contextWindow: int | None = Field(default=None, ge=1)
    enabled: bool = True
    sourceUrl: str = Field(min_length=1)
    verifiedAt: str = Field(min_length=1)


class ModelCatalogUpdate(BaseModel):
    upstreamModelId: str | None = Field(default=None, min_length=1)
    displayName: str | None = Field(default=None, min_length=1)
    contextWindow: int | None = Field(default=None, ge=1)
    enabled: bool | None = None
    sourceUrl: str | None = Field(default=None, min_length=1)
    verifiedAt: str | None = Field(default=None, min_length=1)


class PriceSnapshot(BaseModel):
    id: str
    providerId: str
    modelCatalogEntryId: str
    currency: str = "CNY"
    inputPricePerMillionTokens: float | None = None
    outputPricePerMillionTokens: float | None = None
    sourceUrl: str | None = None
    effectiveFrom: str | None = None
    verifiedAt: str | None = None
    isCurrent: bool = True


class PriceSnapshotCreate(BaseModel):
    modelCatalogEntryId: str = Field(min_length=1)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    inputPricePerMillionTokens: float | None = Field(default=None, ge=0)
    outputPricePerMillionTokens: float | None = Field(default=None, ge=0)
    sourceUrl: str = Field(min_length=1)
    effectiveFrom: str = Field(min_length=1)
    verifiedAt: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_at_least_one_price(self) -> "PriceSnapshotCreate":
        if (
            self.inputPricePerMillionTokens is None
            and self.outputPricePerMillionTokens is None
        ):
            raise ValueError("输入价和输出价至少填写一项")
        self.currency = self.currency.upper()
        return self


class Promotion(BaseModel):
    id: str
    providerId: str
    title: str
    type: str
    description: str | None = None
    sourceUrl: str | None = None
    startsAt: str | None = None
    endsAt: str | None = None
    active: bool = False
    status: Literal["draft", "verified", "expired"] = "draft"
    lifecycleStatus: Literal["draft", "upcoming", "active", "expired"] = "draft"
    verifiedAt: str | None = None


PromotionType = Literal["discount", "credit", "price_change"]
PromotionStatus = Literal["draft", "verified", "expired"]


class PromotionCreate(BaseModel):
    providerId: str = Field(min_length=1)
    title: str = Field(min_length=1)
    type: PromotionType
    description: str | None = None
    sourceUrl: str | None = None
    startsAt: str | None = None
    endsAt: str | None = None
    status: PromotionStatus = "draft"
    verifiedAt: str | None = None


class PromotionUpdate(BaseModel):
    providerId: str | None = Field(default=None, min_length=1)
    title: str | None = Field(default=None, min_length=1)
    type: PromotionType | None = None
    description: str | None = None
    sourceUrl: str | None = None
    startsAt: str | None = None
    endsAt: str | None = None
    status: PromotionStatus | None = None
    verifiedAt: str | None = None


# ============================================================
# API 分组与成员
# ============================================================
class ApiGroup(BaseModel):
    id: str
    name: str
    routeKey: str
    routingPolicy: str = "ORDERED_FAILOVER"
    maxAttempts: int = 3
    enabled: bool = True
    createdAt: str
    updatedAt: str


class ApiGroupMember(BaseModel):
    id: str
    groupId: str
    upstreamEndpointId: str
    upstreamDisplayName: str | None = None
    upstreamModelName: str
    priorityRank: int
    enabled: bool = True


class ApiGroupDetail(ApiGroup):
    members: list[ApiGroupMember] = Field(default_factory=list)


class ApiGroupCreate(BaseModel):
    name: str
    routeKey: str
    maxAttempts: int = Field(default=3, ge=1, le=10)
    enabled: bool = True


class ApiGroupUpdate(BaseModel):
    name: str | None = None
    maxAttempts: int | None = Field(default=None, ge=1, le=10)
    enabled: bool | None = None


class ApiGroupMemberCreate(BaseModel):
    upstreamEndpointId: str
    upstreamModelName: str
    priorityRank: int | None = Field(default=None, ge=1, description="不传则追加到末尾")
    enabled: bool = True


class ApiGroupMemberUpdate(BaseModel):
    upstreamModelName: str | None = None
    priorityRank: int | None = Field(default=None, ge=1)
    enabled: bool | None = None


class ReorderRequest(BaseModel):
    orderedMemberIds: list[str]


# ============================================================
# 路由记录
# ============================================================
class GatewayRequest(BaseModel):
    requestId: str
    routeKey: str
    startedAt: str
    endedAt: str | None = None
    finalStatus: str | None = None
    finalUpstreamDisplayName: str | None = None
    attemptCount: int = 0


class RouteAttempt(BaseModel):
    requestId: str
    attemptIndex: int
    upstreamEndpointId: str
    upstreamDisplayName: str | None = None
    upstreamModelName: str | None = None
    startedAt: str
    endedAt: str | None = None
    resultCategory: str
    upstreamStatusCode: int | None = None
    durationMs: int | None = None
    sanitizedError: str | None = None
    retryable: bool = False


# ============================================================
# OpenAI 兼容 Chat Completions
# ============================================================
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = Field(description="分组 routeKey")
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 1024
    stream: bool = False


class ChatChoiceMessage(ChatMessage):
    pass


class ChatChoice(BaseModel):
    index: int
    message: ChatChoiceMessage
    finish_reason: str | None = None


class ChatUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    choices: list[ChatChoice]
    usage: ChatUsage | None = None


# ============================================================
# Android 兼容 DTO（字段名严格对齐现有 Kotlin 类）
# ============================================================
class AndroidChannel(BaseModel):
    """对齐 Channel.kt"""
    id: str
    name: str
    type: str
    link: str
    description: str | None = None


class AndroidProvider(BaseModel):
    """对齐 ModelProvider.kt"""
    id: str
    name: str
    logoUrl: str | None = None
    websiteUrl: str
    region: str = "global"
    channels: list[AndroidChannel] = Field(default_factory=list)
    apiBaseUrl: str | None = None
    apiKey: str | None = None  # 后端永不返回真实 Key，恒为 null
    chatModel: str | None = None
    supportsOpenAiChat: bool = False


class AndroidLlmModel(BaseModel):
    """对齐 LlmModel.kt"""
    id: str
    providerId: str
    name: str
    contextWindow: int | None = None
    inputPricePerMillionTokens: float | None = None
    outputPricePerMillionTokens: float | None = None
    currency: str = "USD"
    tier: str = "standard"
    priceSourceUrl: str | None = None
    updatedAt: str | None = None
    priceNote: str | None = None


class AndroidPriceNews(BaseModel):
    """对齐 PriceNews.kt"""
    id: str
    providerId: str
    title: str
    summary: str | None = None
    type: str
    link: str | None = None
    validFrom: str | None = None
    validUntil: str | None = None
    createdAt: str


# ============================================================
# 系统
# ============================================================
class HealthStatus(BaseModel):
    status: str = "ok"
    database: str = "ok"
    version: str = "0.1.0"
