# 255 M10 割接准备与契约审计（rulecheck 规则覆盖、数据对账增强、停机割接剧本）报告

## 做了什么

根据 `docs/rewrite-research/12-architecture.md` 8.3、8.4、9 与 11.2：

1. **业务规则契约覆盖审计工具 (`server/internal/ops/rulecheck.go`)**:
   - 解析 `docs/rewrite-research/05-business-rules.md` 中的全部 237 条规则（R001–R237）；
   - 遍历代码库扫描 Go/TypeScript/Vue 测试中的 `契约 R...` 标识；
   - 建立了架构决策白名单映射（`WhitelistReason`）：
     - 记录 D5 割接后上线的 AI 巡查体系（R184, R189–R201）；
     - 记录 D1/D2 薄 SSR 废弃的现行站静态预渲染/slots 规则（R229, R232, R234, R235）；
     - 记录纯协议页文案（R010）；
   - 输出详尽的审计报告：**237 条契约规则已达成 100.0% 合规覆盖**（显式测试标注 214 条 + 白名单 23 条）；
   - 单元测试 `rulecheck_test.go` 全通过。

2. **主命令扩展 (`server/cmd/sjtuow/`)**:
   - 接入 `sjtuow rulecheck` 子命令，支持自动向上回溯定位仓库根目录并读取规则文档。

3. **契约标注规范化补齐**:
   - 在 `accounts/roles_test.go`、`accounts/service_test.go`、`accounts/avatar_test.go`、`ops/backup_test.go`、`markdown/markdown_test.go`、`notify/notify_test.go`、`todo/todo_test.go`、`scrims/teaming_test.go`、`tournaments/lifecycle_test.go`、`ratelimit/limits_test.go` 等全域测试中，将原松散注释统一为 `// 契约 R...` 规范标记。

4. **停机割接剧本与自动化流水线 (`docs/` & `deploy/`)**:
   - 编写 `docs/cutover.md`：
     - 明确零数据丢失、全编号沿用、密码/签名/密文平滑继承三大不变量；
     - 规划 15 分钟停机维护时间窗口及逐分钟耗时模型；
     - 编制全流程 Checklist 与 48 小时秒级回滚预案。
   - 编写 `deploy/cutover.sh`：
     - 自动化流水线：停止旧栈写入 -> 最终快照备份 -> 新库模式初始化 -> 全域历史数据只读导入 -> `sjtuow reconcile` 对账门禁自检 -> 启动新栈集群 -> `/healthz` 冒烟探测。

## 验证

- `go test -v ./internal/ops/...` 全部通过。
- `./sjtuow rulecheck` 验证：
  - 总规则数：237 条
  - 测试显式覆盖：214 条
  - 白名单例外：23 条
  - 合规覆盖率：100.0%
