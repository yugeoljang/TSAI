# Personal Gateway Plus - Web 管理端

Vue 3 + TypeScript + Element Plus 管理端，默认开发地址为 `http://127.0.0.1:5173`。

## 已实现

Web 管理端用于可视化管理网关配置与查看请求记录：

- **供应商管理**：增删改查供应商与上游 API（`/api/admin/providers`、`/api/admin/upstreams`）
- **分组路由**：配置 API 分组与成员优先级（`/api/admin/groups`）
- **模型与价格**：查看模型目录与价格快照（`/api/admin/models`、`/api/admin/prices`）
- **活动通知**：查看促销活动（`/api/admin/promotions`）
- **请求历史**：查看网关请求与故障切换轨迹（`/api/admin/requests`）

## 启动

```powershell
cd web
npm.cmd ci
npm.cmd run dev
```

开发服务器会把 `/api`、`/v1` 和 `/health` 转发到 `http://127.0.0.1:8000`。

## 对接后端

- 后端地址：`http://127.0.0.1:8000`
- API 文档：`http://127.0.0.1:8000/docs`
- 接口契约：`../contracts/openapi.yaml`
- 右上角 Mock 开关默认在开发环境开启；真实联调时需要关闭。
- CORS：后端默认允许全部来源（仅限本机初版，后续需收紧）。

## 构建检查

```powershell
npm.cmd run build
```
