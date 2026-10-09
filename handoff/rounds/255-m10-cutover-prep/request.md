# 255 M10 割接准备与契约审计（rulecheck 规则覆盖、数据对账增强、停机割接剧本）

## 背景

在 M1–M9 完成了全套 Go 服务端、Vue 3 SSR 前端、后台管理系统、备份还原与容器化部署后，进入 M10（割接准备与系统加固）。
根据 `docs/rewrite-research/12-architecture.md` 8.3、8.4、9 与 11.2：
1. 契约覆盖审计工具 `sjtuow rulecheck`：
   - 提取 `docs/rewrite-research/05-business-rules.md` 中的 237 条业务规则（R001–R237）；
   - 扫描全部 Go 测试与前端/E2E 测试中的 `契约 R...` 标注；
   - 统计覆盖率，标记未覆盖规则与例外白名单；
2. 全库对账功能增强 (`reconcile`)：
   - 支持新旧库全域表行数对比、核心字段（邮箱、段位、队伍成员、文章状态）抽样校验、外键约束全量检查；
3. 割接剧本与演练工具：
   - 产出 `docs/cutover.md`（完整停机割接操作剧本、耗时预估模型、48 小时回滚方案）；
   - 产出 `deploy/cutover.sh`（执行自动化割接流水线：维护页挂起 -> 最终备份 -> 导入 -> 对账 -> 启动新站 -> 冒烟检查）。

## 本轮范围

做：
1. `server/internal/ops/rulecheck.go`:
   - 实现 `RuleCheck(rulesPath, repoDir string)`，解析 237 条规则并匹配测试文件中的引用；
   - 支持输出覆盖率报告和未覆盖规则清单。
2. 接入 `server/cmd/sjtuow/main.go`:
   - 挂载 `sjtuow rulecheck` 子命令。
3. 增强 `server/internal/ops/reconcile.go`:
   - 增加报名名单快照比对、文章评论数比对等精细化对账项目。
4. 编制割接剧本与脚本：
   - `docs/cutover.md`: 割接剧本与回滚预案；
   - `deploy/cutover.sh`: 割接自动化脚本。
5. 编写测试 `server/internal/ops/rulecheck_test.go`。
6. 测试机整组检查验证全绿。

不做：
- 生产服务器实际割接（等待用户宣布割接日期）。

## 验收

- `go test -v ./internal/ops/...` 全部通过。
- `sjtuow rulecheck` 能准确解析 05 号文档并报告规则覆盖情况。
- 测试机整组检查 `scripts/remote-check.sh` 退出码 0。
