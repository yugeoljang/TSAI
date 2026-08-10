package com.example.myapplication.data.model

/**
 * 网关调用的一次原始结果（纯数据，便于单测）。
 *
 * @param replyText 成功时 choices 首条内容；失败时为 null
 * @param error     失败时解析出的 OpenAI 风格错误（网关 ErrorEnvelope 的 error 字段）
 * @param httpStatus HTTP 状态码（失败兜底映射用）
 */
data class GatewayCallOutcome(
    val requestId: String? = null,
    val upstreamHeader: String? = null,
    val replyText: String? = null,
    val error: ChatApiError? = null,
    val httpStatus: Int? = null
)

/**
 * 展示在路由结果卡片上的信息。不包含上游内部技术细节与密钥。
 */
data class RouteResult(
    val requestId: String? = null,
    val finalUpstream: String? = null,
    val attemptCount: Int = 0,
    val switched: Boolean = false,
    val success: Boolean = false,
    val errorMessage: String? = null
)

object RouteResultMapper {

    /**
     * 网关响应 + 尝试记录 -> 路由结果。
     * 切换判定：attempts 条数 > 1（前提是网关记录按序尝试，失败才继续）。
     * 最终上游优先取 X-Upstream 头，缺失时退回最后一次尝试的上游名。
     */
    fun buildRouteResult(
        outcome: GatewayCallOutcome,
        attempts: List<RouteAttempt>? = null
    ): RouteResult {
        val count = attempts?.size ?: 0
        val requestId = outcome.requestId ?: attempts?.firstOrNull()?.requestId
        val finalUpstream = outcome.upstreamHeader
            ?: attempts?.lastOrNull()?.upstreamDisplayName
        val success = outcome.replyText != null
        return RouteResult(
            requestId = requestId,
            finalUpstream = finalUpstream,
            attemptCount = count,
            switched = count > 1,
            success = success,
            errorMessage = if (success) null else friendlyError(outcome)
        )
    }

    /**
     * 失败时的友好文案。优先用网关 ErrorEnvelope 的 message（已是安全文案，
     * 不含上游 sanitized_error 明细）；取不到时按 HTTP 状态兜底。
     */
    private fun friendlyError(outcome: GatewayCallOutcome): String {
        val message = outcome.error?.message
        if (!message.isNullOrBlank()) return message
        return when (outcome.httpStatus) {
            404 -> "找不到该 API 分组，或分组未启用。"
            429 -> "请求过于频繁，请稍后再试。"
            502 -> "所有候选上游均不可用，请稍后再试。"
            504 -> "请求超时，已尝试全部候选上游。"
            else -> "网关调用失败（HTTP ${outcome.httpStatus ?: "未知"}）。"
        }
    }
}
