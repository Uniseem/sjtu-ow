# 256: M11 完成：割接演练流水线、全栈端到端新旧兼容与对拍工具 (Parity Check & Cutover Rehearsal)

## 做了什么

1. **新旧对拍与兼容性核验工具 (`server/internal/ops/parity.go`)**：
   - 依据 `docs/rewrite-research/12-architecture.md` 第 8.2 节「兼容项清单」与第 9 节实现统一核验执行器 `ParityChecker`；
   - **签名凭据兼容性**：核验日历订阅 ICS 签名 URL（`agenda.CalendarSalt`）与邮件退订签名 URL（`notify.UnsubscribeSalt`），确保与 Django `djsign` 算法及存量链接完全互通；
   - **用户密码哈希兼容性**：核验 Argon2id 密码哈希生成与校验，核验 Django PBKDF2 存量密码哈希验证与登录自动升级标记（`rehash`）；
   - **文章正文渲染结构**：抽样校验 `goldmark` 渲染管线、标题降级锚点抽取（`h-1`, `h-2`...）、字数统计与最少 1 分钟阅读时长计算；
   - **图片与媒体可达性**：扫描数据库 `images` 表与所有文章/站点页面正文中的图片引用，验证本地磁盘与 HTTP 可达性；
   - **端点路由对拍**：核验 16 个核心公开页面（首页、关于、章程、加入、资讯、赛事、内战、成员、战队、登录、注册、健康探针等）HTTP 状态码（200）、标题品牌前缀与基本链接；
   - 接入 `server/cmd/sjtuow/main.go` 挂载 `sjtuow parity` 子命令，支持 `--new-url`、`--legacy-url`、`--media-dir`、`--signing-key` 与 `--json` 输出。

2. **全库对账与数据自检增强 (`server/internal/ops/reconcile.go`)**：
   - 增加按状态分组的业务领域指标汇总（文章已发布/草稿、赛事进行中/开启报名、内战进行中/开放、战队活跃/解散、赛事报名已确认/待审核、评论正常/置顶/隐藏）；
   - 扩展新旧库关键实体抽样对比：除超级管理员外，增加文章标题/Slug 与战队名称跨库比对；
   - 提供更加直观的标准终端报告与综合状态标记。

3. **割接模拟演练流水线脚本 (`deploy/rehearse.sh`)**：
   - 依据 12 号文档 8.4 节规范，构建非破坏性 staging 全流程演练工具；
   - 自动化串联：历史库快照镜像 -> 表结构构建 (`migrate`) -> 全领域存量导入 (`import`) -> 完整性对账 (`reconcile`) -> 契约审计与对拍 (`rulecheck` & `parity`)；
   - 逐项精确计时并输出耗时表格，测算全流程耗时是否在 900 秒（15 分钟）停机窗口预算之内；
   - 更新割接剧本 `docs/cutover.md`，将全真演练作为割接前置必备步骤写入剧本。

4. **单元与集成测试**：
   - `server/internal/ops/parity_test.go`：测试签名与密码兼容性、文章渲染以及基于 `httptest` 的端点路由对拍；
   - `server/internal/ops/reconcile_test.go`：测试数据库一致性自检、多领域分组统计与对账报告输出。

## 验证

在测试机 `sjtu-ow-test` 上运行整组检查 `scripts/remote-check.sh`：
- Go：gofmt、go vet、staticcheck、govulncheck（0 漏洞）全过；
- Go 单测：`go test ./...` 全包通过；
- Web 前端：`pnpm test` 通过，包含单测、客户端与 SSR 构建成功、体积预算合格。
