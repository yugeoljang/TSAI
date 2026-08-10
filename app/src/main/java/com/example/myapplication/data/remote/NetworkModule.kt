package com.example.myapplication.data.remote

import com.example.myapplication.BuildConfig
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit

object NetworkModule {

    private val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        isLenient = true
    }

    private val okHttpClient: OkHttpClient by lazy {
        OkHttpClient.Builder().apply {
            if (BuildConfig.DEBUG) {
                addInterceptor(
                    HttpLoggingInterceptor().apply {
                        level = HttpLoggingInterceptor.Level.BASIC
                    }
                )
            }
        }
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    val apiService: ApiService? by lazy {
        BuildConfig.AGGREGATOR_BASE_URL.trim()
            .takeIf { it.isNotEmpty() }
            ?.let { baseUrl ->
                Retrofit.Builder()
                    .baseUrl(baseUrl.ensureTrailingSlash())
                    .client(okHttpClient)
                    .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
                    .build()
                    .create(ApiService::class.java)
            }
    }

    /** 聚合网关聊天服务：baseUrl = 聚合根地址 + "v1/"。 */
    val gatewayChatService: GatewayChatService? by lazy {
        BuildConfig.AGGREGATOR_BASE_URL.trim()
            .takeIf { it.isNotEmpty() }
            ?.let { baseUrl ->
                createGatewayChatService("${baseUrl.ensureTrailingSlash()}v1/")
            }
    }
}

private fun String.ensureTrailingSlash(): String =
    if (endsWith("/")) this else "$this/"
