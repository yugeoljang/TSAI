package com.example.myapplication.data.model

import org.junit.Assert.assertEquals
import org.junit.Test

class PricingCalculatorTest {

    @Test
    fun estimatesCostUsingPerMillionTokenPrices() {
        val model = LlmModel(
            id = "test",
            providerId = "test",
            name = "Test",
            inputPricePerMillionTokens = 2.0,
            outputPricePerMillionTokens = 8.0,
            currency = "CNY"
        )

        val cost = model.estimateCost(
            inputTokens = 1_000_000,
            outputTokens = 500_000
        )

        assertEquals(6.0, cost!!, 0.0001)
    }
}
