/**
 * Mock 路由表。模拟后端语义，让 5 个页面在 B/C 合并前就能跑通完整演示。
 *
 * 刻意保留的后端语义（这些正是最容易写错、也最该被验证的地方）：
 *   - routeKey 重复 → 409 conflict
 *   - 上游 apiKey 不传 → 保持原 Key 不变
 *   - members/order → 事务性重排后返回排序结果
 *   - 网关按 priorityRank 顺序尝试；超时/429/5xx 切换，400 不切换
 */
import { ApiError } from '../http'
import type { ApiResponse, HeaderBag, HttpMethod } from '../http'
import type {
  ApiGroup,
  ApiGroupCreate,
  ApiGroupDetail,
  ApiGroupMember,
  ApiGroupMemberCreate,
  ApiGroupMemberUpdate,
  ApiGroupUpdate,
  ChatCompletionRequest,
  ChatCompletionResponse,
  ErrorType,
  ModelCatalogCreate,
  ModelCatalogEntry,
  ModelCatalogUpdate,
  PriceSnapshot,
  PriceSnapshotCreate,
  Promotion,
  PromotionCreate,
  PromotionUpdate,
  Provider,
  ProviderCreate,
  ProviderUpdate,
  ResultCategory,
  RouteAttempt,
  UpstreamCreate,
  UpstreamEndpoint,
  UpstreamUpdate,
} from '@/types/api'
import * as db from './db'

const LATENCY_MS = 180

function fail(code: number, type: ErrorType, message: string, requestId?: string): never {
  // chatCompletions 会传入已生成的 requestId，让 ApiError 的 requestId 与
  // 路由尝试记录里的 requestId 一致 —— 否则前端 listAttempts 用错 ID 查不到。
  throw new ApiError(code, type, message, requestId ?? db.nextId('mockreq'))
}

/**
 * 不使用 `new Headers(headers)`：它是 ISO-8859-1 严格校验的，
 * 用户给上游取的中文 displayName 会直接抛 "String contains non ISO-8859-1 code point"。
 * 自己实现一个最小 bag，只暴露消费者用得到的 .get / .has。
 */
function makeBag(headers: Record<string, string> = {}): HeaderBag {
  // 用小写 key 建索引，.get 走大写小写无差别
  const idx = new Map<string, string>()
  for (const [k, v] of Object.entries(headers)) idx.set(k.toLowerCase(), v)
  return {
    get(name: string): string | null {
      return idx.get(name.toLowerCase()) ?? null
    },
    has(name: string): boolean {
      return idx.has(name.toLowerCase())
    },
  }
}

function ok<T>(data: T, headers: Record<string, string> = {}): ApiResponse<T> {
  return { data, headers: makeBag(headers) }
}

export async function handleMock<T>(
  method: HttpMethod,
  path: string,
  body?: unknown,
): Promise<ApiResponse<T>> {
  // 模拟网络延迟，让加载态在演示中真实可见
  await new Promise((r) => setTimeout(r, LATENCY_MS))

  const [rawPath, search] = path.split('?')
  const query = new URLSearchParams(search ?? '')
  const seg = rawPath.split('/').filter(Boolean) // 如 ['api','admin','providers','deepseek']

  try {
    const res = route(method, seg, query, body)
    return res as ApiResponse<T>
  } finally {
    // 任何写操作后落盘，保证刷新页面配置仍在。
    // 放在 finally 里：失败调用（chatCompletions 内部 fail 抛错）
    // 也已经往 db 写入了 GatewayRequest / RouteAttempt，同样要保存。
    if (method !== 'GET') db.save()
  }
}

