import { http, qs } from './http'
import type {
  Provider,
  ProviderCreate,
  ProviderUpdate,
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

export const listModels = (providerId?: string) =>
  http.get<import('@/types/api').ModelCatalogEntry[]>(`${A}/models${qs({ providerId })}`).then((r) => r.data)

export const listPrices = (providerId?: string) =>
  http.get<import('@/types/api').PriceSnapshot[]>(`${A}/prices${qs({ providerId })}`).then((r) => r.data)

export const listPromotions = (opts: { providerId?: string; activeOnly?: boolean } = {}) =>
  http
    .get<import('@/types/api').Promotion[]>(`${A}/promotions${qs({ ...opts })}`)
    .then((r) => r.data)
