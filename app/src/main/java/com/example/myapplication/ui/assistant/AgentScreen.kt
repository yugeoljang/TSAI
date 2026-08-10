package com.example.myapplication.ui.assistant

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.myapplication.data.local.ApiConfig
import com.example.myapplication.data.local.normalizeApiConfig
import com.example.myapplication.data.local.validateApiConfig
import com.example.myapplication.data.model.Channel
import com.example.myapplication.data.model.LlmModel
import com.example.myapplication.data.model.ModelProvider
import com.example.myapplication.data.model.RouteResult
import java.text.DecimalFormat

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgentScreen(
    viewModel: AgentViewModel = viewModel(
        factory = AgentViewModelFactory(
            LocalContext.current.applicationContext as android.app.Application
        )
    )
) {
    val uiState by viewModel.uiState.collectAsState()
    var selectedTab by remember { mutableIntStateOf(0) }
    var showSettings by remember { mutableStateOf(false) }
    val tabs = listOf("助手", "模型价格", "渠道入口", "优惠通知")

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("AI 大模型比价助手") },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    titleContentColor = MaterialTheme.colorScheme.onPrimaryContainer
                ),
                actions = {
                    IconButton(
                        onClick = viewModel::loadEverything,
                        enabled = !uiState.isLoading
                    ) {
                        Icon(Icons.Default.Refresh, contentDescription = "刷新数据")
                    }
                    IconButton(onClick = { showSettings = true }) {
                        Icon(Icons.Default.Settings, contentDescription = "API 设置")
                    }
                }
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
        ) {
            ScrollableTabRow(selectedTabIndex = selectedTab) {
                tabs.forEachIndexed { index, title ->
                    Tab(
                        selected = selectedTab == index,
                        onClick = { selectedTab = index },
                        text = { Text(title) }
                    )
                }
            }

            DataStatusBanner(uiState.dataMode, uiState.dataMessage)
            uiState.error?.let { message ->
                ErrorBanner(message, onOpenSettings = { showSettings = true })
            }

            when (selectedTab) {
                0 -> AssistantTab(uiState, viewModel)
                1 -> ModelsTab(uiState.models)
                2 -> ChannelsTab(uiState.providers)
                3 -> NewsTab(uiState, viewModel)
            }
        }

        if (showSettings) {
            ApiSettingsDialog(
                providers = uiState.providers,
                onDismiss = { showSettings = false },
                onSave = viewModel::saveApiConfig
            )
        }
    }
}

@Composable
private fun DataStatusBanner(mode: DataMode, message: String) {
    val colors = when (mode) {
        DataMode.LIVE -> CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        )

        DataMode.MIXED -> CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.tertiaryContainer
        )

        DataMode.REFERENCE -> CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 8.dp),
        colors = colors
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                text = mode.displayName,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.Bold
            )
            Text(message, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun ErrorBanner(message: String, onOpenSettings: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 2.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = message,
                modifier = Modifier.weight(1f),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onErrorContainer
            )
            TextButton(onClick = onOpenSettings) {
                Text("API 设置")
            }
        }
    }
}

