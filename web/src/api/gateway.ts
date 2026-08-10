import { http, qs } from './http'
import type { ChatCompletionRequest, ChatCompletionResponse, GatewayRequest, RouteAttempt } from '@/types/api'

export interface ChatResult {
  answer: string
  /** 来自响应头 X-Upstream —— 最终真正服务本次请求的上游 */
  finalUpstream: string | null
  /** 来自响应头 X-Request-Id */
  requestId: string | null
  usage?: ChatCompletionResponse['usage']
}

/**
 * 通过分组 routeKey 发起一次真实调用。
 * routeKey 填在 OpenAI 请求体的 model 字段，这是本产品的核心约定。
 */
export async function sendChat(routeKey: string, question: string): Promise<ChatResult> {
  const body: ChatCompletionRequest = {
    model: routeKey,
    messages: [{ role: 'user', content: question }],
    stream: false,
  }
  const { data, headers } = await http.post<ChatCompletionResponse>('/v1/chat/completions', body)
  return {
    answer: data.choices?.[0]?.message?.content ?? '(上游返回了空内容)',
    finalUpstream: headers.get('X-Upstream'),
    requestId: headers.get('X-Request-Id'),
    usage: data.usage,
  }
}

export const listRequests = (limit = 20) =>
  http.get<GatewayRequest[]>(`/api/admin/requests${qs({ limit })}`).then((r) => r.data)

export const listAttempts = (requestId: string) =>
  http.get<RouteAttempt[]>(`/api/admin/requests/${requestId}/attempts`).then((r) => r.data)
