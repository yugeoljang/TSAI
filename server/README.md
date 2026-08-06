# Personal Gateway Plus 本地网关（任务 B）

这是 `WEEK1_MVP.md` 中任务 B 的独立实现，当前使用 Node.js 内置 HTTP、`fetch` 和测试框架，不需要安装第三方依赖。

## 已实现

- `POST /v1/chat/completions` 非流式 OpenAI Chat Completions 代理。
- 使用请求中的 `model` 作为 API 分组 `routeKey`。
- 按 `priority` 从小到大调用已启用的组成员。
- 连接失败、超时、408、429、5xx 和无效上游 JSON 自动尝试下一上游。
- 400、422 和其他 4xx 不自动切换。
- 默认最多尝试 3 个上游，默认单上游超时 10 秒、总超时 25 秒。
- 每次尝试记录请求 ID、顺序、上游、模型、状态、错误类型和耗时。
- 成功响应通过 `x-request-id` 和 `x-gateway-upstream` 返回追踪信息。
- `GET /gateway/route-attempts?requestId=...` 查询内存中的最近尝试。
- `GET /health` 健康检查。

明确不支持：流式响应、熔断、主动健康检查、负载均衡和按最低价选路。

## 本地运行

需要 Node.js 20 或更高版本。

1. 复制 `config/gateway.example.json` 为 `config/gateway.local.json`。
2. 修改两个上游的 Base URL、真实模型名和优先级。
3. 设置示例配置中引用的环境变量：

```powershell
$env:UPSTREAM_PRIMARY_API_KEY = "你的主 API Key"
$env:UPSTREAM_BACKUP_API_KEY = "你的备用 API Key"
```

4. 启动网关：

```powershell
cd server
node src/index.js
```

服务默认只监听 `http://127.0.0.1:8787`，没有登录保护，不应暴露到局域网或公网。

## 调用示例

```powershell
$body = @{
    model = "demo-route"
    messages = @(
        @{ role = "user"; content = "你好" }
    )
    stream = $false
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8787/v1/chat/completions" `
    -ContentType "application/json" `
    -Body $body
```

## 测试

```powershell
cd server
node --test
```

测试使用本机随机端口模拟上游，不需要真实 API Key，覆盖：

- 第一上游成功时不访问备用上游。
- 500、429、超时自动切换。
- 400 不切换。
- 最多尝试三个上游。
- 拒绝 `stream=true`。
- `routeKey` 选择分组并映射真实模型名。
- HTTP 健康检查和 OpenAI 兼容错误结构。

## 与任务 A/C 的接口

路由核心只依赖两个仓库对象：

```text
groupRepository.findEnabledGroupByRouteKey(routeKey)
attemptRepository.record(attempt)
attemptRepository.list({ requestId, limit })
```

C 完成 SQLite 后，只需用数据库仓库替换 `JsonFileGroupRepository` 和 `InMemoryAttemptRepository`。查询得到的分组应包含按下列结构组织的成员：

```json
{
  "id": "group-id",
  "routeKey": "demo-route",
  "enabled": true,
  "members": [
    {
      "id": "member-id",
      "priority": 1,
      "enabled": true,
      "model": "real-upstream-model",
      "upstream": {
        "id": "upstream-id",
        "name": "上游名称",
        "baseUrl": "https://provider.example/v1",
        "apiKey": "由数据层解密后的密钥，仅在服务端内存中存在",
        "enabled": true
      }
    }
  ]
}
```

A 集成时可直接复用 `createGatewayHttpServer`，也可以只调用 `GatewayRouter.route(body)` 后把 `statusCode`、`body` 和 `headers` 写入所选框架的响应。
