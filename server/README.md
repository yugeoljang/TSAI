# Personal Gateway Plus 本地后端

正式后端使用 FastAPI + SQLite，监听 `127.0.0.1:8000`。`src/` 下的 Node 实现仅保留为任务 B 的算法回归测试，不是 Web/Android 的启动入口。

## Windows 启动

需要 Python 3.12 或更高版本。启动脚本会依次寻找项目 `.tools` 运行时、Windows `py` 启动器和 `python` 命令。

```powershell
cd server
.\run.bat
```

首次运行会创建 `.venv`、安装 `requirements.txt` 并从 `.env.example` 复制 `.env`。正式添加 API Key 前必须在 `.env` 中设置固定主密钥：

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

把输出的 64 位十六进制字符串填写到：

```text
GATEWAY_MASTER_KEY=这里填写生成的字符串
```

后端地址与接口文档：

- 服务：`http://127.0.0.1:8000`
- Swagger：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`
- 网关入口：`POST http://127.0.0.1:8000/v1/chat/completions`

## 模拟上游

另开一个终端：

```powershell
cd server
.\run_mock.bat
```

模拟服务监听 `127.0.0.1:8100`，在 Web 中新增上游时填写：

```text
Base URL: http://127.0.0.1:8100
API Key: 任意测试字符串
模型名: mock-model
```

浏览器打开 `http://127.0.0.1:8100` 可以切换 normal、timeout、429、500、400。timeout 会延迟约 3 秒后返回 408，网关会继续尝试下一上游。

## Web 联调

```powershell
cd web
npm.cmd ci
npm.cmd run dev
```

打开 `http://127.0.0.1:5173`，关闭右上角“Mock 模式”后即可使用真实 FastAPI 后端。

## 测试

FastAPI/SQLite：

```powershell
cd server
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

遗留 Node 路由算法回归测试：

```powershell
cd server
node --test
```

Web 与 Android：

```powershell
cd web
npm.cmd run build

cd ..
.\gradlew.bat testDebugUnitTest
```

## 已知边界

- 仅支持单用户、本机运行，不要绑定公网地址。
- Chat Completions 仅支持 `stream=false`。
- `model` 字段填写 API 分组的 `routeKey`，每个成员映射自己的真实模型名。
- 连接失败、超时、408、429、5xx 会按优先级切换；其他 4xx 不切换。
- 默认最多尝试分组配置的 `maxAttempts` 个上游。