@Composable
private fun AssistantTab(uiState: AgentUiState, viewModel: AgentViewModel) {
    var input by remember { mutableStateOf("") }
    val context = LocalContext.current
    Column(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 6.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("路由方式：", style = MaterialTheme.typography.bodyMedium)
                FilterChip(
                    selected = uiState.routeMode == RouteMode.DIRECT,
                    onClick = { viewModel.setRouteMode(RouteMode.DIRECT) },
                    label = { Text(RouteMode.DIRECT.displayName) }
                )
                Spacer(modifier = Modifier.width(8.dp))
                FilterChip(
                    selected = uiState.routeMode == RouteMode.GATEWAY,
                    onClick = { viewModel.setRouteMode(RouteMode.GATEWAY) },
                    label = { Text(RouteMode.GATEWAY.displayName) }
                )
            }
            Spacer(modifier = Modifier.height(4.dp))

            when (uiState.routeMode) {
                RouteMode.DIRECT -> {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("对话平台：", style = MaterialTheme.typography.bodyMedium)
                        var expanded by remember { mutableStateOf(false) }
                        Box {
                            OutlinedButton(onClick = { expanded = true }) {
                                Text(uiState.activeProvider?.name ?: "未选择")
                            }
                            DropdownMenu(
                                expanded = expanded,
                                onDismissRequest = { expanded = false }
                            ) {
                                uiState.providers.forEach { provider ->
                                    val configured = provider.hasCompleteApiConfig()
                                    DropdownMenuItem(
                                        text = {
                                            Text("${provider.name}${if (configured) " ✓" else ""}")
                                        },
                                        onClick = {
                                            viewModel.setActiveProvider(provider)
                                            expanded = false
                                        }
                                    )
                                }
                            }
                        }
                    }
                    val realApi = uiState.activeProvider?.hasCompleteApiConfig() == true
                    Text(
                        text = if (realApi) {
                            "真实 API 已配置；将携带最近 12 条消息作为上下文。"
                        } else {
                            "未完成 API 配置；当前使用本地参考回复。"
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = if (realApi) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.outline
                        }
                    )
                }

                RouteMode.GATEWAY -> {
                    if (uiState.groups.isEmpty()) {
                        Text(
                            "未发现可用分组。请先在服务端运行 setup_demo_group.py，再点右上角刷新。",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.outline
                        )
                    } else {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("API 分组：", style = MaterialTheme.typography.bodyMedium)
                            var expanded by remember { mutableStateOf(false) }
                            Box {
                                OutlinedButton(onClick = { expanded = true }) {
                                    Text(
                                        uiState.selectedGroup?.let { "${it.routeKey} · ${it.name}" }
                                            ?: "选择分组"
                                    )
                                }
                                DropdownMenu(
                                    expanded = expanded,
                                    onDismissRequest = { expanded = false }
                                ) {
                                    uiState.groups.forEach { group ->
                                        DropdownMenuItem(
                                            text = { Text("${group.routeKey} · ${group.name}") },
                                            onClick = {
                                                viewModel.setSelectedGroup(group)
                                                expanded = false
                                            }
                                        )
                                    }
                                }
                            }
                        }
                        val hasGroup = uiState.selectedGroup != null
                        Text(
                            text = if (hasGroup) {
                                "消息经聚合网关自动路由；上游故障时自动切换。"
                            } else {
                                "请选择分组后发送消息。"
                            },
                            style = MaterialTheme.typography.bodySmall,
                            color = if (hasGroup) {
                                MaterialTheme.colorScheme.primary
                            } else {
                                MaterialTheme.colorScheme.outline
                            }
                        )
                    }
                }
            }
        }

        if (uiState.isLoading) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator()
            }
        } else if (uiState.chatMessages.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .padding(24.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    "试试提问：\n“对比当前模型的输入和输出价格”\n“价格数据来自哪里？”",
                    style = MaterialTheme.typography.bodyLarge
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(12.dp),
                reverseLayout = true
            ) {
                if (uiState.routeResult != null) {
                    item {
                        RouteResultCard(
                            result = uiState.routeResult,
                            onCopyRequestId = { id ->
                                val clipboard = context.getSystemService(
                                    Context.CLIPBOARD_SERVICE
                                ) as ClipboardManager
                                clipboard.setPrimaryClip(
                                    ClipData.newPlainText("gateway_request_id", id)
                                )
                                Toast.makeText(context, "已复制请求 ID", Toast.LENGTH_SHORT).show()
                            }
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                }
                if (uiState.isAgentThinking) {
                    item {
                        Text(
                            "正在调用模型…",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.outline
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                }
                items(uiState.chatMessages.asReversed()) { message ->
                    ChatBubble(message)
                    Spacer(modifier = Modifier.height(8.dp))
                }
            }
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                placeholder = { Text("问价格、来源、优惠或渠道…") },
                modifier = Modifier.weight(1f),
                maxLines = 4
            )
            Spacer(modifier = Modifier.width(8.dp))
            IconButton(
                onClick = {
                    viewModel.sendMessage(input)
                    input = ""
                },
                enabled = input.isNotBlank() && !uiState.isAgentThinking
            ) {
                Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "发送")
            }
        }
    }
}

@Composable
private fun ChatBubble(message: ChatMessage) {
    val isUser = message.role == "user"
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        Card(
            shape = RoundedCornerShape(
                topStart = 16.dp,
                topEnd = 16.dp,
                bottomStart = if (isUser) 16.dp else 4.dp,
                bottomEnd = if (isUser) 4.dp else 16.dp
            ),
            colors = CardDefaults.cardColors(
                containerColor = if (isUser) {
                    MaterialTheme.colorScheme.primaryContainer
                } else {
                    MaterialTheme.colorScheme.secondaryContainer
                }
            ),
            modifier = Modifier.fillMaxWidth(0.85f)
        ) {
            Text(
                text = message.content,
                modifier = Modifier.padding(12.dp),
                style = MaterialTheme.typography.bodyMedium
            )
        }
    }
}

