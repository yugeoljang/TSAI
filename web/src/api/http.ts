import type { ErrorEnvelope, ErrorType } from '@/types/api'
import { handleMock } from './mock/handlers'

/** 归一化后的接口错误。所有页面只需 catch 这一种。 */
export class ApiError extends Error {
  constructor(
    public code: number,
    public type: ErrorType,
    message: string,
    public requestId?: string,
    public details?: unknown[],
  ) {
    super(message)
    this.name = 'ApiError'
  }

  /** 给用户看的中文说明。区分几种最常见的失败，避免笼统报错。 */
  get friendly(): string {
    switch (this.type) {
      case 'not_found':
        return this.message || '资源不存在'
      case 'conflict':
        return this.message || '已存在同名资源'
      case 'validation_error':
        return this.message || '参数校验失败'
      case 'all_upstreams_failed':
        return '分组内所有上游均调用失败'
      case 'request_timeout':
        return '整次请求超时'
      case 'stream_not_supported':
        return '初版不支持流式响应（stream=true）'
      default:
        return this.message || '服务异常'
    }
  }
}

// ---------- Mock 开关 ----------
// 默认值来自 .env，运行时可在页头切换并记住选择。

const MOCK_KEY = 'pgp.useMock'

export function isMockOn(): boolean {
  const saved = localStorage.getItem(MOCK_KEY)
  if (saved !== null) return saved === 'true'
  return import.meta.env.VITE_USE_MOCK === 'true'
}

export function setMockOn(on: boolean): void {
  localStorage.setItem(MOCK_KEY, String(on))
}

// ---------- 请求 ----------

export type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

/**
 * 响应的「可读头部」接口。
 * 真实后端走 fetch 返回的 `Headers` 自带 .get() / .has()；
 * Mock 不能用 `new Headers()`，因为它强制 ISO-8859-1，
 * 上游的 displayName 是中文时会抛 "String contains non ISO-8859-1 code point"。
 * 这里抽象出一个最小子集：消费者只要 .get(key)。
 */
export interface HeaderBag {
  get(name: string): string | null
  has(name: string): boolean
}

export interface ApiResponse<T> {
  data: T
  /** D5 需要从这里读 X-Request-Id 与 X-Upstream */
  headers: HeaderBag
}

/**
 * 唯一的网络出入口。Mock 与真实后端在此分流。
 * 路径一律用相对路径（如 /api/admin/providers），由 vite dev proxy 转发到后端。
 */
export async function request<T>(
  method: HttpMethod,
  path: string,
  body?: unknown,
): Promise<ApiResponse<T>> {
  if (isMockOn()) {
    return handleMock<T>(method, path, body)
  }

  let res: Response
  try {
    res = await fetch(path, {
      method,
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    // 后端没启动 / 网络断开：fetch 直接 reject，此时没有任何响应可解析
    throw new ApiError(0, 'internal_error', '无法连接后端服务，请确认它已在 127.0.0.1:8000 启动')
  }

  if (!res.ok) throw await toApiError(res)

  // 204 No Content 没有 body，不能盲目 .json()
  if (res.status === 204) {
    return { data: undefined as T, headers: res.headers }
  }

  const text = await res.text()
  if (!text) return { data: undefined as T, headers: res.headers }

  try {
    return { data: JSON.parse(text) as T, headers: res.headers }
  } catch {
    throw new ApiError(res.status, 'internal_error', '响应不是合法 JSON')
  }
}

/**
 * 把失败响应转成 ApiError。
 * 后端正常情况下返回 { error: {...} } 信封，但 501 兜底、代理错误、
 * 反向代理返回 HTML 等情况下 body 未必是 JSON，必须兜住。
 */
async function toApiError(res: Response): Promise<ApiError> {
  const requestIdHeader = res.headers.get('X-Request-Id') ?? undefined
  let text = ''
  try {
    text = await res.text()
  } catch {
    /* 读不出 body 就用状态码兜底 */
  }

  try {
    const envelope = JSON.parse(text) as ErrorEnvelope
    const e = envelope?.error
    if (e && typeof e.message === 'string') {
      return new ApiError(
        e.code ?? res.status,
        e.type ?? 'internal_error',
        e.message,
        e.requestId ?? requestIdHeader,
        e.details,
      )
    }
  } catch {
    /* 不是 JSON，走下面的兜底 */
  }

  const fallback =
    res.status === 501
      ? '该接口尚未实现（后端 501）。可打开右上角「Mock 模式」继续演示。'
      : `请求失败：HTTP ${res.status}`
  return new ApiError(res.status, 'internal_error', fallback, requestIdHeader)
}

// ---------- 便捷方法 ----------

export const http = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
}

/** 拼查询串，自动跳过 undefined / null / 空串 */
export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== '',
  )
  if (entries.length === 0) return ''
  return '?' + entries.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')
}
