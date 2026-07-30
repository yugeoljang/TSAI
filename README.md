# AI 大模型比价助手（Android）

一个使用 Kotlin 与 Jetpack Compose 开发的 Android 应用，用于查看大模型 API
价格、官方渠道和通知，并可通过 OpenAI Chat Completions 兼容接口调用真实 AI。

## 当前改进

- 所有模型价格统一为“每 100 万 tokens”。
- 每条内置价格显示官方来源、核对日期和计价说明。
- 顶部明确区分“实时数据”“混合数据”和“内置参考数据”。
- 未配置聚合服务时不会把参考数据伪装成实时刷新结果。
- 支持 DeepSeek、SiliconFlow、OpenAI 等 OpenAI Chat Completions 兼容接口。
- 真实 AI 对话携带最近 12 条消息作为上下文。
- API Key 使用 Android Keystore + AES-GCM 加密。
- API Key 不进入系统备份，Authorization 不写入请求日志。
- 仅在 Debug 构建中记录 BASIC 级网络日志。

## 技术栈

- Kotlin
- Jetpack Compose + Material 3
- Retrofit + OkHttp + Kotlinx Serialization
- ViewModel + StateFlow
- Android Keystore

## 项目结构

```text
app/src/main/java/com/example/myapplication/
├── data/
│   ├── local/
│   │   ├── ApiConfigValidator.kt
│   │   └── ProviderSettings.kt
│   ├── model/
│   │   ├── ModelProvider.kt
│   │   └── PricingCalculator.kt
│   ├── remote/
│   │   ├── ApiService.kt
│   │   ├── ChatApiService.kt
│   │   └── NetworkModule.kt
│   └── repository/
│       └── LlmRepository.kt
└── ui/assistant/
    ├── AgentScreen.kt
    ├── AgentViewModel.kt
    └── AgentViewModelFactory.kt
```

## 编译运行

要求：

- JDK 17 或更新版本
- Android SDK 37
- Android Studio

```powershell
.\gradlew.bat testDebugUnitTest lintDebug assembleDebug
```

APK 输出位置：

```text
app/build/outputs/apk/debug/app-debug.apk
```

`local.properties` 是本机生成文件。如果 SDK 路径变化，请使用 Android Studio
重新同步项目，不要把该文件作为交付配置。

## 配置真实 AI

打开应用右上角“API 设置”，选择平台并填写：

- API Base URL：必须是 HTTPS 地址。
- API Key：保存在 Android Keystore 加密存储中。
- 模型名：必须是该平台当前支持的模型 ID。

已提供的兼容配置：

| 平台 | Base URL | 默认模型 |
|---|---|---|
| DeepSeek | `https://api.deepseek.com` | `deepseek-v4-flash` |
| SiliconFlow | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-72B-Instruct` |
| OpenAI | `https://api.openai.com/v1` | 请填写当前可用模型 |

Anthropic 和 Gemini 的原生接口并非 OpenAI Chat Completions 格式，当前版本只展示
其官方渠道，不再声称已经适配它们的原生 API。若使用兼容代理，可以在设置中填写
代理的 HTTPS Base URL 和模型名。

## 聚合服务

聚合服务用于提供价格、渠道和通知。默认不配置聚合服务，此时应用明确显示
“内置参考数据”。

在用户级 `gradle.properties` 中设置：

```properties
AGGREGATOR_BASE_URL=https://your-service.example.com/
```

服务端接口：

| 端点 | 说明 |
|---|---|
| `GET providers` | 平台和渠道 |
| `GET models?providerId=` | 模型价格 |
| `GET news?providerId=&type=` | 价格与优惠通知 |

模型价格统一使用每 100 万 tokens：

```json
{
  "id": "example-model",
  "providerId": "example-provider",
  "name": "Example Model",
  "contextWindow": 1000000,
  "inputPricePerMillionTokens": 1.0,
  "outputPricePerMillionTokens": 4.0,
  "currency": "CNY",
  "tier": "standard",
  "priceSourceUrl": "https://provider.example.com/pricing",
  "updatedAt": "2026-07-29",
  "priceNote": "标准按量价格，不含活动折扣"
}
```

后端必须提供真实来源和更新时间。活动数据还应提供有效期；过期活动不应返回给
客户端。

## 内置参考数据

内置参考数据仅用于离线演示，核对日期为 2026-07-29：

- DeepSeek 价格来源：
  `https://api-docs.deepseek.com/quick_start/pricing/`
- 阿里云百炼价格来源：
  `https://help.aliyun.com/zh/model-studio/model-pricing`
- SiliconFlow OpenAI 兼容调用说明：
  `https://docs.siliconflow.cn/cn/userguide/quickstart`

价格会变化，最终费用以平台官方页面和控制台结算结果为准。

## 安全说明

- 不要把 API Key 写入源码、README、截图或演示视频。
- 发布版不记录请求体和 Authorization。
- `provider_settings.xml` 已排除在云备份和设备迁移之外。
- Web 版本不应把平台 API Key 保存在浏览器，应通过自己的后端代理调用。
