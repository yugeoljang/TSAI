/**
 * Mock 内存数据库。
 *
 * 种子数据严格镜像 server/app/database.py 的 _seed_if_empty()，
 * 包括两处刻意保留的边界情况：
 *   - sf-deepseek-v3 没有价格记录 → 用来验证「价格缺失不显示成 0」
 *   - promo-3 已于 2026-05-01 结束   → 用来验证「有效 / 过期」区分
 *
 * 数据同时保存到 localStorage，便于在纯前端 Mock 模式下演示完整管理流程。
 */
import type {
  ApiGroup,
  ApiGroupMember,
  GatewayRequest,
  ModelCatalogEntry,
  PriceSnapshot,
  Promotion,
  Provider,
  RouteAttempt,
  UpstreamEndpoint,
} from '@/types/api'

const NOW = '2026-07-29T00:00:00Z'

export const providers: Provider[] = [
  {
    id: 'deepseek',
    name: 'DeepSeek',
    protocolType: 'OPENAI_COMPATIBLE',
    officialUrl: 'https://www.deepseek.com',
    pricingUrl: 'https://api-docs.deepseek.com/quick_start/pricing/',
    enabled: true,
    createdAt: NOW,
    updatedAt: NOW,
  },
  {
    id: 'siliconflow',
    name: 'SiliconFlow',
    protocolType: 'OPENAI_COMPATIBLE',
    officialUrl: 'https://siliconflow.cn',
    pricingUrl: 'https://docs.siliconflow.cn/cn/userguide/quickstart',
    enabled: true,
    createdAt: NOW,
    updatedAt: NOW,
  },
  {
    id: 'openai',
    name: 'OpenAI',
    protocolType: 'OPENAI_COMPATIBLE',
    officialUrl: 'https://openai.com',
    pricingUrl: 'https://openai.com/api/pricing/',
    enabled: true,
    createdAt: NOW,
    updatedAt: NOW,
  },
]

const DS_SRC = 'https://api-docs.deepseek.com/quick_start/pricing/'
const SF_SRC = 'https://docs.siliconflow.cn/cn/userguide/quickstart'
const OA_SRC = 'https://openai.com/api/pricing/'

export const models: ModelCatalogEntry[] = [
  { id: 'deepseek-chat', providerId: 'deepseek', upstreamModelId: 'deepseek-chat', displayName: 'DeepSeek Chat', contextWindow: 64000, enabled: true, sourceUrl: DS_SRC, verifiedAt: '2026-07-29' },
  { id: 'deepseek-reasoner', providerId: 'deepseek', upstreamModelId: 'deepseek-reasoner', displayName: 'DeepSeek Reasoner', contextWindow: 64000, enabled: true, sourceUrl: DS_SRC, verifiedAt: '2026-07-29' },
  { id: 'sf-qwen-72b', providerId: 'siliconflow', upstreamModelId: 'Qwen/Qwen2.5-72B-Instruct', displayName: 'Qwen2.5-72B-Instruct', contextWindow: 131072, enabled: true, sourceUrl: SF_SRC, verifiedAt: '2026-07-29' },
  { id: 'sf-deepseek-v3', providerId: 'siliconflow', upstreamModelId: 'deepseek-ai/DeepSeek-V3', displayName: 'DeepSeek-V3 (SF)', contextWindow: 64000, enabled: true, sourceUrl: SF_SRC, verifiedAt: '2026-07-29' },
  { id: 'openai-gpt-4o', providerId: 'openai', upstreamModelId: 'gpt-4o', displayName: 'GPT-4o', contextWindow: 128000, enabled: true, sourceUrl: OA_SRC, verifiedAt: '2026-07-29' },
  { id: 'openai-gpt-4o-mini', providerId: 'openai', upstreamModelId: 'gpt-4o-mini', displayName: 'GPT-4o mini', contextWindow: 128000, enabled: true, sourceUrl: OA_SRC, verifiedAt: '2026-07-29' },
  { id: 'openai-gpt-4.1', providerId: 'openai', upstreamModelId: 'gpt-4.1', displayName: 'GPT-4.1', contextWindow: 1047576, enabled: true, sourceUrl: OA_SRC, verifiedAt: '2026-07-29' },
  { id: 'openai-gpt-4.1-mini', providerId: 'openai', upstreamModelId: 'gpt-4.1-mini', displayName: 'GPT-4.1 mini', contextWindow: 1047576, enabled: true, sourceUrl: OA_SRC, verifiedAt: '2026-07-29' },
]