function route(
  method: HttpMethod,
  seg: string[],
  q: URLSearchParams,
  body: unknown,
): ApiResponse<unknown> {
  // ---- POST /v1/chat/completions ----
  if (seg[0] === 'v1' && seg[1] === 'chat' && seg[2] === 'completions' && method === 'POST') {
    return chatCompletions(body as ChatCompletionRequest)
  }

  if (seg[0] === 'health') return ok({ status: 'ok', database: 'ok', version: '0.1.0-mock' })

  if (seg[0] !== 'api' || seg[1] !== 'admin') fail(404, 'not_found', `Mock 未覆盖的路径：/${seg.join('/')}`)

  const [resource, id, sub, subId] = seg.slice(2)

  switch (resource) {
    case 'providers':
      return providersRoute(method, id, body)
    case 'upstreams':
      return upstreamsRoute(method, id, body)
    case 'groups':
      return groupsRoute(method, id, sub, subId, body)
    case 'models':
      return modelsRoute(method, id, q, body)
    case 'prices':
      return pricesRoute(method, id, sub, q, body)
    case 'promotions':
      return promotionsRoute(method, id, q, body)
    case 'requests':
      return requestsRoute(id, sub, q)
    default:
      fail(404, 'not_found', `Mock 未覆盖的资源：${resource}`)
  }
}

function filterByProvider<T extends { providerId: string }>(list: T[], q: URLSearchParams): T[] {
  const pid = q.get('providerId')
  return pid ? list.filter((x) => x.providerId === pid) : [...list]
}

// ---------- 供应商 ----------

function providersRoute(method: HttpMethod, id: string | undefined, body: unknown): ApiResponse<unknown> {
  if (!id) {
    if (method === 'GET') return ok([...db.providers])
    if (method === 'POST') {
      const input = body as ProviderCreate
      if (!input?.name?.trim()) fail(422, 'validation_error', '供应商名称不能为空')
      const created: Provider = {
        id: db.nextId('provider'),
        name: input.name.trim(),
        protocolType: 'OPENAI_COMPATIBLE',
        officialUrl: input.officialUrl ?? null,
        pricingUrl: input.pricingUrl ?? null,
        enabled: input.enabled ?? true,
        createdAt: db.nowIso(),
        updatedAt: db.nowIso(),
      }
      db.providers.push(created)
      return ok(created)
    }
  }

  const idx = db.providers.findIndex((p) => p.id === id)
  if (idx === -1) fail(404, 'not_found', '供应商不存在')

  if (method === 'GET') return ok(db.providers[idx])

  if (method === 'PATCH') {
    const patch = body as ProviderUpdate
    const cur = db.providers[idx]
    db.providers[idx] = {
      ...cur,
      ...(patch.name !== undefined ? { name: patch.name } : {}),
      ...(patch.officialUrl !== undefined ? { officialUrl: patch.officialUrl } : {}),
      ...(patch.pricingUrl !== undefined ? { pricingUrl: patch.pricingUrl } : {}),
      ...(patch.enabled !== undefined ? { enabled: patch.enabled } : {}),
      updatedAt: db.nowIso(),
    }
    return ok(db.providers[idx])
  }

  if (method === 'DELETE') {
    if (db.upstreams.some((u) => u.providerId === id)) {
      fail(409, 'conflict', '该供应商下仍有上游，请先删除上游')
    }
    db.providers.splice(idx, 1)
    return ok(undefined)
  }

  fail(404, 'not_found', '不支持的操作')
}

// ---------- 上游 ----------

