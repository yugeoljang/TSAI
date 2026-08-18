# Personal Gateway Plus

面向个人开发者与 AI Agent 的多上游 API 管理和自动路由网关。项目通过 Web 管理端配置供应商、API 分组、优先级、模型价格与活动信息，并通过 OpenAI Compatible 接口统一对外服务。

> 当前产品范围以 **Web + FastAPI 服务端** 为准；`app/` 中的 Android 工程仅作为历史代码保留，不再作为当前版本的开发和验收对象。

## 已实现能力

- 上游 API 增删改查、密钥加密保存和连接测试；
- API 分组、成员排序和按顺序自动故障切换；
- OpenAI 兼容的 `POST /v1/chat/completions` 非流式接口；
- 请求记录、每次路由尝试、最终上游与失败原因展示；
- 模型目录的新增、编辑、启停、检索和删除；
- 价格快照发布、当前价格、历史版本、来源与核验时间；
- 活动草稿/核验发布/手动结束，以及未开始、进行中、已过期状态；
- Web Mock 模式和 Windows 一键启动。

## 一键启动

首次运行请根据 `server/.env.example` 创建 `server/.env`，并至少配置 `PGP_MASTER_KEY`。

```powershell
cd C:\Users\TSCQ\Desktop\TS
.\start-all.bat
```

使用真实上游且不需要模拟服务时：

```powershell
.\start-all.bat -NoMock
```

旧进程占用 `8000`、`5173` 或 `8100` 端口时：

```powershell
.\start-all.bat -NoMock -Restart
```

启动后访问 [http://127.0.0.1:5173](http://127.0.0.1:5173)，在启动终端按 `Ctrl+C` 可停止所有服务。

## 外部 Agent 接入

| 配置项 | 示例 |
|---|---|
| API 类型 | OpenAI Compatible |
| Base URL | `http://127.0.0.1:8000/v1` |
| API Key | 任意非空本地标识，例如 `local-gateway` |
| Model | 分组的 `routeKey`，例如 `my-test-route` |
| 流式输出 | 关闭 |

网关会把 `model` 解释为分组标识，按组内优先级依次调用上游，并在连接失败、超时、429 或 5xx 时自动切换。

## 价格与活动数据说明

当前已经形成完整的人工维护闭环：模型目录、价格历史、唯一当前价格、官方来源、核验时间、缺失/过期提示，以及活动生命周期管理。数据保存在 SQLite 中，Web 的刷新是读取数据库，**不是每次刷新时抓取供应商官网**。

自动采集需要为每个供应商单独开发采集适配器、定时任务和审核发布流程。目前没有把内置快照伪装成实时数据；正式使用前应以供应商官方页面和账单为准。

## 验证命令

```powershell
cd server
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd ..\web
npm.cmd run typecheck
npm.cmd run build
```

## 主要目录

```text
server/                     # FastAPI 网关、SQLite 数据与服务端测试
web/                        # Vue 3 Web 管理端、Mock 与端到端检查
contracts/openapi.yaml      # 管理接口与网关接口契约
docs/personal-gateway-plus/ # 产品、模块、计划与项目介绍
mock_upstream/              # 可控故障的模拟上游
app/                        # 历史 Android 工程（当前不再开发）
```

详细文档：

- [项目介绍](docs/personal-gateway-plus/PROJECT_INTRODUCTION.md)
- [产品与总体架构](docs/personal-gateway-plus/README.md)
- [模块与自动路由设计](docs/personal-gateway-plus/MODULES.md)
- [开发路线图](docs/personal-gateway-plus/ROADMAP.md)