// 注意：故意没有 sf-deepseek-v3 的价格
export const prices: PriceSnapshot[] = [
  { id: 'price-1', providerId: 'deepseek', modelCatalogEntryId: 'deepseek-chat', currency: 'CNY', inputPricePerMillionTokens: 1.0, outputPricePerMillionTokens: 8.0, sourceUrl: DS_SRC, effectiveFrom: '2026-07-29', verifiedAt: '2026-07-29', isCurrent: true },
  { id: 'price-2', providerId: 'deepseek', modelCatalogEntryId: 'deepseek-reasoner', currency: 'CNY', inputPricePerMillionTokens: 4.0, outputPricePerMillionTokens: 16.0, sourceUrl: DS_SRC, effectiveFrom: '2026-07-29', verifiedAt: '2026-07-29', isCurrent: true },
  { id: 'price-3', providerId: 'siliconflow', modelCatalogEntryId: 'sf-qwen-72b', currency: 'CNY', inputPricePerMillionTokens: 4.13, outputPricePerMillionTokens: 4.13, sourceUrl: SF_SRC, effectiveFrom: '2026-07-29', verifiedAt: '2026-07-29', isCurrent: true },
  { id: 'price-4', providerId: 'openai', modelCatalogEntryId: 'openai-gpt-4o', currency: 'USD', inputPricePerMillionTokens: 2.5, outputPricePerMillionTokens: 10.0, sourceUrl: OA_SRC, effectiveFrom: '2026-07-29', verifiedAt: '2026-07-29', isCurrent: true },
  { id: 'price-5', providerId: 'openai', modelCatalogEntryId: 'openai-gpt-4o-mini', currency: 'USD', inputPricePerMillionTokens: 0.15, outputPricePerMillionTokens: 0.6, sourceUrl: OA_SRC, effectiveFrom: '2026-07-29', verifiedAt: '2026-07-29', isCurrent: true },
  { id: 'price-6', providerId: 'openai', modelCatalogEntryId: 'openai-gpt-4.1', currency: 'USD', inputPricePerMillionTokens: 2.0, outputPricePerMillionTokens: 8.0, sourceUrl: OA_SRC, effectiveFrom: '2026-07-29', verifiedAt: '2026-07-29', isCurrent: true },
  { id: 'price-7', providerId: 'openai', modelCatalogEntryId: 'openai-gpt-4.1-mini', currency: 'USD', inputPricePerMillionTokens: 0.4, outputPricePerMillionTokens: 1.6, sourceUrl: OA_SRC, effectiveFrom: '2026-07-29', verifiedAt: '2026-07-29', isCurrent: true },
]

// active 由 handlers.ts 按当前时间推导，这里存的是原始有效期
export const promotions: Omit<Promotion, 'active' | 'lifecycleStatus'>[] = [
  { id: 'promo-1', providerId: 'deepseek', title: 'DeepSeek 重磅升级', type: 'price_change', description: 'DeepSeek-V3 上线，输入价格大幅降低。', sourceUrl: DS_SRC, startsAt: '2026-07-01T00:00:00Z', endsAt: '2026-12-31T23:59:59Z', status: 'verified', verifiedAt: '2026-07-29' },
  { id: 'promo-2', providerId: 'siliconflow', title: 'SiliconFlow 新用户赠送额度', type: 'credit', description: '注册即送 14 元额度，可用于所有开源模型调用。', sourceUrl: SF_SRC, startsAt: '2026-06-01T00:00:00Z', endsAt: '2026-09-30T23:59:59Z', status: 'verified', verifiedAt: '2026-07-29' },
  // 已过期，用于验证过期标记
  { id: 'promo-3', providerId: 'openai', title: 'GPT-4.1 系列发布', type: 'price_change', description: 'GPT-4.1 相比 GPT-4o 降价并提升上下文能力。', sourceUrl: OA_SRC, startsAt: '2026-04-01T00:00:00Z', endsAt: '2026-05-01T00:00:00Z', status: 'verified', verifiedAt: '2026-07-29' },
]