function upstreamsRoute(method: HttpMethod, id: string | undefined, body: unknown): ApiResponse<unknown> {
  if (!id) {
    if (method === 'GET') return ok([...db.upstreams])
    if (method === 'POST') {
      const input = body as UpstreamCreate
      if (!input?.displayName?.trim()) fail(422, 'validation_error', '显示名称不能为空')
      if (!input?.baseUrl?.trim()) fail(422, 'validation_error', 'Base URL 不能为空')
      if (!input?.apiKey?.trim()) fail(422, 'validation_error', '新增上游时 API Key 必填')
      if (!db.providers.some((p) => p.id === input.providerId)) {
        fail(422, 'validation_error', '供应商不存在')
      }
      const created: UpstreamEndpoint = {
        id: db.nextId('upstream'),
        providerId: input.providerId,
        displayName: input.displayName.trim(),
        baseUrl: input.baseUrl.trim(),
        apiKeyLastFour: lastFour(input.apiKey),
        defaultModel: input.defaultModel ?? null,
        enabled: input.enabled ?? true,
        timeoutMs: input.timeoutMs ?? 15000,
        createdAt: db.nowIso(),
        updatedAt: db.nowIso(),
      }
      db.upstreams.push(created)
      return ok(created)
    }
  }

  const idx = db.upstreams.findIndex((u) => u.id === id)
  if (idx === -1) fail(404, 'not_found', '上游不存在')

  if (method === 'GET') return ok(db.upstreams[idx])

  if (method === 'PATCH') {
    const patch = body as UpstreamUpdate
    const cur = db.upstreams[idx]
    db.upstreams[idx] = {
      ...cur,
      ...(patch.displayName !== undefined ? { displayName: patch.displayName } : {}),
      ...(patch.baseUrl !== undefined ? { baseUrl: patch.baseUrl } : {}),
      ...(patch.defaultModel !== undefined ? { defaultModel: patch.defaultModel } : {}),
      ...(patch.enabled !== undefined ? { enabled: patch.enabled } : {}),
      ...(patch.timeoutMs !== undefined ? { timeoutMs: patch.timeoutMs } : {}),
      // 关键语义：apiKey 不传 = 保持原 Key。前端必须永远不发空串。
      ...(patch.apiKey ? { apiKeyLastFour: lastFour(patch.apiKey) } : {}),
      updatedAt: db.nowIso(),
    }
    return ok(db.upstreams[idx])
  }

  if (method === 'DELETE') {
    const memberIdx = db.members.findIndex((m) => m.upstreamEndpointId === id)
    if (memberIdx !== -1) fail(409, 'conflict', '该上游仍被分组引用，请先从分组移除')
    db.upstreams.splice(idx, 1)
    return ok(undefined)
  }

  fail(404, 'not_found', '不支持的操作')
}

function lastFour(key: string): string {
  return key.trim().slice(-4).padStart(4, '*')
}

// ---------- 分组 ----------

function groupsRoute(
  method: HttpMethod,
  id: string | undefined,
  sub: string | undefined,
  subId: string | undefined,
  body: unknown,
): ApiResponse<unknown> {
  if (!id) {
    if (method === 'GET') return ok([...db.groups])
    if (method === 'POST') {
      const input = body as ApiGroupCreate
      if (!input?.name?.trim()) fail(422, 'validation_error', '分组名称不能为空')
      if (!input?.routeKey?.trim()) fail(422, 'validation_error', 'routeKey 不能为空')
      // 后端会返回 409，页面要给出「已被占用」的专门提示
      if (db.groups.some((g) => g.routeKey === input.routeKey.trim())) {
        fail(409, 'conflict', `routeKey「${input.routeKey}」已被占用`)
      }
      const created: ApiGroup = {
        id: db.nextId('group'),
        name: input.name.trim(),
        routeKey: input.routeKey.trim(),
        routingPolicy: 'ORDERED_FAILOVER',
        maxAttempts: input.maxAttempts ?? 3,
        enabled: input.enabled ?? true,
        createdAt: db.nowIso(),
        updatedAt: db.nowIso(),
      }
      db.groups.push(created)
      return ok(created)
    }
  }

  const gIdx = db.groups.findIndex((g) => g.id === id)
  if (gIdx === -1) fail(404, 'not_found', '分组不存在')

  // ---- 成员子资源 ----
  if (sub === 'members') {
    return membersRoute(method, id!, subId, body)
  }

  if (method === 'GET') {
    // GET /groups/{id} 是唯一返回 members 的接口
    const detail: ApiGroupDetail = { ...db.groups[gIdx], members: sortedMembers(id!) }
    return ok(detail)
  }

  if (method === 'PATCH') {
    const patch = body as ApiGroupUpdate
    db.groups[gIdx] = {
      ...db.groups[gIdx],
      ...(patch.name !== undefined ? { name: patch.name } : {}),
      ...(patch.maxAttempts !== undefined ? { maxAttempts: patch.maxAttempts } : {}),
      ...(patch.enabled !== undefined ? { enabled: patch.enabled } : {}),
      updatedAt: db.nowIso(),
    }
    return ok(db.groups[gIdx])
  }

  if (method === 'DELETE') {
    db.groups.splice(gIdx, 1)
    for (let i = db.members.length - 1; i >= 0; i--) {
      if (db.members[i].groupId === id) db.members.splice(i, 1)
    }
    return ok(undefined)
  }

  fail(404, 'not_found', '不支持的操作')
}

