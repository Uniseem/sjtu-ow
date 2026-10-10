# 275 复核结果（自查）

## 结论

通过（自查；不标「复核通过」）。

## 验证记录

1. **全量测试**（本地 + 测试机）：`pnpm test` 201 条全绿（含 17 组评论区旧模板真渲染对照、三页 SSR、草稿评论降级、路由、守卫、壳、预算）。
2. **变异自查**（换角度，硬规则 7 的做法）：把五处关键逻辑改坏再恢复，每处都有测试红——
   - 评论 404 降级改成照抛 → 4 失败（草稿场景 + 相邻用例）
   - 「更新于」的超过一天阈值改成超过零天 → 1 失败
   - 「我的安排」的登录条件删掉 → 1 失败
   - 分类标签的 `aria-current` 改成恒 false → 1 失败
   - 「加载更多」的 `hasMore` 改成恒真 → 5 失败（fixture 对照 + 内容测试）
3. **fixture 生成一致性**：本地与测试机各自跑 `legacy_fixtures.py`，产出逐字节一致（首次在测试机跑出的两处错误——空池没传、CCommentReply 用错上下文键——修后重跑通过）。
4. **browser-check**（测试机，严格 CSP、真 Chromium）：`BROWSER-CHECK-OK`。第一次随整组跑时报首页探测失败（连接时序的偶发，log `20261011-005408-8177543`），单独复跑通过（`20261011-005955-f6f48c4`）；本轮换页读旧键的 TypeError 是真问题，已修（见 report「逐条结果」补记）。
5. **对拍**：`--only=home,news,article,about,terms,privacy,search,submit --wide --strict`，结果见 report「验收输出」。

## 发现的问题

- **必须修（本轮已修）**：页面 computed 直接读 `page-data` 的键，SPA 换页时全局 page 对象先删旧键、旧组件卸载前重渲染读空（browser-check 抓到 `reading 'stats'` 的 TypeError）。三页统一改成可选链/空形状兜底（StandardPage 262 年就这个写法）。这条值得进 AGENTS「已知的坑」。
- **建议修（后续轮次）**：`GetApiMeAgendaOut.items[].kind` 是代码值不是显示文案，首页「我的安排」原样输出；等 agenda 组合进 HomePageOut（glm-handoff 5.1）时由后端投影，前端无需改。

## 判断里最没把握的

- **评论区的真实交互**（发表、回复、点赞、隐藏、置顶、加载更多）只有 SSR 结构对照和桩测试，没有在真浏览器里点过——旅程脚本要等 F5 阶段。Go 的评论接口本身有回归，前端动作映射是照接口形状逐个写的。
- **首页对拍的截图差**：hero 的昼夜场景图和动态占位是 CSS 动画，对拍已 reduce-motion；像素差阈值 0.5% 应该过得去，等结果。
- **`comment_total`（BE-4 之前）**：头部事实行的评论数现在用 `thread.total`（评论接口的顶层总数），和旧站 `thread.total` 同源；BE-4 的 `comment_total` 到位后优先用谁需要再看（旧站两者同源，应相等）。

## 文档更新

- STATUS：头部（round/next_frontend/next_backend/updated）、BE 表（BE-0–3 已接 275；新增 BE-4–8）、前台页面进度表三行、「最近轮次」加 275。
- AGENTS「已知的坑」：补「page-data 换页先删旧键」一条（见提交）。
- `docs/frontend-migration.md` 不动（第 2 节是快照）。
