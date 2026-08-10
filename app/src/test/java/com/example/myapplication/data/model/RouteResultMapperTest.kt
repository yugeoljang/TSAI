package com.example.myapplication.data.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RouteResultMapperTest {

    private fun attempt(
        requestId: String,
        index: Int,
        displayName: String,
        category: String,
        statusCode: Int
    ) = RouteAttempt(
        requestId = requestId,
        attemptIndex = index,
        upstreamEndpointId = "u$index",
        upstreamDisplayName = displayName,
        upstreamModelName = "mock-model",
        startedAt = "2026-08-10T00:00:00Z",
        resultCategory = category,
        upstreamStatusCode = statusCode
    )

    @Test
    fun failoverSuccessMarksSwitched() {
        val outcome = GatewayCallOutcome(
            requestId = "req-1",
            upstreamHeader = "mock-ok",
            replyText = "你好！",
            httpStatus = 200
        )
        val attempts = listOf(
            attempt("req-1", 1, "mock-fail", "server_error", 500),
            attempt("req-1", 2, "mock-ok", "success", 200)
        )

        val result = RouteResultMapper.buildRouteResult(outcome, attempts)

        assertTrue(result.success)
        assertTrue(result.switched)
        assertEquals("req-1", result.requestId)
        assertEquals("mock-ok", result.finalUpstream)
        assertEquals(2, result.attemptCount)
        assertNull(result.errorMessage)
    }

    @Test
    fun directHitWhenOnlyOneAttempt() {
        val outcome = GatewayCallOutcome(
            requestId = "req-2",
            upstreamHeader = "mock-ok",
            replyText = "ok"
        )
        val attempts = listOf(
            attempt("req-2", 1, "mock-ok", "success", 200)
        )

        val result = RouteResultMapper.buildRouteResult(outcome, attempts)

        assertTrue(result.success)
        assertFalse(result.switched)
        assertEquals(1, result.attemptCount)
    }

    @Test
    fun typeMapOverridesGatewayMessage() {
        // 网关"有候选但全挂"时会透出上游响应体原文（message 含技术细节），
        // Android 必须按 error.type 映射固定友好文案，而不是展示 message。
        val outcome = GatewayCallOutcome(
            requestId = "req-3",
            error = ChatApiError(
                message = "Internal server error (simulated).",
                type = "all_upstreams_failed"
            ),
            httpStatus = 502
        )

        val result = RouteResultMapper.buildRouteResult(outcome, attempts = emptyList())

        assertFalse(result.success)
        assertEquals("所有候选上游均不可用，请稍后再试。", result.errorMessage)
    }

    @Test
    fun failureFallsBackToStatusHint() {
        val outcome = GatewayCallOutcome(requestId = "req-4", error = null, httpStatus = 504)

        val result = RouteResultMapper.buildRouteResult(outcome)

        assertFalse(result.success)
        assertEquals("请求超时，已尝试全部候选上游。", result.errorMessage)
    }

    @Test
    fun requestIdAndUpstreamFallBackToAttempts() {
        // 响应头缺失时，从尝试记录补齐请求 ID 与最终上游
        val outcome = GatewayCallOutcome(replyText = "ok")
        val attempts = listOf(
            attempt("req-9", 1, "mock-ok", "success", 200)
        )

        val result = RouteResultMapper.buildRouteResult(outcome, attempts)

        assertEquals("req-9", result.requestId)
        assertEquals("mock-ok", result.finalUpstream)
        assertTrue(result.success)
    }
}