function sortedMembers(groupId: string): ApiGroupMember[] {
  return db.members
    .filter((m) => m.groupId === groupId)
    .sort((a, b) => a.priorityRank - b.priorityRank)
}

function membersRoute(
  method: HttpMethod,
  groupId: string,
  subId: string | undefined,
  body: unknown,
): ApiResponse<unknown> {
  // PUT /groups/{id}/members/order —— 事务性重排
  if (subId === 'order' && method === 'PUT') {
    const { orderedMemberIds } = body as { orderedMemberIds: string[] }
    const current = sortedMembers(groupId)
    if (orderedMemberIds.length !== current.length) {
      fail(422, 'validation_error', '成员 ID 列表与当前成员数量不一致')
    }
    orderedMemberIds.forEach((mid, i) => {
      const m = db.members.find((x) => x.id === mid && x.groupId === groupId)
      if (!m) fail(422, 'validation_error', `成员 ${mid} 不属于该分组`)
      m.priorityRank = i + 1
    })
    return ok(sortedMembers(groupId))
  }

  if (!subId && method === 'POST') {
    const input = body as ApiGroupMemberCreate
    if (!db.upstreams.some((u) => u.id === input.upstreamEndpointId)) {
      fail(422, 'validation_error', '上游不存在')
    }
    if (!input.upstreamModelName?.trim()) {
      fail(422, 'validation_error', '上游模型名不能为空')
    }
    const existing = sortedMembers(groupId)
    const created: ApiGroupMember = {
      id: db.nextId('member'),
      groupId,
      upstreamEndpointId: input.upstreamEndpointId,
      upstreamDisplayName:
        db.upstreams.find((u) => u.id === input.upstreamEndpointId)?.displayName ?? null,
      upstreamModelName: input.upstreamModelName.trim(),
      priorityRank: input.priorityRank ?? existing.length + 1,
      enabled: input.enabled ?? true,
    }
    db.members.push(created)
    return ok(created)
  }

  const mIdx = db.members.findIndex((m) => m.id === subId && m.groupId === groupId)
  if (mIdx === -1) fail(404, 'not_found', '成员不存在')

  if (method === 'PATCH') {
    const patch = body as ApiGroupMemberUpdate
    db.members[mIdx] = {
      ...db.members[mIdx],
      ...(patch.upstreamModelName !== undefined ? { upstreamModelName: patch.upstreamModelName } : {}),
      ...(patch.priorityRank !== undefined ? { priorityRank: patch.priorityRank } : {}),
      ...(patch.enabled !== undefined ? { enabled: patch.enabled } : {}),
    }
    return ok(db.members[mIdx])
  }

  if (method === 'DELETE') {
    db.members.splice(mIdx, 1)
    // 重排剩余成员，避免出现优先级空洞
    sortedMembers(groupId).forEach((m, i) => (m.priorityRank = i + 1))
    return ok(undefined)
  }

  fail(404, 'not_found', '不支持的操作')
}

// ---------- 模型与价格 ----------

