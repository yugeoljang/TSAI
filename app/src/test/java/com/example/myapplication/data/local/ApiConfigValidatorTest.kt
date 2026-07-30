package com.example.myapplication.data.local

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ApiConfigValidatorTest {

    @Test
    fun acceptsCompleteHttpsConfigAndNormalizesIt() {
        val config = normalizeApiConfig(
            ApiConfig(
                baseUrl = " https://api.deepseek.com/ ",
                apiKey = " secret ",
                model = " deepseek-v4-flash "
            )
        )

        assertEquals("https://api.deepseek.com", config.baseUrl)
        assertEquals("secret", config.apiKey)
        assertEquals("deepseek-v4-flash", config.model)
        assertNull(validateApiConfig(config))
    }

    @Test
    fun rejectsHttpEndpoint() {
        val error = validateApiConfig(
            ApiConfig(
                baseUrl = "http://api.example.com",
                apiKey = "secret",
                model = "model"
            )
        )

        assertEquals("API Base URL 必须是有效的 HTTPS 地址。", error)
    }

    @Test
    fun requiresModelWhenApiKeyIsPresent() {
        val error = validateApiConfig(
            ApiConfig(
                baseUrl = "https://api.example.com",
                apiKey = "secret",
                model = ""
            )
        )

        assertEquals("填写 API Key 后还需要填写模型名。", error)
    }
}
