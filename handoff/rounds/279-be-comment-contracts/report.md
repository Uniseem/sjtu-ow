# 279 实现报告

## 结论

BE-7、BE-8 后端实现与自查通过；前端接入和文章真实浏览器旅程尚未验证，不标文章页完成。连续开发计划已记入 request，本轮先落地评论契约。

## 逐条结果

1. `/api/session` 添加 `user.can_comment`，直接取 `Viewer.CanUse(FeatureArticleComment)`；不混入邮箱或后台能力。真实 HTTP 测试覆盖 7 种权限组合（含超管、角色禁用、个人允许覆盖）；现有 `TestGetSessionApi` 同时覆盖访客和停用用户 `user: null`。
2. `Comment` 添加可空 `edited_at`，创建/列表/回复/修改共用投影；作者实际修改正文才更新时间。同正文（去首尾空白后）不修改时间、版本或重复送审，与旧 `comments/services.py:edit` 一致。隐藏/恢复、置顶、点赞、删除保留独立编辑时间。真实 GET/PATCH、回复以及 service 管理动作均有回归。
3. 新迁移 00019 添加可空字段；旧库导入保留原 `edited_at`（含微秒、NULL），重复导入保持值。原 `updated_at` 兼容保留。
4. 升级测试先应用到 00018、插入真实旧格式评论，再升级两次；正文和更新时间保留、编辑时间为 NULL。已有 Go 行的作者编辑历史无法从管理更新时间可靠反推，本轮不伪造。
5. 通过测试机 `sjtuow apigen` 生成并取回类型；`docs/api-reference.md` 重新生成但无差异。12 号文档补上权限和编辑时间语义。未加依赖、未修改旧站、未部署。

## 验收输出

全部在测试机后台执行，本机日志在 `/tmp/sjtuow-279-*.log`；测试机日志位于 `/srv/sjtu-ow-check/runs/`。

- 初轮 `20261011-121808-5b4c9ab`：`cd server && go test ./internal/accounts ./internal/comments ./internal/content ./internal/platform/db && go run ./cmd/sjtuow apigen`，退出 1。accounts/comments/db 通过；新增导入断言把旧导入器固定六位小数的 `.000000Z` 错写成 `Z`，修正测试预期，不改导入器格式。
- 第二轮 `20261011-121908-23250fe`：四包专项全绿，apigen 成功；随后变异阶段退出 1，因为「投影遗漏编辑时间」的变异使局部变量 at 未使用。修变异使其保持可编译；没有把编译失败记成抓到规则。
- 最终 `20261011-122024-44ae78e`：`uv run python handoff/rounds/279-be-comment-contracts/mutate.py && sh scripts/check.sh`，退出 **0**。9 处变异先通过编译，再分别被本轮回归抓住，输出 `MUTATIONS-OK 9`。
- 最终整组：gofmt、go vet、staticcheck、govulncheck、全部 Go 测试、apigen 生成物对比通过；Web 15 + 202 条通过，生产构建通过，首页壳 gzip 96649 字节，`BUDGET-OK`，输出「全部通过」。

## 设计偏差

无。本轮权限与旧功能权限一致；同正文不记编辑直接依据旧站 service。迁移追加字段，旧 `updated_at` 保持原义，页面已读字段未删除或改名。

## 未完成 / 顺带发现 / 需要确认

- BE-4–6 下一轮补文章/资讯/首页投影。
- 前端 `pending-api.ts` 的 BE-7 和递归 CommentNode、已编辑标记接入待前端轮次；本轮不删交接类型。
- 评论真实 Go 浏览器旅程、文章整页对拍：未验证；已有桩浏览器证据不替代它们。
- 本轮为自查，不称独立复核。推送后须检查对应提交的 CI，执行结果在交班消息报告。

## 改动文件

- `server/internal/accounts/api.go`、`session_comment_test.go`
- `server/internal/comments/model.go`、`store.go`、`service.go`、`edited_at_test.go`
- `server/internal/content/import.go`、`import_comment_edited_test.go`
- `server/db/migrations/00019_comment_edited_at.sql`、`server/internal/platform/db/comment_migration_test.go`
- `web/packages/api/src/gen/index.ts`（apigen 生成）
- `docs/rewrite-research/12-architecture.md`、本轮 request/report/review/mutate、STATUS 与移出的最近轮次摘要
