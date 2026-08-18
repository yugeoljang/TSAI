/**
 * 全部 DTO 严格对齐 contracts/openapi.yaml。
 * 命名一律 camelCase，唯独 OpenAI 兼容字段是 snake_case（max_tokens 等），不要「顺手改成」驼峰。
 */

// ---------- 错误 ----------

export type ErrorType =
  | 'validation_error'
  | 'not_found'
  | 'conflict'
  | 'upstream_error'
  | 'all_upstreams_failed'
  | 'request_timeout'
  | 'stream_not_supported'
  | 'internal_error'

export interface ErrorEnvelope {
  error: {
    code: number
    type: ErrorType
    message: string
    requestId?: string
    details?: unknown[]
  }
}

// ---------- 供应商 / 上游 ----------

export interface Provider {
  id: string
  name: string
  protocolType: 'OPENAI_COMPATIBLE'
  officialUrl?: string | null
  pricingUrl?: string | null
  enabled: boolean
  createdAt: string
  updatedAt: string
}

export interface ProviderCreate {
  name: string
  officialUrl?: string | null
  pricingUrl?: string | null
  enabled?: boolean
}

export type ProviderUpdate = Partial<ProviderCreate>

export interface UpstreamEndpoint {
  id: string
  providerId: string
  displayName: string
  baseUrl: string
  /** 后端只回传后四位，明文 Key 永不出现在响应里 */
  apiKeyLastFour: string
  defaultModel?: string | null
  enabled: boolean
  timeoutMs: number
  createdAt: string
  updatedAt: string
}

export interface UpstreamCreate {
  providerId: string
  displayName: string
  baseUrl: string
  /** 新增时必填；写入即加密 */
  apiKey: string
  defaultModel?: string | null
  enabled?: boolean
  timeoutMs?: number
}

export interface UpstreamUpdate {
  displayName?: string
  baseUrl?: string
  /** 不传 = 保持原有 Key。切勿传空字符串。 */
  apiKey?: string
  defaultModel?: string | null
  enabled?: boolean
  timeoutMs?: number
}

// ---------- 模型 / 价格 / 活动 ----------

export interface ModelCatalogEntry {
  id: string
  providerId: string
  upstreamModelId: string
  displayName: string
  contextWindow?: number | null
  enabled: boolean
  sourceUrl?: string | null
  verifiedAt?: string | null
}

export interface ModelCatalogCreate {
  providerId: string
  upstreamModelId: string
  displayName: string
  contextWindow?: number | null
  enabled?: boolean
  sourceUrl: string
  verifiedAt: string
}

export type ModelCatalogUpdate = Partial<Omit<ModelCatalogCreate, 'providerId'>>

export interface PriceSnapshot {
  id: string
  providerId: string
  modelCatalogEntryId: string
  currency: string
  /** 可为 null —— 缺失时界面必须显示「—」，不得显示 0 */
  inputPricePerMillionTokens?: number | null
  outputPricePerMillionTokens?: number | null
  sourceUrl?: string | null
  effectiveFrom?: string | null
  verifiedAt?: string | null
  isCurrent: boolean
}

export interface PriceSnapshotCreate {
  modelCatalogEntryId: string
  currency: string
  inputPricePerMillionTokens?: number | null
  outputPricePerMillionTokens?: number | null
  sourceUrl: string
  effectiveFrom: string
  verifiedAt: string
}

export type PromotionType = 'discount' | 'credit' | 'price_change'
export type PromotionStatus = 'draft' | 'verified' | 'expired'
export type PromotionLifecycleStatus = 'draft' | 'upcoming' | 'active' | 'expired'

export interface Promotion {
  id: string
  providerId: string
  title: string
  type: PromotionType
  description?: string | null
  sourceUrl?: string | null
  startsAt?: string | null
  endsAt?: string | null
  /** 由后端按当前时间推导 */
  active: boolean
  status: PromotionStatus
  lifecycleStatus: PromotionLifecycleStatus
  verifiedAt?: string | null
}

export interface PromotionCreate {
  providerId: string
  title: string
  type: PromotionType
  description?: string | null
  sourceUrl?: string | null
  startsAt?: string | null
  endsAt?: string | null
  status?: PromotionStatus
  verifiedAt?: string | null
}

export type PromotionUpdate = Partial<PromotionCreate>

// ---------- 分组 ----------

export interface ApiGroup {
  id: string
  name: string
  /** 调用时填进 OpenAI 请求体 model 字段的值 */
  routeKey: string
  routingPolicy: 'ORDERED_FAILOVER'
  maxAttempts: number
  enabled: boolean
  createdAt: string
  updatedAt: string
}

export interface ApiGroupMember {
  id: string
  groupId: string
  upstreamEndpointId: string
  upstreamDisplayName?: string | null
  upstreamModelName: string
  /** 数字越小优先级越高 */
  priorityRank: number
  enabled: boolean
}

export interface ApiGroupDetail extends ApiGroup {
  members: ApiGroupMember[]
}

export interface ApiGroupCreate {
  name: string
  routeKey: string
  maxAttempts?: number
  enabled?: boolean
}

export interface ApiGroupUpdate {
  name?: string
  maxAttempts?: number
  enabled?: boolean
}

export interface ApiGroupMemberCreate {
  upstreamEndpointId: string
  upstreamModelName: string
  /** 不传则追加到末尾 */
  priorityRank?: number
  enabled?: boolean
}

export interface ApiGroupMemberUpdate {
  upstreamModelName?: string
  priorityRank?: number
  enabled?: boolean
}

export interface ReorderRequest {
  orderedMemberIds: string[]
}

// ---------- 路由记录 ----------

export type FinalStatus = 'success' | 'all_failed' | 'client_error' | 'timeout'

export type ResultCategory =
  | 'success'
  | 'network_error'
  | 'timeout'
  | 'rate_limited'
  | 'server_error'
  | 'auth_error'
  | 'client_error'

export interface GatewayRequest {
  requestId: string
  routeKey: string
  startedAt: string
  endedAt?: string | null
  finalStatus?: FinalStatus | null
  finalUpstreamDisplayName?: string | null
  attemptCount: number
}

export interface RouteAttempt {
  requestId: string
  attemptIndex: number
  upstreamEndpointId: string
  upstreamDisplayName?: string | null
  upstreamModelName?: string | null
  startedAt: string
  endedAt?: string | null
  resultCategory: ResultCategory
  upstreamStatusCode?: number | null
  durationMs?: number | null
  sanitizedError?: string | null
  retryable: boolean
}

// ---------- 网关调用（OpenAI 兼容，注意 snake_case） ----------

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export interface ChatCompletionRequest {
  /** 这里填分组的 routeKey，不是真实模型名 */
  model: string
  messages: ChatMessage[]
  temperature?: number
  max_tokens?: number
  /** 初版只接受 false */
  stream?: boolean
}

export interface ChatCompletionResponse {
  id: string
  object: string
  choices: Array<{
    index: number
    message: ChatMessage
    finish_reason: string
  }>
  usage?: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  }
}
