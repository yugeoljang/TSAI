# Personal Gateway Plus — 后端服务

个人 API 网关，聚合多家 LLM 供应商，支持分组路由、故障切换、价格追踪与活动通知。

## 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Python 3.12+ |
| Web 框架 | FastAPI 0.115 |
| ASGI 服务器 | Uvicorn 0.34 |
| 数据库 | SQLite（aiosqlite 异步驱动） |
| HTTP 客户端 | httpx 0.28（转发上游请求） |
| 加密 | cryptography 44（AES-256-GCM 加密 API Key） |
| 配置 | python-dotenv + 环境变量 |

## 目录结构

```
server/
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI 入口（中间件/CORS/异常/路由/lifespan）
│   ├── config.py          # 配置加载（.env / 环境变量）
│   ├── database.py        # SQLite 连接 + 建表 + 种子数据
│   ├── schema.sql         # 建表 DDL（9 张表）
│   ├── security.py        # API Key AES-GCM 加解密
│   ├── errors.py          # 统一错误格式 + 全局异常处理
│   ├── middleware.py      # 请求 ID 中间件 + 日志脱敏
│   ├── schemas.py         # Pydantic DTO（对齐 OpenAPI 契约）
│   └── routers/
│       ├── health.py          # GET /health                    ✅ 已实现
│       ├── android_compat.py  # Android 兼容查询（5 端点）      ✅ 已实现
│       ├── gateway.py         # POST /v1/chat/completions      🚧 B 骨架
│       ├── providers.py       # 供应商/上游 CRUD               🚧 C 骨架
│       ├── groups.py          # 分组/成员 CRUD                 🚧 C 骨架
│       ├── catalog.py         # 模型/价格/活动查询              🚧 C 骨架
│       └── requests.py        # 路由记录查询                    🚧 C 骨架
├── data/                  # SQLite 数据库文件（自动生成，已 gitignore）
├── .env.example           # 配置模板
├── requirements.txt
├── run.bat                # Windows 一键启动
└── run.sh                 # macOS/Linux 一键启动
```

## 快速启动

### 方式一：一键脚本（推荐）

```bash
# Windows
run.bat

# macOS / Linux
chmod +x run.sh && ./run.sh
```

脚本会自动：创建虚拟环境 → 安装依赖 → 复制 `.env.example` 为 `.env` → 启动服务。

### 方式二：手动

```bash
cd server

# 1. 创建虚拟环境
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 生成主密钥：python -c "import secrets; print(secrets.token_hex(32))"
# 填入 .env 的 GATEWAY_MASTER_KEY

# 4. 启动
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

启动后访问：
- API 文档（Swagger UI）：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health
- Android 兼容接口：http://127.0.0.1:8000/providers

## 配置说明

所有配置通过 `.env` 文件或环境变量读取，详见 `.env.example`：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `GATEWAY_MASTER_KEY` | （空） | API Key 加密主密钥，64 位十六进制。留空用临时密钥（重启后无法解密旧数据） |
| `HOST` | `127.0.0.1` | 监听地址 |
| `PORT` | `8000` | 监听端口 |
| `DATABASE_PATH` | `data/gateway.db` | SQLite 文件路径（相对 server/） |
| `REQUEST_TOTAL_TIMEOUT_SECONDS` | `30` | 单次请求总超时 |
| `UPSTREAM_TIMEOUT_SECONDS` | `15` | 单上游超时 |
| `CORS_ORIGINS` | `*` | 跨域来源，逗号分隔 |

> **安全提示**：生产环境务必设置 `GATEWAY_MASTER_KEY`，否则重启后已加密的 API Key 将无法解密。

## 数据库

- 启动时自动建表（`schema.sql`，9 张表）
- 空库时自动写入种子数据：3 供应商（DeepSeek / SiliconFlow / OpenAI）、8 模型、7 价格快照、3 活动
- 数据库文件位于 `data/gateway.db`，已加入 `.gitignore`
- 使用 `sqlite3 data/gateway.db` 可直接查看数据

## 安全设计

- **API Key 加密**：上游 API Key 使用 AES-256-GCM 加密后存入数据库，永不回显明文
- **响应脱敏**：所有响应只返回 `apiKeyLastFour`（后四位），Android 兼容接口的 `apiKey` 恒为 `null`
- **主密钥**：来自环境变量，不落盘、不进日志
- **日志脱敏**：`Authorization` / `X-API-Key` / `Cookie` 等敏感头在日志中以 `***` 显示

## 已知限制（WEEK1 MVP）

1. **中转路由（B 任务）**：`POST /v1/chat/completions` 目前返回 501 占位，实际转发逻辑待 B 任务实现
2. **管理 CRUD（C 任务）**：`/api/admin/*` 的增删改查端点目前返回 501 占位，待 C 任务实现
3. **仅支持非流式**：`stream=true` 返回 400 `stream_not_supported`
4. **单进程**：使用全局 SQLite 连接，适合本地单用户场景
5. **无认证**：管理接口暂无鉴权，仅限本地运行

## 接口契约

完整 API 定义见 `contracts/openapi.yaml`（OpenAPI 3.0）。

所有错误响应统一格式：
```json
{
  "error": {
    "code": 404,
    "type": "not_found",
    "message": "资源不存在",
    "requestId": "abc123..."
  }
}
```