@Composable
private fun RouteResultCard(
    result: RouteResult,
    onCopyRequestId: (String) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (result.success) {
                MaterialTheme.colorScheme.surfaceVariant
            } else {
                MaterialTheme.colorScheme.errorContainer
            }
        )
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "路由结果",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.width(8.dp))
                RouteBadge(
                    text = when {
                        result.switched -> "已切换"
                        result.success -> "直连命中"
                        else -> "失败"
                    },
                    color = when {
                        result.switched -> MaterialTheme.colorScheme.tertiary
                        result.success -> MaterialTheme.colorScheme.primary
                        else -> MaterialTheme.colorScheme.error
                    }
                )
            }
            Spacer(modifier = Modifier.height(6.dp))
            if (result.success) {
                result.finalUpstream?.let {
                    Text("最终上游：$it", style = MaterialTheme.typography.bodyMedium)
                }
                Text(
                    "尝试次数：${if (result.attemptCount > 0) result.attemptCount else "未知"}",
                    style = MaterialTheme.typography.bodyMedium
                )
            }
            result.requestId?.let { id ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = "请求 ID：$id",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.outline,
                        modifier = Modifier.weight(1f)
                    )
                    IconButton(onClick = { onCopyRequestId(id) }) {
                        Icon(
                            Icons.Default.ContentCopy,
                            contentDescription = "复制请求 ID",
                            modifier = Modifier.size(16.dp)
                        )
                    }
                }
            }
            result.errorMessage?.let {
                Text(
                    it,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onErrorContainer
                )
            }
        }
    }
}

@Composable
private fun RouteBadge(text: String, color: androidx.compose.ui.graphics.Color) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier
            .background(color.copy(alpha = 0.18f), RoundedCornerShape(6.dp))
            .padding(horizontal = 6.dp, vertical = 2.dp)
    )
}

