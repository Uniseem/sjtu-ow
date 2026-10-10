# SJTU-OW（上海交通大学守望先锋社区网站）

社区网站，包含文章、成员、战队、赛事和内战。现行站采用 Django 6 / Wagtail 8 / Python 3.13，前台 SSR + HTMX + Alpine CSP；新栈采用 Vue 3 + Go，在同一仓库逐步迁移。当前运行版本、开发进度和下一步只看 [STATUS](handoff/STATUS.md)。

## 从这里开始

| 要做什么 | 入口 |
|---|---|
| 参与开发 / 让编码助手开工 | [AGENTS.md](AGENTS.md) → [当前状态](handoff/STATUS.md) → [轮次流程](handoff/README.md)与[改动范围](handoff/OWNERSHIP.md) |
| 找设计、规格或维护文档 | [文档导航](docs/README.md)，按任务读相关章节 |
| 开发、构建和测试新栈 | [开发与验收](docs/development.md)，所有编译和检查先在测试机后台运行 |
| 运行或使用 Django 旧站 | [旧站使用与运行手册](docs/legacy-guide.md)：本地开发、账号/后台、业务功能与运维命令 |
| 连接机器、部署、备份与恢复 | [机器与运维](docs/operations.md)；新栈割接另读 [cutover.md](docs/cutover.md) |
| 查复核风险、技术陷阱、历史依据 | [独立复核指南](handoff/REVIEW-GUIDE.md)、[踩坑记录](docs/pitfalls.md)、[各轮报告](handoff/rounds/) |

## 代码入口

- `server/`：Go 服务、worker、迁移和 `sjtuow` 命令。
- `web/`：Vue 工作区、前台 SSR、后台应用与公共组件。
- `e2e/`：新旧页面对拍与 Caddy 验收。
- Django 各应用、`templates/`、`static/`、`assets/`：旧站及迁移参照，冻结保留；模块地图见 [文档导航](docs/README.md)。

## 许可证


本项目按 [PolyForm Strict License 1.0.0](LICENSE.md) 授权。**这不是开源许可证**，简单说：

- **允许**：出于非商业目的使用本软件——个人学习、研究、测试、业余项目，以及教育机构、公益组织、政府机构等的使用
- **不允许**：分发本软件，修改本软件，或者基于它做新的作品
- **商业用途**不在授权范围内
- 法律规定的合理使用（比如为评论、说明问题适当引用）不受这份许可证限制

以上只是帮助理解的概括，以 `LICENSE.md` 原文为准。

`static/vendor/` 下的第三方文件不适用上面的许可证，按各自的许可证授权，见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。
