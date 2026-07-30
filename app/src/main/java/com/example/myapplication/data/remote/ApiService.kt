package com.example.myapplication.data.remote

import com.example.myapplication.data.model.Channel
import com.example.myapplication.data.model.LlmModel
import com.example.myapplication.data.model.ModelProvider
import com.example.myapplication.data.model.PriceNews
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

interface ApiService {

    @GET("providers")
    suspend fun getProviders(): List<ModelProvider>

    @GET("providers/{id}")
    suspend fun getProvider(@Path("id") id: String): ModelProvider

    @GET("providers/{id}/channels")
    suspend fun getChannels(@Path("id") providerId: String): List<Channel>

    @GET("models")
    suspend fun getModels(
        @Query("providerId") providerId: String? = null
    ): List<LlmModel>

    @GET("news")
    suspend fun getNews(
        @Query("providerId") providerId: String? = null,
        @Query("type") type: String? = null
    ): List<PriceNews>
}