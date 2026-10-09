# 256 轮复核报告：M11 割接演练流水线、全栈端到端新旧兼容与对拍工具

## 变更核查

1. **对拍核验工具 (`server/internal/ops/parity.go` & `parity_test.go`)**：
   - 验证了签名算法使用 `djsign.SignObject` / `UnsignObject`（日历）与 `djsign.Dumps` / `Loads`（退订），与现有生产站签名算法一致；
   - 验证了 Argon2id 与 Django PBKDF2 哈希兼容，且 PBKDF2 能够正确标记 `rehash` 触发升级；
   - 验证了 Markdown 文章渲染管线与图片引用的有效性扫描；
   - 单元测试与 mock 服务器端点对拍测试全绿。

2. **全库对账工具 (`server/internal/ops/reconcile.go` & `reconcile_test.go`)**：
   - 完整性检查 `PRAGMA integrity_check` 与外键检查 `PRAGMA foreign_key_check` 守卫正常；
   - 领域指标按状态分组（文章、赛事、内战、战队、报名、评论）统计逻辑准确；
   - 新旧库抽样比对支持用户、文章与战队。

3. **割接模拟演练流水线 (`deploy/rehearse.sh`)**：
   - 脚本语法严谨（`set -euo pipefail`，`trap 'rm -rf "$WORK_DIR"' EXIT`）；
   - 在独立临时工作目录下操作，零脏数据风险；
   - 计时准确输出清晰的耗时表格与 15 分钟预算评估。

4. **契约合规与测试机验证**：
   - 测试机整组检查（Go + Web）全绿通过；
   - 契约规则引用遵循规范。