@Composable
private fun ModelsTab(models: List<LlmModel>) {
    val uriHandler = LocalUriHandler.current
    LazyColumn(
        contentPadding = PaddingValues(12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        items(models, key = { it.id }) { model ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        model.name,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        "上下文：${model.contextWindow?.let(::formatTokenCount) ?: "-"} tokens",
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Text(
                        "输入：${formatPrice(model.inputPricePerMillionTokens)} " +
                            "${model.currency} / 100万 tokens",
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Text(
                        "输出：${formatPrice(model.outputPricePerMillionTokens)} " +
                            "${model.currency} / 100万 tokens",
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Text(
                        "等级：${localizeTier(model.tier)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.outline
                    )
                    model.updatedAt?.let {
                        Text(
                            "价格核对日期：$it",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.outline
                        )
                    }
                    model.priceNote?.let {
                        Text(
                            it,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.outline
                        )
                    }
                    model.priceSourceUrl?.let { source ->
                        TextButton(onClick = { uriHandler.openUri(source) }) {
                            Text("查看官方价格来源 ↗")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ChannelsTab(providers: List<ModelProvider>) {
    val context = LocalContext.current
    LazyColumn(
        contentPadding = PaddingValues(12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        providers.forEach { provider ->
            item(key = "provider-${provider.id}") {
                Text(
                    text = provider.name,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(vertical = 4.dp)
                )
            }
            items(provider.channels, key = { it.id }) { channel ->
                ChannelCard(channel) {
                    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(channel.link)))
                }
            }
        }
    }
}

@Composable
private fun ChannelCard(channel: Channel, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                channel.name,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold
            )
            Text(
                "类型：${if (channel.type == "official") "官方" else channel.type}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.outline
            )
            channel.description?.let {
                Text(it, style = MaterialTheme.typography.bodyMedium)
            }
            Text(
                channel.link,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.primary
            )
        }
    }
}

@Composable
private fun NewsTab(uiState: AgentUiState, viewModel: AgentViewModel) {
    val context = LocalContext.current
    val locale = LocalConfiguration.current.locales[0]
    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            val timeText = when {
                uiState.dataMode == DataMode.REFERENCE -> "参考通知｜不会伪装成实时刷新"
                uiState.lastNewsRefreshAt != null -> {
                    val formatter = java.text.SimpleDateFormat(
                        "MM-dd HH:mm",
                        locale
                    )
                    "更新于 ${formatter.format(java.util.Date(uiState.lastNewsRefreshAt))}"
                }

                else -> "尚未刷新"
            }
            Text(
                text = timeText,
                modifier = Modifier.weight(1f),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.outline
            )
            TextButton(
                onClick = viewModel::refreshNews,
                enabled = !uiState.isNewsLoading && uiState.dataMode != DataMode.REFERENCE
            ) {
                if (uiState.isNewsLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier
                            .width(16.dp)
                            .height(16.dp),
                        strokeWidth = 2.dp
                    )
                } else {
                    Text(if (uiState.dataMode == DataMode.REFERENCE) "参考数据" else "刷新通知")
                }
            }
        }

        LazyColumn(
            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            items(uiState.news, key = { it.id }) { item ->
                val typeColor = when (item.type) {
                    "discount" -> MaterialTheme.colorScheme.tertiary
                    "welfare" -> MaterialTheme.colorScheme.primary
                    else -> MaterialTheme.colorScheme.secondary
                }
                val isRead = viewModel.isNewsRead(item.id)
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    onClick = {
                        viewModel.markNewsAsRead(item.id)
                        item.link?.let { url ->
                            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                        }
                    }
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = localizeNewsType(item.type),
                                color = typeColor,
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold
                            )
                            if (!isRead) {
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    text = "未读",
                                    color = MaterialTheme.colorScheme.error,
                                    style = MaterialTheme.typography.labelSmall
                                )
                            }
                        }
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            item.title,
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold
                        )
                        item.summary?.let {
                            Text(it, style = MaterialTheme.typography.bodyMedium)
                        }
                        item.link?.let {
                            Text(
                                text = "查看原通知 ↗",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.primary
                            )
                        }
                        item.validUntil?.let {
                            Text(
                                "有效期至：$it",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.outline
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ApiSettingsDialog(
    providers: List<ModelProvider>,
    onDismiss: () -> Unit,
    onSave: (ModelProvider, ApiConfig) -> Boolean
) {
    var selectedProvider by remember { mutableStateOf(providers.firstOrNull()) }
    var baseUrl by remember { mutableStateOf(selectedProvider?.apiBaseUrl ?: "") }
    var apiKey by remember { mutableStateOf(selectedProvider?.apiKey ?: "") }
    var model by remember { mutableStateOf(selectedProvider?.chatModel ?: "") }
    var configError by remember { mutableStateOf<String?>(null) }

    fun refreshFields(provider: ModelProvider?) {
        baseUrl = provider?.apiBaseUrl ?: ""
        apiKey = provider?.apiKey ?: ""
        model = provider?.chatModel ?: ""
        configError = null
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("安全 API 设置") },
        text = {
            Column {
                Text(
                    "仅支持 OpenAI Chat Completions 兼容接口。API Key 使用 Android Keystore 加密，不会写入请求日志或系统备份。",
                    style = MaterialTheme.typography.bodySmall
                )
                Spacer(modifier = Modifier.height(8.dp))
                var expanded by remember { mutableStateOf(false) }
                Box {
                    OutlinedButton(
                        onClick = { expanded = true },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(selectedProvider?.name ?: "选择平台")
                    }
                    DropdownMenu(
                        expanded = expanded,
                        onDismissRequest = { expanded = false }
                    ) {
                        providers.forEach { provider ->
                            DropdownMenuItem(
                                text = { Text(provider.name) },
                                onClick = {
                                    selectedProvider = provider
                                    refreshFields(provider)
                                    expanded = false
                                }
                            )
                        }
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = baseUrl,
                    onValueChange = {
                        baseUrl = it
                        configError = null
                    },
                    label = { Text("API Base URL（HTTPS）") },
                    placeholder = { Text("https://api.deepseek.com") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = apiKey,
                    onValueChange = {
                        apiKey = it
                        configError = null
                    },
                    label = { Text("API Key") },
                    visualTransformation = PasswordVisualTransformation(),
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = model,
                    onValueChange = {
                        model = it
                        configError = null
                    },
                    label = { Text("模型名") },
                    placeholder = { Text("例如 deepseek-v4-flash") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
                configError?.let {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = it,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    val provider = selectedProvider ?: return@Button
                    val config = normalizeApiConfig(
                        ApiConfig(baseUrl = baseUrl, apiKey = apiKey, model = model)
                    )
                    val validationError = validateApiConfig(config)
                    if (validationError != null) {
                        configError = validationError
                    } else if (onSave(provider, config)) {
                        onDismiss()
                    } else {
                        configError = "配置保存失败，请检查系统安全设置。"
                    }
                },
                enabled = selectedProvider != null
            ) {
                Text("安全保存")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("取消")
            }
        }
    )
}

private fun ModelProvider.hasCompleteApiConfig(): Boolean =
    !apiBaseUrl.isNullOrBlank() && !apiKey.isNullOrBlank() && !chatModel.isNullOrBlank()

private fun formatPrice(value: Double?): String =
    value?.let { DecimalFormat("0.###").format(it) } ?: "-"

private fun formatTokenCount(value: Int): String =
    DecimalFormat("#,###").format(value)

private fun localizeTier(tier: String): String = when (tier) {
    "pro" -> "专业"
    "discount" -> "优惠"
    else -> "标准"
}

private fun localizeNewsType(type: String): String = when (type) {
    "discount" -> "折扣"
    "welfare" -> "福利"
    else -> "价格调整"
}
