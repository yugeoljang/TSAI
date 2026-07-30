package com.example.myapplication.data.local

import android.content.Context
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ProviderSettingsInstrumentedTest {

    @Test
    fun apiKeyIsEncryptedAtRestAndCanBeReadBack() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val settings = ProviderSettings(context)
        val providerId = "security-test"
        val secret = "sk-test-plaintext-must-not-appear"

        try {
            settings.saveApiConfig(
                providerId,
                ApiConfig(
                    baseUrl = "https://api.example.com",
                    apiKey = secret,
                    model = "test-model"
                )
            )

            val rawPreferences = context
                .getSharedPreferences("provider_settings", Context.MODE_PRIVATE)
                .all
                .toString()

            assertFalse(rawPreferences.contains(secret))
            assertEquals(secret, settings.getApiConfig(providerId)?.apiKey)
        } finally {
            context.getSharedPreferences("provider_settings", Context.MODE_PRIVATE)
                .edit()
                .remove("config_$providerId")
                .remove("secret_$providerId")
                .commit()
        }
    }
}
