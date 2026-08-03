# 项目文档索引

本目录保存跨 Android、Web、后端与运维的长期设计。根目录 `README.md` 继续描述
当前已经能够运行的 Android 应用；尚未实现的能力统一写在这里，避免把规划当成现状。

## Personal Gateway Plus

- [产品与总体架构](personal-gateway-plus/README.md)
- [模块、领域模型与自动路由](personal-gateway-plus/MODULES.md)
- [开发路线图与协作拆分](personal-gateway-plus/ROADMAP.md)

## 文档维护约定

- 接口、数据模型或验收规则变化时，同一个 PR 必须同步更新文档。
- 已确定的重要技术决策记录背景、选择、替代方案与后果。
- 规划功能使用“计划/提案”，只有完成测试的能力才能标记为“已实现”。
- API 契约最终以计划新增的 `contracts/openapi.yaml` 为准。

