import { http, qs } from './http'
import type {
  Provider,
  ProviderCreate,
  ProviderUpdate,
  ModelCatalogCreate,
  ModelCatalogUpdate,
  PriceSnapshotCreate,
  PromotionCreate,
  PromotionUpdate,
  UpstreamCreate,
  UpstreamEndpoint,
  UpstreamUpdate,
} from '@/types/api'

const A = '/api/admin'

// ---------- 供应商 ----------

export const listProviders = () => http.get<Provider[]>(`${A}/providers`).then((r) => r.data)

export const createProvider = (input: ProviderCreate) =>
  http.post<Provider>(`${A}/providers`, input).then((r) => r.data)

export const updateProvider = (id: string, input: ProviderUpdate) =>
  http.patch<Provider>(`${A}/providers/${id}`, input).then((r) => r.data)

export const deleteProvider = (id: string) => http.delete<void>(`${A}/providers/${id}`)

// ---------- 上游 ----------

export const listUpstreams = () => http.get<UpstreamEndpoint[]>(`${A}/upstreams`).then((r) => r.data)

export const createUpstream = (input: UpstreamCreate) =>
  http.post<UpstreamEndpoint>(`${A}/upstreams`, input).then((r) => r.data)

/**
 * 注意：调用方若不想改 Key，必须整个省略 apiKey 字段，不要传空字符串。
 * 这里主动剔除空值，避免把 Key 覆盖成空。
 */
export const updateUpstream = (id: string, input: UpstreamUpdate) => {
  const payload: UpstreamUpdate = { ...input }
  if (!payload.apiKey?.trim()) delete payload.apiKey
  return http.patch<UpstreamEndpoint>(`${A}/upstreams/${id}`, payload).then((r) => r.data)
}

export const deleteUpstream = (id: string) => http.delete<void>(`${A}/upstreams/${id}`)

// ---------- 目录：模型 / 价格 / 活动 ----------

export const listModels = (opts: { providerId?: string; includeDisabled?: boolean; keyword?: string } = {}) =>
  http.get<import('@/types/api').ModelCatalogEntry[]>(`${A}/models${qs({ ...opts })}`).then((r) => r.data)

export const createModel = (input: ModelCatalogCreate) =>
  http.post<import('@/types/api').ModelCatalogEntry>(`${A}/models`, input).then((r) => r.data)

export const updateModel = (id: string, input: ModelCatalogUpdate) =>
  http.patch<import('@/types/api').ModelCatalogEntry>(`${A}/models/${id}`, input).then((r) => r.data)

export const deleteModel = (id: string) => http.delete<void>(`${A}/models/${id}`)

export const listPrices = (opts: { providerId?: string; modelCatalogEntryId?: string; currentOnly?: boolean } = {}) =>
  http.get<import('@/types/api').PriceSnapshot[]>(`${A}/prices${qs({ ...opts })}`).then((r) => r.data)

export const listPriceHistory = (modelId: string) =>
  http.get<import('@/types/api').PriceSnapshot[]>(`${A}/prices/history/${modelId}`).then((r) => r.data)

export const createPrice = (input: PriceSnapshotCreate) =>
  http.post<import('@/types/api').PriceSnapshot>(`${A}/prices`, input).then((r) => r.data)

export const deletePrice = (id: string) => http.delete<void>(`${A}/prices/${id}`)

export const listPromotions = (opts: { providerId?: string; activeOnly?: boolean; lifecycleStatus?: string } = {}) =>
  http
    .get<import('@/types/api').Promotion[]>(`${A}/promotions${qs({ ...opts })}`)
    .then((r) => r.data)

export const createPromotion = (input: PromotionCreate) =>
  http.post<import('@/types/api').Promotion>(`${A}/promotions`, input).then((r) => r.data)

export const updatePromotion = (id: string, input: PromotionUpdate) =>
  http.patch<import('@/types/api').Promotion>(`${A}/promotions/${id}`, input).then((r) => r.data)

export const deletePromotion = (id: string) => http.delete<void>(`${A}/promotions/${id}`)