// 后端 seed 同样不预置这些，演示时由用户在页面上创建
export const upstreams: UpstreamEndpoint[] = []
export const groups: ApiGroup[] = []
export const members: ApiGroupMember[] = []
export const gatewayRequests: GatewayRequest[] = []
export const routeAttempts: RouteAttempt[] = []

/**
 * 模拟上游故障场景。对应 E 的 mock_upstream 的 PUT /_mock/scenario。
 * 调用测试页可以切换，用来演示故障自动切换。
 */
export type FaultScenario = 'normal' | 'timeout' | 'rate_limited' | 'server_error' | 'client_error'

export const faultConfig: { firstUpstream: FaultScenario } = { firstUpstream: 'normal' }

let counter = 0
/** 递增 ID。不用 Date.now()/random，保证演示可复现。 */
export function nextId(prefix: string): string {
  counter += 1
  return `${prefix}-${counter}`
}

export function nowIso(): string {
  return new Date().toISOString()
}

// ---------------- 持久化 ----------------
//
// MVP 验收要求「刷新页面后配置仍存在」，所以 Mock 模式也必须跨刷新保留用户
// 创建的供应商 / 上游 / 分组。存进 localStorage。
//
// 安全前提：这里存的 upstreams 只含 apiKeyLastFour，明文 Key 从未进入过
// db，也就不可能被写进浏览器存储。

const STORE_KEY = 'pgp.mockdb.v1'

interface Persisted {
  providers: Provider[]
  models: ModelCatalogEntry[]
  prices: PriceSnapshot[]
  promotions: Omit<Promotion, 'active' | 'lifecycleStatus'>[]
  upstreams: UpstreamEndpoint[]
  groups: ApiGroup[]
  members: ApiGroupMember[]
  gatewayRequests: GatewayRequest[]
  routeAttempts: RouteAttempt[]
  counter: number
}

/** 原地替换数组内容，保持模块导出的引用不变 */
function refill<T>(target: T[], source: T[] | undefined): void {
  if (!source) return
  target.length = 0
  target.push(...source)
}

export function save(): void {
  try {
    const snapshot: Persisted = {
      providers,
      models,
      prices,
      promotions,
      upstreams,
      groups,
      members,
      gatewayRequests,
      routeAttempts,
      counter,
    }
    localStorage.setItem(STORE_KEY, JSON.stringify(snapshot))
  } catch {
    /* 存储写满或被禁用时降级为纯内存，不影响功能 */
  }
}

export function load(): void {
  try {
    const raw = localStorage.getItem(STORE_KEY)
    if (!raw) return
    const s = JSON.parse(raw) as Partial<Persisted>
    refill(providers, s.providers)
    refill(models, s.models)
    refill(prices, s.prices)
    refill(promotions, s.promotions)
    refill(upstreams, s.upstreams)
    refill(groups, s.groups)
    refill(members, s.members)
    refill(gatewayRequests, s.gatewayRequests)
    refill(routeAttempts, s.routeAttempts)
    if (typeof s.counter === 'number') counter = s.counter
  } catch {
    /* 数据损坏时回到种子状态 */
  }
}

/** 清空用户数据，回到种子状态。演示前重置用。 */
export function reset(): void {
  try {
    localStorage.removeItem(STORE_KEY)
  } catch {
    /* 忽略 */
  }
  window.location.reload()
}

load()
