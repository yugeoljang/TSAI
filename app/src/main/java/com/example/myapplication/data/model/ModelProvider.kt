package com.example.myapplication.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ModelProvider(
    val id: String,
    val name: String,
    val logoUrl: String? = null,
    val websiteUrl: String,
    val region: String = "global",
    val channels: List<Channel> = emptyList(),
    // OpenAI-compatible chat configuration. The API key is only populated
    // from encrypted local storage and must never be returned by a backend.
    val apiBaseUrl: String? = null,
    val apiKey: String? = null,
    val chatModel: String? = null,
    val supportsOpenAiChat: Boolean = false
)

@Serializable
data class Channel(
    val id: String,
    val name: String,
    val type: String,
    val link: String,
    val description: String? = null
)

@Serializable
data class LlmModel(
    val id: String,
    val providerId: String,
    val name: String,
    val contextWindow: Int? = null,
    val inputPricePerMillionTokens: Double? = null,
    val outputPricePerMillionTokens: Double? = null,
    val currency: String = "USD",
    val tier: String = "standard",
    val priceSourceUrl: String? = null,
    val updatedAt: String? = null,
    val priceNote: String? = null
)

@Serializable
data class PriceNews(
    val id: String,
    val providerId: String,
    val title: String,
    val summary: String? = null,
    val type: String,
    val link: String? = null,
    val validFrom: String? = null,
    val validUntil: String? = null,
    val createdAt: String
)

@Serializable
data class ChatCompletionRequest(
    val model: String,
    val messages: List<ChatMessageDto>,
    val temperature: Double = 0.7,
    @SerialName("max_tokens")
    val maxTokens: Int = 1024,
    val stream: Boolean = false
)

@Serializable
data class ChatMessageDto(
    val role: String,
    val content: String
)

@Serializable
data class ChatCompletionResponse(
    val id: String? = null,
    val choices: List<ChatChoice> = emptyList(),
    val error: ChatApiError? = null
)

@Serializable
data class ChatChoice(
    val index: Int = 0,
    val message: ChatMessageDto? = null,
    @SerialName("finish_reason")
    val finishReason: String? = null
)

@Serializable
data class ChatApiError(
    val message: String? = null,
    val type: String? = null
)
