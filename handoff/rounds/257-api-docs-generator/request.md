# 257 架构落地：接口注册表自动生成全景 API 参考手册与干部能力对照表 (apigen docgen)

## 背景

根据 `docs/rewrite-research/13-ideas-and-followups.md` D 节「新栈的想法」：
> 注册表同时生成文档：每个接口的方法、路径、门、限流、查询预算，也生成一页给干部看的「谁能做什么」表（现在的 `docs/admin.md` 4 章手写），门改了文档自动跟着改。

随着 M1–M11 全部核心领域、后台管理页面与割接流水线落地完成，全站已累积 163 个接口。需要统一的自动化工具，将 Go 服务端注册表单向派生为标准化的 Markdown 全景参考手册，确保代码实现与架构文档 100% 保持同步。

## 本轮范围

做：
1. `server/internal/platform/api/gates.go`:
   - 给 `Gate` 接口增加 `Describe() string` 方法；
   - 补齐所有门类型（`Public`、`Member`、`Verified`、`Feature`、`Cap`、`Superuser`）的标准化可读描述。
2. `server/internal/platform/apigen/docgen.go`:
   - 实现 `RenderMarkdown(reg *api.Registry) string` 与 `WriteMarkdown(filePath string, reg *api.Registry) error`；
   - 自动统计接口总数、门禁分布、限流规则及查询预算指标；
   - 自动生成全量接口清单表格（方法、路径、准入门禁、限流规则、查询预算、后台分类）；
   - 自动生成干部角色能力对照表（Who Can Do What）。
3. 接入 `server/cmd/sjtuow/main.go`:
   - 在 `runApigen` 中自动生成 `docs/api-reference.md`。
4. 编写测试 `server/internal/platform/apigen/apigen_test.go`:
   - 增加 `TestRenderMarkdown` 单元测试。
5. 测试机整组检查验证全绿。

不做：
- 手工修改 `docs/api-reference.md`（必须由生成器自动导出）。

## 验收

- `go test -v ./internal/platform/apigen/...` 通过。
- `sjtuow apigen` 能顺利导出 `docs/api-reference.md` 并包含 163 个接口明细。
- 测试机整组检查 `scripts/remote-check.sh` 退出码 0。
