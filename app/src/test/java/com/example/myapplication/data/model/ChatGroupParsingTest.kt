package com.example.myapplication.data.model

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ChatGroupParsingTest {

    private val json = Json { ignoreUnknownKeys = true }

    @Test
    fun parsesApiGroupJsonWithUnknownKeys() {
        val raw = """
            {"id":"g1","name":"demo 分组","routeKey":"demo",
             "routingPolicy":"ORDERED_FAILOVER","maxAttempts":3,"enabled":true,
             "createdAt":"2026-08-10T00:00:00Z","updatedAt":"2026-08-10T00:00:00Z"}
        """.trimIndent()

        val group = json.decodeFromString<ChatGroup>(raw)

        assertEquals("g1", group.id)
        assertEquals("demo", group.routeKey)
        assertEquals("demo 分组", group.name)
        assertEquals(3, group.maxAttempts)
        assertTrue(group.enabled)
    }

    @Test
    fun defaultsMissingOptionalFields() {
        val raw = """{"id":"g2","name":"简单分组","routeKey":"k2"}"""

        val group = json.decodeFromString<ChatGroup>(raw)

        assertEquals(3, group.maxAttempts)
        assertEquals("ORDERED_FAILOVER", group.routingPolicy)
        assertTrue(group.enabled)
    }

    @Test
    fun parsesRouteAttemptJson() {
        val raw = """
            {"requestId":"req-1","attemptIndex":2,"upstreamEndpointId":"u2",
             "upstreamDisplayName":"mock-ok","upstreamModelName":"mock-model",
             "startedAt":"2026-08-10T00:00:00Z","endedAt":"2026-08-10T00:00:00Z",
             "resultCategory":"success","upstreamStatusCode":200,"durationMs":12,
             "sanitizedError":null,"retryable":false}
        """.trimIndent()

        val attempt = json.decodeFromString<RouteAttempt>(raw)

        assertEquals("req-1", attempt.requestId)
        assertEquals(2, attempt.attemptIndex)
        assertEquals("mock-ok", attempt.upstreamDisplayName)
        assertEquals("success", attempt.resultCategory)
        assertEquals(200, attempt.upstreamStatusCode)
        assertFalse(attempt.retryable)
    }
}
