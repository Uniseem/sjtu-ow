# AGENTS.md

SJTU-OW 的编码助手入口。这里放必须常驻的约束；当前状态、具体分工、操作手册和历史证据在各自文档，按任务读取。

## 开工顺序

1. `git status`：共用检出目录轮流工作；发现他人的未提交改动就停下问用户，不提交、不删除。干净时 `git pull --rebase`。
2. 读 [handoff/STATUS.md](handoff/STATUS.md)：当前任务、前台验收表、FE/BE 交接与阻塞。进度只维护这里。
3. 读 [handoff/README.md](handoff/README.md)（轮次流程）和 [handoff/OWNERSHIP.md](handoff/OWNERSHIP.md)（可改范围）。本轮用户授权优先，例外记进 request 和 STATUS，不能当作长期授权。
4. 按 [docs/README.md](docs/README.md) 的任务导航读相关规格；不必通读全部文档、历史轮次或踩坑记录。

## 常驻约束

- 现行站设计依据是 `docs/design.md` 及其前台/后台细节文档；新栈设计写 `docs/design-next.md`、实现规格写 `12-architecture.md`。需要用户拍板的设计变化先问，定了先改文档再改代码。详细权威关系见文档导航。
- 旧站 Django 冻结，是新站对拍参照；对拍全通过前不许删。安全或丢数据修复先问用户，由用户指定谁做；报告写「新站要不要跟」。正式站当前运行状态看 STATUS。
- Claude 前端、GLM 后端，按 OWNERSHIP 的路径表轮流干；越界需求写 FE/BE 表。共享规则不因换助手而改变。`web/packages/api/src/gen/`、`docs/api-reference.md` 只由 `sjtuow apigen` 生成，不手改；页面已读字段只能兼容添加，改名/删除/改含义先交接。
- 按轮次写 request → 实现 → report → review → STATUS；一轮一个中文提交，详细正文、具体模型 Co-authored-by，直接推 main，推后检查对应提交的 CI。提交身份沿用仓库本地 `Uniseem` 配置，不改身份。历史轮次不重写，错处追加更正。
- 所有编译、测试和检查先走测试机，全部放后台、输出写文件；仅测试机连不上时允许本机兜底并在报告说明。提交前整组全绿，专项验收按 [开发与验收](docs/development.md)。报告只写真实结果，未跑写「未验证」。
- 不扩大本轮范围；新增依赖先问用户，并核对许可证（MIT/BSD/Apache 可，GPL/AGPL 不可）。具体代码分层和变异验收要求见开发文档。
- 部署到任何服务器先取得用户授权。正式站有真实数据，绝不用备份整库覆盖；只动本站目录和 Compose 项目，不做全局清理。机器访问与备份操作前读 [运维文档](docs/operations.md)。
- 不提交 `data/`、`backups/`、`media/`、`.env`、`static/css/app.css` 或真实身份/密钥。系统密钥只放环境变量；后台业务密钥按设计加密且不回显。SQLite 写进程逐个 TERM，不批量杀；数据库不直接删，先移走。

## 按任务读取

| 任务 | 必须先读 |
|---|---|
| 新栈前台任何页面或部件 | [frontend-migration.md](docs/frontend-migration.md)，再按导航读设计 13.2、design-details 或 admin |
| Go、API、迁移 | [新栈实现规格](docs/rewrite-research/12-architecture.md)相关章节；业务规则/契约按需 |
| 构建、检查、截图、浏览器、对拍、变异 | [development.md](docs/development.md)对应小节 |
| SSH、部署、备份、恢复、服务器配置 | [operations.md](docs/operations.md)；新栈割接另读 cutover 第 5 节 |
| 独立复核 | [REVIEW-GUIDE.md](handoff/REVIEW-GUIDE.md) |
| 定位旧坑、查当年的决定 | 搜 [pitfalls.md](docs/pitfalls.md) 或相关轮次；历史入口见文档导航 |

## 维护入口

文档职责和更新规则只维护在 [docs/README.md](docs/README.md)。这里不放命令全集、服务器参数、当轮授权经过、版本清单、踩坑长表或历史进度。
