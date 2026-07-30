package com.example.myapplication.data.model

private const val TOKENS_PER_MILLION = 1_000_000.0

fun LlmModel.estimateCost(inputTokens: Long, outputTokens: Long): Double? {
    require(inputTokens >= 0) { "inputTokens must be non-negative" }
    require(outputTokens >= 0) { "outputTokens must be non-negative" }
    val inputPrice = inputPricePerMillionTokens ?: return null
    val outputPrice = outputPricePerMillionTokens ?: return null
    return inputTokens / TOKENS_PER_MILLION * inputPrice +
        outputTokens / TOKENS_PER_MILLION * outputPrice
}
