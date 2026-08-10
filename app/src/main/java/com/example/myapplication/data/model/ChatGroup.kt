package com.example.myapplication.data.model

import kotlinx.serialization.Serializable

/**
 * API 分组（对齐服务端 ApiGroup，camelCase）。
 * 未知字段（createdAt/updatedAt 等）由反序列化配置忽略。
 */
@Serializable
data class ChatGroup(
    val id: String,
    val name: String,
    val routeKey: String,
    val routingPolicy: String = "ORDERED_FAILOVER",
    val maxAttempts: Int = 3,
    val enabled: Boolean = true
)