function modelsRoute(method: HttpMethod, id: string | undefined, q: URLSearchParams, body: unknown): ApiResponse<unknown> {
  if (!id) {
    if (method === 'GET') {
      let list = filterByProvider(db.models, q)
      if (q.get('includeDisabled') !== 'true') list = list.filter((m) => m.enabled)
      const keyword = q.get('keyword')?.trim().toLowerCase()
      if (keyword) list = list.filter((m) => `${m.displayName} ${m.upstreamModelId}`.toLowerCase().includes(keyword))
      return ok(list)
    }
    if (method === 'POST') {
      const input = body as ModelCatalogCreate
      if (!db.providers.some((p) => p.id === input.providerId)) fail(404, 'not_found', '供应商不存在')
      if (db.models.some((m) => m.providerId === input.providerId && m.upstreamModelId === input.upstreamModelId)) {
        fail(409, 'conflict', '同一供应商下不能重复添加相同模型 ID')
      }
      const created: ModelCatalogEntry = { id: db.nextId('model'), ...input, enabled: input.enabled ?? true }
      db.models.push(created)
      return ok(created)
    }
  }
  const idx = db.models.findIndex((m) => m.id === id)
  if (idx === -1) fail(404, 'not_found', '模型不存在')
  if (method === 'PATCH') {
    const patch = body as ModelCatalogUpdate
    db.models[idx] = { ...db.models[idx], ...patch }
    return ok(db.models[idx])
  }
  if (method === 'DELETE') {
    db.models.splice(idx, 1)
    for (let i = db.prices.length - 1; i >= 0; i--) if (db.prices[i].modelCatalogEntryId === id) db.prices.splice(i, 1)
    return ok(undefined)
  }
  fail(404, 'not_found', '不支持的模型操作')
}

function pricesRoute(method: HttpMethod, id: string | undefined, sub: string | undefined,
  q: URLSearchParams, body: unknown): ApiResponse<unknown> {
  if (id === 'history' && sub && method === 'GET') {
    return ok(db.prices.filter((p) => p.modelCatalogEntryId === sub)
      .sort((a, b) => Number(b.isCurrent) - Number(a.isCurrent) || (b.effectiveFrom ?? '').localeCompare(a.effectiveFrom ?? '')))
  }
  if (!id) {
    if (method === 'GET') {
      let list = filterByProvider(db.prices, q)
      if (q.get('currentOnly') !== 'false') list = list.filter((p) => p.isCurrent)
      const modelId = q.get('modelCatalogEntryId')
      if (modelId) list = list.filter((p) => p.modelCatalogEntryId === modelId)
      return ok(list)
    }
    if (method === 'POST') {
      const input = body as PriceSnapshotCreate
      const model = db.models.find((m) => m.id === input.modelCatalogEntryId)
      if (!model) fail(404, 'not_found', '模型不存在')
      if (input.inputPricePerMillionTokens == null && input.outputPricePerMillionTokens == null) {
        fail(422, 'validation_error', '输入价和输出价至少填写一项')
      }
      db.prices.filter((p) => p.modelCatalogEntryId === input.modelCatalogEntryId).forEach((p) => (p.isCurrent = false))
      const created: PriceSnapshot = {
        id: db.nextId('price'), providerId: model.providerId, ...input,
        currency: input.currency.toUpperCase(), isCurrent: true,
      }
      db.prices.push(created)
      return ok(created)
    }
  }
  const idx = db.prices.findIndex((p) => p.id === id)
  if (idx === -1) fail(404, 'not_found', '价格快照不存在')
  if (method === 'DELETE') {
    const removed = db.prices[idx]
    db.prices.splice(idx, 1)
    if (removed.isCurrent) {
      const previous = db.prices.filter((p) => p.modelCatalogEntryId === removed.modelCatalogEntryId)
        .sort((a, b) => (b.effectiveFrom ?? '').localeCompare(a.effectiveFrom ?? ''))[0]
      if (previous) previous.isCurrent = true
    }
    return ok(undefined)
  }
  fail(404, 'not_found', '不支持的价格操作')
}

