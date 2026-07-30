package com.example.myapplication.data.local

import java.net.URI

fun normalizeApiConfig(config: ApiConfig): ApiConfig = config.copy(
    baseUrl = config.baseUrl.trim().trimEnd('/'),
    apiKey = config.apiKey.trim(),
    model = config.model.trim()
)

fun validateApiConfig(config: ApiConfig): String? {
    val normalized = normalizeApiConfig(config)

    if (normalized.baseUrl.isBlank()) {
        return if (normalized.apiKey.isBlank() && normalized.model.isBlank()) {
            null
        } else {
            "请填写 API Base URL。"
        }
    }

    val uri = runCatching { URI(normalized.baseUrl) }.getOrNull()
        ?: return "API Base URL 格式不正确。"
    if (uri.scheme?.lowercase() != "https" || uri.host.isNullOrBlank()) {
        return "API Base URL 必须是有效的 HTTPS 地址。"
    }

    if (normalized.apiKey.isNotBlank() && normalized.model.isBlank()) {
        return "填写 API Key 后还需要填写模型名。"
    }

    return null
}
