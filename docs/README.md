# 文档导航与维护

按任务找正文；本文件只维护导航、权威关系和落笔位置，不复制进度、规格或操作步骤。编码助手先读 [AGENTS](../AGENTS.md)，开发者从 [仓库 README](../README.md) 进入。

## 事实写在哪里

| 类型 | 唯一维护位置 | 更新时机 |
|---|---|---|
| 当前进度、下一步、阻塞、FE/BE、页面验收状态 | [STATUS](../handoff/STATUS.md) | 每轮结束；未完成事项留在当前表，不埋进历史 |
| 本轮要求、实际输出、自查/独立结论 | [rounds/](../handoff/rounds/) 的 request/report/review | 开工、完工、复核；历史只追加更正 |
| 轮次、提交和交班步骤 | [handoff/README](../handoff/README.md) | 工作流程变化 |
| 文件归属、FE/BE 交接规则 | [OWNERSHIP](../handoff/OWNERSHIP.md) | 用户调整分工；当轮例外不改长期表 |
| 常驻约束、必须先读的入口 | [AGENTS](../AGENTS.md) | 用户调整规则或阅读路径 |
| 开发、工具链、命令与验证方法 | [development](development.md) | 检查入口或运行方式变化；脚本是执行事实 |
| 机器参数、SSH、部署、备份操作边界 | [operations](operations.md) | 机器或操作步骤变化；部署状态仍写 STATUS |
| 旧站功能使用、通用 Django 运行步骤 | [legacy-guide](legacy-guide.md) | 获授权的旧站修复改变使用方法 |
| 踩坑与技术经验 | [pitfalls](pitfalls.md) | 追加有复现依据的条目，注明轮次，按任务搜索 |
| 历史状态快照 | [handoff/archive](../handoff/archive/) | 从 STATUS 移出旧摘要；保留原文并标明不是当前进度 |

一条事实只写一处，其他位置链接到它。入口可以写一句必要约束，详细步骤只在正文维护。旧状态不持续追加在 STATUS；只保留最近 3 轮摘要，超出移入 archive，验收未闭环的事项继续留在当前表。想法/待办理由放 13 号文档，执行状态以 STATUS 为准。

## 设计与规格怎么读

| 任务 / 问题 | 依据与读法 |
|---|---|
| 现行站行为 | [design.md](design.md)相关章节，是现行站主设计；前台细节由 [design-details.md](design-details.md) 与 13.2 补充，后台由 [admin.md](admin.md)补充 |
| 新栈目标和设计变化 | [design-next.md](design-next.md)是新栈 v8.0 草案，割接前不替换现行站设计；变化先写草案，割接合并照其第 8 节 |
| 新栈实现 | [12-architecture.md](rewrite-research/12-architecture.md)相关模块：描述怎么做；与早期 00 计划冲突时以 12 为准 |
| 新栈前台/后台页面验收 | 先读 [frontend-migration.md](frontend-migration.md)：不变量、阶段顺序、逐页验收与完成定义；行为/视觉照现行站主设计和细节，对拍旧代码保留 |
| 业务等价与 API 契约 | [05-business-rules.md](rewrite-research/05-business-rules.md)、[08-contracts.md](rewrite-research/08-contracts.md)；实际接口查看自动生成的 [api-reference.md](api-reference.md) |
| 割接或回滚 | [cutover.md](cutover.md)，先读第 5 节的回滚教训，再读操作章节和运维文档 |
| 独立复核 | [REVIEW-GUIDE](../handoff/REVIEW-GUIDE.md)，技术陷阱按任务搜 pitfalls |
| 当时为什么这样定 | [调研索引](rewrite-research/README.md)、相关轮次；00–11 的早期调查和 [admin-inventory.md](admin-inventory.md)保留原文，发现错误追加更正，不整体改写 |
| 遗留、待拍板、后续实验 | [13-ideas-and-followups.md](rewrite-research/13-ideas-and-followups.md)；当前阻塞和执行结果只写 STATUS |

这些文档属于不同层次：业务目标与批准的设计 → 模块实现规格 → 验收方法 → 实际结果。发现冲突先查相应轮次/用户决定，修正在拥有该事实的文档；不能仅凭代码或一条绿日志改写设计。业务设计变化需要用户拍板时先问，批准后先改设计并记变更版本。本轮仅重排入口，不改变产品设计。

## 仓库代码地图

新栈：`server/` 是 Go 服务、迁移和命令；`web/` 是 Vue 工作区、SSR、UI/shared/styles；`e2e/` 是真 Caddy 和新旧对拍验收。目录归属以 OWNERSHIP 为准。

下面是 Django 对拍参照的模块索引，不授予修改或删除权限。

| 路径 | 内容 |
|---|---|
| `accounts/` | 用户、游戏 ID、段位、联系方式、功能权限（`permissions.can_use`） |
| `content/` | 页面类型、文章分类、投稿、B 站嵌入、sitemap / robots；正文的 Markdown 渲染（`markdown.py`）、后台编辑器（`widgets.py`、`markdown_views.py`）、旧内容转换（`legacy_body.py`，迁移要用） |
| `backoffice/` | 后台（196 起自己写的，`/admin/`）：网址、进门和权限、大类和标签、表单、各页面视图和模板（设计 `docs/admin.md`）。Wagtail 的管理界面挪到 `/wagtail/`，只给超管应急 |
| `core/` | 全站设置、邮件、字体、预渲染、健康检查、备份恢复与运维命令 |
| `teams/` | 战队 |
| `members/` | 成员展示、成员分组（066 轮代替了原来的组队大厅） |
| `tournaments/` | 赛事、报名（`registration.py` 是状态机，含个人报名和临时队伍）、后台审核、`teams_admin.py` 队伍编排页 |
| `integrations/` | 只剩迁移历史。067 删了开放 API 与 Webhook；`tournaments/0004` 依赖它的迁移，包不能删 |
| `scrims/` | 内战、分队算法（`teaming.py`）、拖拽分队页 |
| `moderation/` | AI 内容审核 |
| `search/` | 站内搜索（四类内容的子串匹配） |
| `comments/` | 文章评论（YouTube 式回复串、隐藏、置顶、点赞） |
| `sjtu_ow/settings/` | `base` / `dev` / `prod` |
| `deploy/` | Docker Compose、Caddy、crontab 示例、维护页 |
| `handoff/` | 进度、轮次记录、复核指南 |
| `docs/rewrite-research/` | 重构调研和架构规划（现行站换成 Vue 3 + Go，218 起，入口 `README.md`、总纲 `12-architecture.md`）。进度仍只写 `handoff/STATUS.md` |
| `docs/design-next.md` | 新栈的设计草案 v8.0（221 起；割接前 `docs/design.md` 仍是现行站的设计） |

## 其他随实现维护的文件

新增/修改环境变量同步 `.env.example`；定时任务同步 `deploy/crontab.example`；原样收录或升级第三方文件同步 `THIRD_PARTY_NOTICES.md`。独立复核改变薄弱处判断时更新 REVIEW-GUIDE。自动生成文档与类型只重新生成，不手写。

## 278 轮入口迁移表

历史报告中的旧位置仍可按此找到：AGENTS「Claude 和 GPT 分开做」→ OWNERSHIP；「常用命令」「新栈的命令和检查」→ development；「测试机与部署」「第二台」「每轮升级」→ operations；「已知的坑」→ pitfalls；「改了什么，就更新哪份文档」→ 本文件。原 README 的功能、Django 运行和运维章节 → legacy-guide；STATUS 的旧叙述与旧总表 → archive/status-through-277.md。历史轮次正文不批量重写。