// ---------- 活动 ----------

function promotionDto(p: (typeof db.promotions)[number]): Promotion {
  const now = Date.now()
  const starts = p.startsAt ? Date.parse(p.startsAt) : -Infinity
  const ends = p.endsAt ? Date.parse(p.endsAt) : Infinity
  const lifecycleStatus = p.status === 'draft' ? 'draft'
    : p.status === 'expired' || now > ends ? 'expired'
      : now < starts ? 'upcoming' : 'active'
  return { ...p, active: lifecycleStatus === 'active', lifecycleStatus }
}

function promotionsRoute(method: HttpMethod, id: string | undefined, q: URLSearchParams, body: unknown): ApiResponse<unknown> {
  if (!id && method === 'POST') {
    const input = body as PromotionCreate
    if (!db.providers.some((p) => p.id === input.providerId)) fail(404, 'not_found', '供应商不存在')
    const created = { id: db.nextId('promo'), ...input, status: input.status ?? 'draft' } as (typeof db.promotions)[number]
    db.promotions.push(created)
    return ok(promotionDto(created))
  }
  if (id) {
    const idx = db.promotions.findIndex((p) => p.id === id)
    if (idx === -1) fail(404, 'not_found', '活动不存在')
    if (method === 'PATCH') {
      db.promotions[idx] = { ...db.promotions[idx], ...(body as PromotionUpdate) }
      return ok(promotionDto(db.promotions[idx]))
    }
    if (method === 'DELETE') {
      db.promotions.splice(idx, 1)
      return ok(undefined)
    }
  }

  let list = db.promotions.map(promotionDto)

  const pid = q.get('providerId')
  if (pid) list = list.filter((p) => p.providerId === pid)
  if (q.get('activeOnly') === 'true') list = list.filter((p) => p.active)
  const lifecycle = q.get('lifecycleStatus')
  if (lifecycle) list = list.filter((p) => p.lifecycleStatus === lifecycle)

  return ok(list)
}

// ---------- 路由记录 ----------

function requestsRoute(
  id: string | undefined,
  sub: string | undefined,
  q: URLSearchParams,
): ApiResponse<unknown> {
  if (id && sub === 'attempts') {
    return ok(db.routeAttempts.filter((a) => a.requestId === id).sort((a, b) => a.attemptIndex - b.attemptIndex))
  }
  const limit = Number(q.get('limit') ?? 20)
  // 最近的排前面
  return ok([...db.gatewayRequests].reverse().slice(0, limit))
}

// ---------- 网关调用：顺序故障切换模拟 ----------

/** 各故障场景对应的尝试结果。retryable 决定是否继续切换下一个上游。 */
const SCENARIO: Record<
  db.FaultScenario,
  { category: ResultCategory; status: number | null; retryable: boolean; error: string | null; ms: number }
> = {
  normal: { category: 'success', status: 200, retryable: false, error: null, ms: 820 },
  timeout: { category: 'timeout', status: null, retryable: true, error: '读取超时（15000ms）', ms: 15000 },
  rate_limited: { category: 'rate_limited', status: 429, retryable: true, error: 'Too Many Requests', ms: 210 },
  server_error: { category: 'server_error', status: 500, retryable: true, error: 'Internal Server Error', ms: 340 },
  // 400 属于参数错误，不切换 —— 这是 MVP 明确要求的行为
  client_error: { category: 'client_error', status: 400, retryable: false, error: 'Invalid request parameter', ms: 90 },
}

