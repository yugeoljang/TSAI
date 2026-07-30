package com.example.myapplication.data.local

import android.content.Context
import android.content.SharedPreferences
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import com.example.myapplication.data.model.ModelProvider
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class ProviderSettings(context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    private val json = Json { ignoreUnknownKeys = true }

    fun saveApiConfig(providerId: String, config: ApiConfig) {
        val normalized = normalizeApiConfig(config)
        val publicConfig = normalized.copy(apiKey = "")
        val editor = prefs.edit()
            .putString("config_$providerId", json.encodeToString(publicConfig))

        if (normalized.apiKey.isBlank()) {
            editor.remove("secret_$providerId")
        } else {
            editor.putString("secret_$providerId", encrypt(normalized.apiKey))
        }
        editor.apply()
    }

    fun getApiConfig(providerId: String): ApiConfig? {
        val raw = prefs.getString("config_$providerId", null) ?: return null
        val stored = runCatching { json.decodeFromString<ApiConfig>(raw) }.getOrNull()
            ?: return null
        val encryptedKey = prefs.getString("secret_$providerId", null)

        if (!encryptedKey.isNullOrBlank()) {
            val apiKey = runCatching { decrypt(encryptedKey) }.getOrDefault("")
            return stored.copy(apiKey = apiKey)
        }

        // One-time migration from the old plaintext JSON format.
        if (stored.apiKey.isNotBlank()) {
            return runCatching {
                saveApiConfig(providerId, stored)
                stored
            }.getOrElse {
                prefs.edit()
                    .putString(
                        "config_$providerId",
                        json.encodeToString(stored.copy(apiKey = ""))
                    )
                    .apply()
                stored.copy(apiKey = "")
            }
        }

        return stored
    }

    fun setActiveProvider(providerId: String) {
        prefs.edit().putString("active_provider_id", providerId).apply()
    }

    fun getActiveProviderId(): String? =
        prefs.getString("active_provider_id", null)

    fun applyToProvider(provider: ModelProvider): ModelProvider {
        val config = getApiConfig(provider.id)
        return provider.copy(
            apiBaseUrl = config?.baseUrl?.takeIf { it.isNotBlank() } ?: provider.apiBaseUrl,
            apiKey = config?.apiKey ?: provider.apiKey,
            chatModel = config?.model?.takeIf { it.isNotBlank() } ?: provider.chatModel
        )
    }

    private fun encrypt(value: String): String {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateSecretKey())
        val iv = Base64.encodeToString(cipher.iv, Base64.NO_WRAP)
        val ciphertext = Base64.encodeToString(
            cipher.doFinal(value.toByteArray(Charsets.UTF_8)),
            Base64.NO_WRAP
        )
        return "$iv:$ciphertext"
    }

    private fun decrypt(value: String): String {
        val parts = value.split(":", limit = 2)
        require(parts.size == 2) { "Invalid encrypted API key" }
        val iv = Base64.decode(parts[0], Base64.NO_WRAP)
        val ciphertext = Base64.decode(parts[1], Base64.NO_WRAP)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(
            Cipher.DECRYPT_MODE,
            getOrCreateSecretKey(),
            GCMParameterSpec(128, iv)
        )
        return String(cipher.doFinal(ciphertext), Charsets.UTF_8)
    }

    private fun getOrCreateSecretKey(): SecretKey {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }

        return KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES,
            ANDROID_KEYSTORE
        ).run {
            init(
                KeyGenParameterSpec.Builder(
                    KEY_ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
                )
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build()
            )
            generateKey()
        }
    }

    private companion object {
        const val PREFS_NAME = "provider_settings"
        const val KEY_ALIAS = "ai_price_assistant_api_key"
        const val ANDROID_KEYSTORE = "AndroidKeyStore"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
    }
}

@Serializable
data class ApiConfig(
    val baseUrl: String = "",
    val apiKey: String = "",
    val model: String = ""
)
