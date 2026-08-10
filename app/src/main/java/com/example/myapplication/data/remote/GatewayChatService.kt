package com.example.myapplication.data.remote

import com.example.myapplication.BuildConfig
import com.example.myapplication.data.model.ChatCompletionRequest
import com.example.myapplication.data.model.ChatCompletionResponse
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import retrofit2.http.Body
import retrofit2.http.POST
import java.util.concurrent.TimeUnit

/**
 * 聚合网关聊天接口（不带客户端 Bearer，上游密钥在服务端）。
 * 返回 [Response] 以便读取 X-Request-Id / X-Upstream 响应头，
 * 并允许解析非 2xx 时网关的 ErrorEnvelope（body().error）。
 */
interface GatewayChatService {

    @POST("chat/completions")
    suspend fun chatCompletions(
        @Body request: ChatCompletionRequest
    ): Response<ChatCompletionResponse>
}

/**
 * 构建网关聊天服务。baseUrl 应为聚合服务根地址 + "v1/"，
 * 例如 http://10.0.2.2:8000/v1/。
 */
fun createGatewayChatService(baseUrl: String): GatewayChatService {
    val clientBuilder = OkHttpClient.Builder()
        .connectTimeout(60, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)

    if (BuildConfig.DEBUG) {
        clientBuilder.addInterceptor(
            HttpLoggingInterceptor().apply {
                redactHeader("Authorization")
                level = HttpLoggingInterceptor.Level.BASIC
            }
        )
    }

    val json = kotlinx.serialization.json.Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        isLenient = true
    }

    return Retrofit.Builder()
        .baseUrl(baseUrl.ensureTrailingSlash())
        .client(clientBuilder.build())
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()
        .create(GatewayChatService::class.java)
}

private fun String.ensureTrailingSlash(): String =
    if (endsWith("/")) this else "$this/"