function chatCompletions(req: ChatCompletionRequest): ApiResponse<ChatCompletionResponse> {
  const requestId = db.nextId('req')

  if (req.stream === true) {
    fail(400, 'stream_not_supported', '初版只支持 stream=false', requestId)
  }
  if (!req.messages?.length) {
    fail(400, 'validation_error', 'messages 不能为空', requestId)
  }

  const group = db.groups.find((g) => g.routeKey === req.model)
  if (!group) {
    fail(404, 'not_found', `找不到 routeKey 为「${req.model}」的分组`, requestId)
  }
  if (!group.enabled) {
    fail(404, 'not_found', `分组「${group.name}」已停用`, requestId)
  }

  const candidates = sortedMembers(group.id).filter((m) => {
    const up = db.upstreams.find((u) => u.id === m.upstreamEndpointId)
    return m.enabled && up?.enabled
  })
  if (candidates.length === 0) {
    fail(502, 'all_upstreams_failed', '分组内没有可用的上游成员', requestId)
  }

  const startedAt = db.nowIso()
  const attempts: RouteAttempt[] = []
  let winner: ApiGroupMember | null = null
  let lastCategory: ResultCategory = 'server_error'

  const maxAttempts = Math.min(group.maxAttempts, candidates.length)

  for (let i = 0; i < maxAttempts; i++) {
    const member = candidates[i]
    // 只有第一个上游受故障开关控制，其余一律正常 —— 正好对应演示脚本
    const scenario = i === 0 ? db.faultConfig.firstUpstream : 'normal'
    const s = SCENARIO[scenario]

    attempts.push({
      requestId,
      attemptIndex: i + 1,
      upstreamEndpointId: member.upstreamEndpointId,
      upstreamDisplayName: member.upstreamDisplayName ?? null,
      upstreamModelName: member.upstreamModelName,
      startedAt,
      endedAt: db.nowIso(),
      resultCategory: s.category,
      upstreamStatusCode: s.status,
      durationMs: s.ms,
      sanitizedError: s.error,
      retryable: s.retryable,
    })

    if (s.category === 'success') {
      winner = member
      break
    }
    lastCategory = s.category
    // 不可重试（如 400 参数错误）→ 立即停止，不再尝试后续上游
    if (!s.retryable) break
  }

  db.routeAttempts.push(...attempts)

  const finalStatus = winner
    ? 'success'
    : lastCategory === 'client_error'
      ? 'client_error'
      : lastCategory === 'timeout'
        ? 'timeout'
        : 'all_failed'

  db.gatewayRequests.push({
    requestId,
    routeKey: req.model,
    startedAt,
    endedAt: db.nowIso(),
    finalStatus,
    finalUpstreamDisplayName: winner?.upstreamDisplayName ?? null,
    attemptCount: attempts.length,
  })

  if (!winner) {
    if (finalStatus === 'client_error') {
      fail(400, 'validation_error', '上游返回参数错误（400），按策略不切换其他上游', requestId)
    }
    if (finalStatus === 'timeout') {
      fail(504, 'request_timeout', '整次请求超时', requestId)
    }
    fail(502, 'all_upstreams_failed', `已尝试 ${attempts.length} 个上游，全部失败`, requestId)
  }

  const question = req.messages[req.messages.length - 1]?.content ?? ''
  const answer =
    `【Mock 回答】本次请求由上游「${winner.upstreamDisplayName}」` +
    `使用模型 ${winner.upstreamModelName} 处理。\n\n` +
    `你的问题是：${question}\n\n` +
    (attempts.length > 1
      ? `注意：前 ${attempts.length - 1} 个上游失败后已自动切换到本上游。`
      : '第一优先级上游正常，未触发切换。')

  return ok<ChatCompletionResponse>(
    {
      id: `chatcmpl-${requestId}`,
      object: 'chat.completion',
      choices: [{ index: 0, message: { role: 'assistant', content: answer }, finish_reason: 'stop' }],
      usage: { prompt_tokens: 42, completion_tokens: 96, total_tokens: 138 },
    },
    // 与后端 expose_headers 一致，D5 从这里读
    { 'X-Request-Id': requestId, 'X-Upstream': winner.upstreamDisplayName ?? '' },
  )
}
