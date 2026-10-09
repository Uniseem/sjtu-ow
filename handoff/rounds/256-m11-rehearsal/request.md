# 256 M11 割接演练流水线、全栈端到端新旧兼容与对拍工具 (Parity Check & Cutover Rehearsal)

## 背景

在 M10 完成了 237 条契约规则全量合规审计、割接剧本（`docs/cutover.md`）与自动化割接脚本（`deploy/cutover.sh`）后，进入 M11（割接演练与上线准备）。
根据 `docs/rewrite-research/12-architecture.md` 第 8.2、8.3、8.4 节与第 9 节要求：
1. **端到端新旧对拍与兼容性工具 (`sjtuow parity`)**：
   - 验证 Section 8.2 兼容项清单（割接后必须「什么都没发生」）：
     - 密码哈希：Argon2id 与 Django PBKDF2 存量兼容验证及登录自动升级触发；
     - 签名链接：`djsign` 算法兼容性，验证日历订阅 ICS 签名 URL 与邮件退订签名 URL；
     - 文章正文 Markdown 渲染：`goldmark` 渲染结构（标题降级、单换行 br、B 站播放器嵌入、表格、字数与阅读时长）；
     - 图片与媒体：正文及数据库中引用的 `/media/images/*` 磁盘可达性与 HTTP 探测；
     - 公开端点与页面标题：规范公开路径 HTTP 状态码（200）与 `<title>` 品牌一致性对拍。
2. **全域对账工具增强 (`sjtuow reconcile`)**：
   - 增加按业务状态分组指标统计（文章发布/草稿、赛事开启/结束、内战开启/结束、战队活跃/解散、报名确认/待审、评论置顶/隐藏）；
   - 扩展关键对象新旧库多维抽样核对（用户、文章、战队）。
3. **割接全真模拟演练流水线 (`deploy/rehearse.sh`)**：
   - 依据 8.4 节规范，在测试机（staging）上无损执行两次全流程演练：
     - 快照镜像 -> 表结构构建 (`migrate`) -> 全域存量导入 (`import`) -> 完整性对账 (`reconcile`) -> 契约审计与对拍 (`rulecheck` & `parity`)；
   - 自动化精确记录每一步耗时，计算停机维护总耗时，验证其在 900 秒（15 分钟）停机窗口预算内。

## 本轮范围

做：
1. `server/internal/ops/parity.go`：
   - 实现 `ParityChecker` 与 `ParityResult`，支持密码兼容、签名兼容、Markdown 渲染、图片引用扫描与路由对拍；
   - 支持格式化终端报告与 `--json` 导出。
2. 接入 `server/cmd/sjtuow/main.go`：
   - 挂载 `sjtuow parity` 子命令与命令行参数。
3. 增强 `server/internal/ops/reconcile.go`：
   - 补齐业务领域多状态分组指标与跨实体抽样对账。
4. 编写割接演练脚本 `deploy/rehearse.sh`：
   - 自动化测算各阶段耗时并评估 15 分钟维护窗口合规性。
5. 更新割接剧本 `docs/cutover.md`。
6. 编写单元与集成测试：
   - `server/internal/ops/parity_test.go`
   - `server/internal/ops/reconcile_test.go`
7. 在测试机上运行整组检查并确保全绿。

不做：
- 生产环境实际停机切换（需等用户确定割接时间）。

## 验收

- `go test -v ./internal/ops/...` 全部通过。
- `sjtuow parity` 执行通过并输出详细兼容项报告。
- `deploy/rehearse.sh` 脚本语法与执行逻辑自洽。
- 测试机整组检查 `scripts/remote-check.sh` 退出码 0。
