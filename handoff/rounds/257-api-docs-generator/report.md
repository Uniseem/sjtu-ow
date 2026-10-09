# 257: 架构落地：接口注册表自动生成全景 API 参考手册与干部能力对照表 (apigen docgen)

## 做了什么

1. **门禁可读描述机制 (`server/internal/platform/api/gates.go`)**：
   - 为准入门禁 `Gate` 接口增加 `Describe() string` 方法；
   - 补齐所有六类门类型的自述格式：
     - `publicGate`: `Public（公开）`
     - `memberGate`: `Member（登录成员）`
     - `verifiedGate`: `Verified（已验证成员）`
     - `featureGate`: `Feature(...)`
     - `capGate`: `Cap(...)`
     - `superuserGate`: `Superuser（超级管理员）`

2. **文档自动生成器 (`server/internal/platform/apigen/docgen.go`)**：
   - 实现 `RenderMarkdown(reg *api.Registry) string` 与 `WriteMarkdown(filePath string, reg *api.Registry) error`；
   - 自动生成架构指标概览（全站 163 个接口，其中公开接口 25 个、登录会员接口 60 个、干部管理接口 78 个）；
   - 格式化输出全量接口清单矩阵（HTTP 方法、路径、准入门禁、集中限流规则、查询预算上限、后台大类与标签）；
   - 输出干部角色能力对照表（Who Can Do What），细化超级管理员、赛事总监、内战裁判、资讯编辑的权责范围。

3. **CLI 挂载与自动导出 (`server/cmd/sjtuow/main.go` & `docs/api-reference.md`)**：
   - 扩展 `sjtuow apigen` 子命令：在生成前端 TypeScript API 客户端及导航元数据后，自动将文档输出至 `docs/api-reference.md`；
   - 本地实际运行 `sjtuow apigen`，成功生成包含 163 个接口细节的 `docs/api-reference.md`。

4. **单元测试与整组检查**：
   - 在 `server/internal/platform/apigen/apigen_test.go` 中增加 `TestRenderMarkdown` 单元测试并通过；
   - 在测试机 `sjtu-ow-test` 上运行 `scripts/remote-check.sh`，Go 编译、静态检查、漏洞扫描、单元测试及 Web 端 SSR 构建全绿通过。

## 验证

在测试机 `sjtu-ow-test` 上运行整组检查 `scripts/remote-check.sh`：
- Go：gofmt、go vet、staticcheck、govulncheck（0 漏洞）全过；
- Go 单测：`go test ./...` 全包通过；
- Web 前端：`pnpm test` 通过，包含单测、客户端与 SSR 构建成功、体积预算合格（gzip 79593 字节，BUDGET-OK）。
