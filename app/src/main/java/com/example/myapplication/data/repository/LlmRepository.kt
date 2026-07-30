package com.example.myapplication.data.repository

import com.example.myapplication.data.model.Channel
import com.example.myapplication.data.model.LlmModel
import com.example.myapplication.data.model.ModelProvider
import com.example.myapplication.data.model.PriceNews
import com.example.myapplication.data.remote.ApiService

class LlmRepository(private val apiService: ApiService) {

    suspend fun getProviders(): Result<List<ModelProvider>> = runCatching {
        apiService.getProviders()
    }

    suspend fun getProvider(id: String): Result<ModelProvider> = runCatching {
        apiService.getProvider(id)
    }

    suspend fun getChannels(providerId: String): Result<List<Channel>> = runCatching {
        apiService.getChannels(providerId)
    }

    suspend fun getModels(providerId: String? = null): Result<List<LlmModel>> = runCatching {
        apiService.getModels(providerId)
    }

    suspend fun getNews(
        providerId: String? = null,
        type: String? = null
    ): Result<List<PriceNews>> = runCatching {
        apiService.getNews(providerId, type)
    }
}