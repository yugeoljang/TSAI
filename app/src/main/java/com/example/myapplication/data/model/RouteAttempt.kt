package com.example.myapplication.data.model

import kotlinx.serialization.Serializable

/**
 * 单次路由尝试记录（对齐服务端 RouteAttempt）。
 * 用于判断网关是否发生了故障切换：attemptCount > 1 即切换过。
 */
@Serializable
data class RouteAttempt(
    val requestId: String,
    val attemptIndex: Int,
    val upstreamEndpointId: String,
    val upstreamDisplayName: String? = null,
    val upstreamModelName: String? = null,
    val startedAt: String,
    val endedAt: String? = null,
    val resultCategory: String,
    val upstreamStatusCode: Int? = null,
    val durationMs: Int? = null,
    val sanitizedError: String? = null,
    val retryable: Boolean = false
)
