package com.example.myapplication.ui.assistant

import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.data.local.ApiConfig
import com.example.myapplication.data.local.ProviderSettings
import com.example.myapplication.data.local.normalizeApiConfig
import com.example.myapplication.data.local.validateApiConfig
import com.example.myapplication.data.model.Channel
import com.example.myapplication.data.model.ChatCompletionRequest
import com.example.myapplication.data.model.ChatMessageDto
import com.example.myapplication.data.model.LlmModel
import com.example.myapplication.data.model.ModelProvider
import com.example.myapplication.data.model.PriceNews
import com.example.myapplication.data.remote.NetworkModule
import com.example.myapplication.data.remote.createChatApiService
import com.example.myapplication.data.repository.LlmRepository
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class AgentViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = NetworkModule.apiService?.let(::LlmRepository)
    private val settings = ProviderSettings(application)

    private val _uiState = MutableStateFlow(AgentUiState())
    val uiState: StateFlow<AgentUiState> = _uiState.asStateFlow()

    private val prefs by lazy {
        application.getSharedPreferences("agent_prefs", Context.MODE_PRIVATE)
    }

    init {
        loadEverything()
    }

    fun loadEverything() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val activeRepository = repository

            if (activeRepository == null) {
                showReferenceData("未配置聚合服务，当前显示内置参考数据。")
                return@launch
            }

            val (providersResult, modelsResult, newsResult) = coroutineScope {
                val providers = async { activeRepository.getProviders() }
                val models = async { activeRepository.getModels() }
                val news = async { activeRepository.getNews() }
                Triple(providers.await(), models.await(), news.await())
            }

            val liveProviders = providersResult.getOrNull().orEmpty()
            val liveModels = modelsResult.getOrNull().orEmpty()
            val liveNews = newsResult.getOrNull().orEmpty()
            val livePartCount = listOf(
                liveProviders.isNotEmpty(),
                liveModels.isNotEmpty(),
                liveNews.isNotEmpty()
            ).count { it }

            if (livePartCount == 0) {
                showReferenceData("聚合服务暂时不可用，当前显示内置参考数据。")
                return@launch
            }

            val providers = (liveProviders.ifEmpty { referenceProviders() })
                .map(settings::applyToProvider)
            val dataMode = if (livePartCount == 3) DataMode.LIVE else DataMode.MIXED
            _uiState.value = _uiState.value.copy(
                isLoading = false,
                providers = providers,
                models = liveModels.ifEmpty { referenceModels() },
                news = liveNews.ifEmpty { referenceNews() },
                activeProvider = selectActiveProvider(providers),
                lastNewsRefreshAt = if (liveNews.isNotEmpty()) {
                    System.currentTimeMillis()
                } else {
                    null
                },
                dataMode = dataMode,
                dataMessage = if (dataMode == DataMode.LIVE) {
                    "实时数据：价格、渠道和通知均来自已配置的聚合服务。"
                } else {
                    "混合数据：部分接口不可用，参考数据已明确标注。"
                },
                error = if (dataMode == DataMode.MIXED) {
                    "部分聚合接口请求失败，已保留可用数据。"
                } else {
                    null
                }
            )
        }
    }

    fun refreshNews() {
        val activeRepository = repository
        if (activeRepository == null) {
            _uiState.value = _uiState.value.copy(
                error = "当前未配置聚合服务，参考通知不会伪装成实时刷新。"
            )
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isNewsLoading = true, error = null)
            val result = activeRepository.getNews()
            val news = result.getOrNull().orEmpty()

            if (news.isNotEmpty()) {
                _uiState.value = _uiState.value.copy(
                    isNewsLoading = false,
                    news = news,
                    lastNewsRefreshAt = System.currentTimeMillis(),
                    dataMode = if (_uiState.value.dataMode == DataMode.LIVE) {
                        DataMode.LIVE
                    } else {
                        DataMode.MIXED
                    },
                    error = null
                )
            } else {
                _uiState.value = _uiState.value.copy(
                    isNewsLoading = false,
                    error = "刷新通知失败，已保留原有内容。"
                )
            }
        }
    }

    fun setActiveProvider(provider: ModelProvider) {
        settings.setActiveProvider(provider.id)
        _uiState.value = _uiState.value.copy(activeProvider = provider)
    }

    fun saveApiConfig(provider: ModelProvider, config: ApiConfig): Boolean {
        val normalized = normalizeApiConfig(config)
        validateApiConfig(normalized)?.let { message ->
            _uiState.value = _uiState.value.copy(error = message)
            return false
        }

        return runCatching {
            settings.saveApiConfig(provider.id, normalized)
            val updated = provider.copy(
                apiBaseUrl = normalized.baseUrl.takeIf { it.isNotBlank() },
                apiKey = normalized.apiKey,
                chatModel = normalized.model.takeIf { it.isNotBlank() },
                supportsOpenAiChat = normalized.baseUrl.isNotBlank()
            )
            val newList = _uiState.value.providers.map {
                if (it.id == provider.id) updated else it
            }
            _uiState.value = _uiState.value.copy(
                providers = newList,
                activeProvider = if (_uiState.value.activeProvider?.id == provider.id) {
                    updated
                } else {
                    _uiState.value.activeProvider
                },
                error = null
            )
            true
        }.getOrElse {
            _uiState.value = _uiState.value.copy(
                error = "API 配置未保存：设备安全存储不可用。"
            )
            false
        }
    }

    fun sendMessage(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty() || _uiState.value.isAgentThinking) return

        viewModelScope.launch {
            val userMessage = ChatMessage(role = "user", content = trimmed)
            val conversation = _uiState.value.chatMessages + userMessage
            _uiState.value = _uiState.value.copy(
                chatMessages = conversation,
                isAgentThinking = true,
                error = null
            )

            val active = _uiState.value.activeProvider
            val hasCompleteConfig = active != null &&
                !active.apiBaseUrl.isNullOrBlank() &&
                !active.apiKey.isNullOrBlank() &&
                !active.chatModel.isNullOrBlank()

            val reply = if (hasCompleteConfig) {
                callRealApi(active!!, conversation)
            } else {
                generateLocalReply(trimmed, _uiState.value)
            }

            _uiState.value = _uiState.value.copy(
                chatMessages = _uiState.value.chatMessages + reply,
                isAgentThinking = false
            )
        }
    }

    fun clearChat() {
        _uiState.value = _uiState.value.copy(chatMessages = emptyList())
    }

    fun markNewsAsRead(newsId: String) {
        prefs.edit().putBoolean("read_$newsId", true).apply()
    }

    fun isNewsRead(newsId: String): Boolean =
        prefs.getBoolean("read_$newsId", false)

    private suspend fun callRealApi(
        provider: ModelProvider,
        conversation: List<ChatMessage>
    ): ChatMessage {
        return try {
            val service = createChatApiService(provider.apiBaseUrl!!, provider.apiKey!!)
            val history = conversation.takeLast(12).map { message ->
                ChatMessageDto(
                    role = if (message.role == "user") "user" else "assistant",
                    content = message.content
                )
            }
            val request = ChatCompletionRequest(
                model = provider.chatModel!!,
                messages = listOf(
                    ChatMessageDto("system", buildSystemPrompt(provider, _uiState.value))
                ) + history
            )
            val response = service.chatCompletions(request)
            val content = response.choices.firstOrNull()?.message?.content
                ?: response.error?.let { "[${it.type}] ${it.message}" }
                ?: "（服务未返回有效内容）"
            ChatMessage(role = "agent", content = content)
        } catch (e: retrofit2.HttpException) {
            val hint = when (e.code()) {
                401 -> "API Key 无效或已过期，请检查设置。"
                403 -> "API Key 没有调用该模型的权限。"
                404 -> "接口或模型不存在，请检查 Base URL 和模型名。"
                429 -> "请求过于频繁，请稍后再试。"
                in 500..599 -> "服务端暂时不可用（${e.code()}）。"
                else -> "HTTP 错误：${e.code()} ${e.message()}"
            }
            _uiState.value = _uiState.value.copy(error = hint)
            ChatMessage(
                role = "agent",
                content = "调用 ${provider.name} 失败：$hint\n\n本地参考回复：\n${
                    generateLocalReply(conversation.last().content, _uiState.value).content
                }"
            )
        } catch (e: Exception) {
            val hint = e.message?.take(160) ?: "未知错误"
            _uiState.value = _uiState.value.copy(
                error = "调用 ${provider.name} 失败：$hint"
            )
            ChatMessage(
                role = "agent",
                content = "真实 API 调用失败，已提供本地参考回复：\n${
                    generateLocalReply(conversation.last().content, _uiState.value).content
                }"
            )
        }
    }

    private fun buildSystemPrompt(provider: ModelProvider, state: AgentUiState): String {
        val prices = state.models.take(8).joinToString("\n") {
            "- ${it.name}: 输入 ${it.inputPricePerMillionTokens ?: "-"} ${it.currency}," +
                " 输出 ${it.outputPricePerMillionTokens ?: "-"} ${it.currency} / 100万 tokens;" +
                " 更新 ${it.updatedAt ?: "未知"}; 来源 ${it.priceSourceUrl ?: "未提供"}"
        }
        val channels = state.providers.flatMap { it.channels }.take(8).joinToString("\n") {
            "- ${it.name}: ${it.link}"
        }
        val news = state.news.take(5).joinToString("\n") {
            "- [${it.type}] ${it.title}"
        }
        return """
            你是 AI 大模型价格与渠道助手。当前用户使用 ${provider.name} (${provider.chatModel})。
            根据下方数据回答价格、渠道和优惠问题。所有价格统一为每 100 万 tokens。
            数据可能变化，回答时必须说明更新时间，并建议用户在来源页确认最终价格。
            如果当前是参考数据，不得声称它是实时数据。

            【模型价格】
            $prices

            【官方渠道】
            $channels

            【通知】
            $news
        """.trimIndent()
    }

    private fun generateLocalReply(input: String, state: AgentUiState): ChatMessage {
        val lower = input.lowercase()
        return when {
            lower.contains("价格") || lower.contains("price") ||
                lower.contains("多少钱") || lower.contains("比价") -> {
                val lines = state.models.take(6).joinToString("\n") {
                    "• ${it.name}: 输入 ${it.inputPricePerMillionTokens ?: "-"}，" +
                        "输出 ${it.outputPricePerMillionTokens ?: "-"} ${it.currency}/100万 tokens" +
                        "（更新：${it.updatedAt ?: "未知"}）"
                }
                ChatMessage(
                    role = "agent",
                    content = "当前${state.dataMode.displayName}价格参考：\n$lines\n\n" +
                        "价格会变化，请点击模型卡片中的官方来源确认。"
                )
            }

            lower.contains("优惠") || lower.contains("折扣") ||
                lower.contains("discount") || lower.contains("福利") -> {
                val lines = state.news.take(5).joinToString("\n") {
                    "• ${it.title}"
                }
                ChatMessage(
                    role = "agent",
                    content = "当前通知：\n$lines\n\n参考模式中的通知仅用于界面演示。"
                )
            }

            lower.contains("入口") || lower.contains("链接") ||
                lower.contains("渠道") || lower.contains("购买") -> {
                val lines = state.providers.flatMap { it.channels }.take(8).joinToString("\n") {
                    "• ${it.name}: ${it.link}"
                }
                ChatMessage(role = "agent", content = "官方渠道：\n$lines")
            }

            else -> ChatMessage(
                role = "agent",
                content = "我是 AI 大模型比价助手。你可以问：\n" +
                    "1. 对比当前模型价格\n2. 查看官方购买渠道\n3. 查询价格来源和更新时间\n\n" +
                    "当前使用${state.dataMode.displayName}；配置有效 API Key 后可调用真实 AI。"
            )
        }
    }

    private fun showReferenceData(message: String) {
        val providers = referenceProviders().map(settings::applyToProvider)
        _uiState.value = _uiState.value.copy(
            isLoading = false,
            providers = providers,
            models = referenceModels(),
            news = referenceNews(),
            activeProvider = selectActiveProvider(providers),
            lastNewsRefreshAt = null,
            dataMode = DataMode.REFERENCE,
            dataMessage = "$message 价格核对日期：2026-07-29；最终价格以官方来源为准。",
            error = null
        )
    }

    private fun selectActiveProvider(providers: List<ModelProvider>): ModelProvider? {
        val activeId = settings.getActiveProviderId()
        return providers.find { it.id == activeId }
            ?: providers.firstOrNull {
                !it.apiBaseUrl.isNullOrBlank() &&
                    !it.apiKey.isNullOrBlank() &&
                    !it.chatModel.isNullOrBlank()
            }
            ?: providers.firstOrNull { it.id == "deepseek" }
            ?: providers.firstOrNull()
    }

    private fun referenceProviders(): List<ModelProvider> = listOf(
        ModelProvider(
            id = "deepseek",
            name = "DeepSeek",
            websiteUrl = "https://www.deepseek.com",
            apiBaseUrl = "https://api.deepseek.com",
            chatModel = "deepseek-v4-flash",
            supportsOpenAiChat = true,
            channels = listOf(
                Channel(
                    "deepseek-platform",
                    "DeepSeek 开放平台",
                    "official",
                    "https://platform.deepseek.com",
                    "API Key、充值和调用记录"
                ),
                Channel(
                    "deepseek-pricing",
                    "DeepSeek 官方定价",
                    "official",
                    DEEPSEEK_PRICING_URL,
                    "模型价格与计费规则"
                )
            )
        ),
        ModelProvider(
            id = "siliconflow",
            name = "硅基流动 (SiliconFlow)",
            websiteUrl = "https://www.siliconflow.cn",
            apiBaseUrl = "https://api.siliconflow.cn/v1",
            chatModel = "Qwen/Qwen2.5-72B-Instruct",
            supportsOpenAiChat = true,
            channels = listOf(
                Channel(
                    "siliconflow-models",
                    "硅基流动模型广场",
                    "official",
                    "https://cloud.siliconflow.cn/models",
                    "查看可用模型、实时价格与限速"
                ),
                Channel(
                    "siliconflow-console",
                    "硅基流动控制台",
                    "official",
                    "https://cloud.siliconflow.cn",
                    "创建 API Key 和充值"
                )
            )
        ),
        ModelProvider(
            id = "openai",
            name = "OpenAI",
            websiteUrl = "https://openai.com",
            apiBaseUrl = "https://api.openai.com/v1",
            supportsOpenAiChat = true,
            channels = listOf(
                Channel(
                    "openai-platform",
                    "OpenAI API 平台",
                    "official",
                    "https://platform.openai.com",
                    "请在设置中填写当前可用模型名"
                )
            )
        ),
        ModelProvider(
            id = "alibaba",
            name = "阿里云百炼（千问）",
            websiteUrl = "https://bailian.console.aliyun.com",
            channels = listOf(
                Channel(
                    "alibaba-pricing",
                    "阿里云百炼官方定价",
                    "official",
                    QWEN_PRICING_URL,
                    "价格、阶梯计费和活动说明"
                )
            )
        ),
        ModelProvider(
            id = "anthropic",
            name = "Anthropic",
            websiteUrl = "https://www.anthropic.com",
            channels = listOf(
                Channel(
                    "anthropic-console",
                    "Anthropic Console",
                    "official",
                    "https://console.anthropic.com",
                    "当前版本未适配原生 Messages API"
                )
            )
        ),
        ModelProvider(
            id = "google",
            name = "Google Gemini",
            websiteUrl = "https://ai.google.dev",
            channels = listOf(
                Channel(
                    "google-ai-studio",
                    "Google AI Studio",
                    "official",
                    "https://aistudio.google.com",
                    "当前版本未适配原生 Gemini API"
                )
            )
        )
    )

    private fun referenceModels(): List<LlmModel> = listOf(
        LlmModel(
            id = "deepseek-v4-flash",
            providerId = "deepseek",
            name = "DeepSeek-V4-Flash",
            contextWindow = 1_000_000,
            inputPricePerMillionTokens = 0.14,
            outputPricePerMillionTokens = 0.28,
            currency = "USD",
            tier = "standard",
            priceSourceUrl = DEEPSEEK_PRICING_URL,
            updatedAt = "2026-07-29",
            priceNote = "输入价格采用缓存未命中价；缓存命中价格以官方页面为准。"
        ),
        LlmModel(
            id = "deepseek-v4-pro",
            providerId = "deepseek",
            name = "DeepSeek-V4-Pro",
            contextWindow = 1_000_000,
            inputPricePerMillionTokens = 0.435,
            outputPricePerMillionTokens = 0.87,
            currency = "USD",
            tier = "pro",
            priceSourceUrl = DEEPSEEK_PRICING_URL,
            updatedAt = "2026-07-29",
            priceNote = "输入价格采用缓存未命中价；缓存命中价格以官方页面为准。"
        ),
        LlmModel(
            id = "qwen3.7-max-2026-06-08",
            providerId = "alibaba",
            name = "千问 3.7 Max",
            contextWindow = 1_000_000,
            inputPricePerMillionTokens = 12.0,
            outputPricePerMillionTokens = 36.0,
            currency = "CNY",
            tier = "pro",
            priceSourceUrl = QWEN_PRICING_URL,
            updatedAt = "2026-07-29",
            priceNote = "华北2（北京）原价，不包含限时活动折扣。"
        )
    )

    private fun referenceNews(): List<PriceNews> = listOf(
        PriceNews(
            id = "demo-price-change",
            providerId = "demo",
            title = "演示｜价格调整通知样式",
            summary = "仅用于展示通知卡片，不代表任何平台正在调价。",
            type = "price_change",
            createdAt = "2026-07-29T00:00:00Z"
        ),
        PriceNews(
            id = "demo-discount",
            providerId = "demo",
            title = "演示｜折扣通知样式",
            summary = "仅用于界面演示；真实优惠必须由聚合服务提供来源和有效期。",
            type = "discount",
            createdAt = "2026-07-29T00:00:00Z"
        )
    )

    private companion object {
        const val DEEPSEEK_PRICING_URL =
            "https://api-docs.deepseek.com/quick_start/pricing/"
        const val QWEN_PRICING_URL =
            "https://help.aliyun.com/zh/model-studio/model-pricing"
    }
}

enum class DataMode(val displayName: String) {
    LIVE("实时数据"),
    MIXED("混合数据"),
    REFERENCE("内置参考数据")
}

data class AgentUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val providers: List<ModelProvider> = emptyList(),
    val models: List<LlmModel> = emptyList(),
    val news: List<PriceNews> = emptyList(),
    val activeProvider: ModelProvider? = null,
    val chatMessages: List<ChatMessage> = emptyList(),
    val isAgentThinking: Boolean = false,
    val isNewsLoading: Boolean = false,
    val lastNewsRefreshAt: Long? = null,
    val dataMode: DataMode = DataMode.REFERENCE,
    val dataMessage: String = "正在确认数据来源…"
)

data class ChatMessage(
    val role: String,
    val content: String,
    val timestamp: Long = System.currentTimeMillis()
)
