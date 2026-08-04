# Personal Gateway Plus - Web 管理端

> 🚧 **WEEK1 MVP 占位**：本目录为 D 类任务（Web 管理页面）预留。
> 后端 API 已就绪，前端待 D 任务实现。

## 规划

Web 管理端用于可视化管理网关配置与查看请求记录：

- **供应商管理**：增删改查供应商与上游 API（`/api/admin/providers`、`/api/admin/upstreams`）
- **分组路由**：配置 API 分组与成员优先级（`/api/admin/groups`）
- **模型与价格**：查看模型目录与价格快照（`/api/admin/models`、`/api/admin/prices`）
- **活动通知**：查看促销活动（`/api/admin/promotions`）
- **请求历史**：查看网关请求与故障切换轨迹（`/api/admin/requests`）

## 对接后端

- 后端地址：`http://127.0.0.1:8000`
- API 文档：`http://127.0.0.1:8000/docs`
- 接口契约：`../contracts/openapi.yaml`
- CORS：后端默认允许全部来源（生产环境需收紧）

## 技术栈（待定）

由 D 类任务负责人确定，候选：React / Vue / Svelte。
