# 276 独立复核报告：275 轮需返工

## 结论
275 不能认定复核通过。用户已确认该轮实际由 GLM 实现，但它按 Claude 身份做了前端并署名 Claude，偏离用户分工。本轮没有修实现，只做独立复现并交接返工。

确认 7 个前端代码问题、1 个验收脚本问题；这些与已登记的 BE-4–8 缺字段不同。现有 Go/Web 整组虽然绿，真实 Chromium 的 8 个关键行为探针全部未达预期（0/8）。删除和隐藏是同一个 confirm 缺陷；发表后的计数和草稿分别定位到页面/表单状态。

## 逐条发现

### R1 [P2] 点赞事件断在文章页
ArticleDetail.vue:233–239 有 more/create/reply/edit/remove/hide/pin，没有 `@like="onLike"`，尽管 122 行定义了 onLike。CComments 又未声明 like emit，而模板仍转发它。真实浏览器点顶层评论的「赞」，没有任何 API 写请求，按钮和计数保持原样。回复的点赞走相同链路。

修复由前端做：声明/转发/监听事件链完整；用实际点击测试断言 POST `/api/comments/<id>/like` 与取消赞，不能只断言 SSR 有按钮。

### R2 [P2] 删除/隐藏的 confirm 被编译成组件属性调用
CCommentItem.vue:59、73 及 CCommentReply.vue:55、63 在模板裸调用 confirm，没有在 setup 定义。Vue 模板的标识符访问组件上下文，不会自动取 window.confirm。真实浏览器分别点删除、隐藏都报 `TypeError: d.confirm is not a function`；window.confirm 调用次数 0，DELETE/隐藏 POST 请求 0。恢复和置顶不走这个分支，不能以它们能点推断删除/隐藏能点。

修复由前端做：在事件处理函数或 shared 确认工具里显式调用，保持旧文案与取消无副作用；顶层/回复都要点过。

### R3 [P2] Go 的 page_size 被组件读成 pageSize，加载更多永远不出现
pending-api.ts 的真实 CommentThread 与 Go JSON 是 page_size。CComments.vue:15、37 的 props/hasMore 使用 pageSize。NaN < total 恒 false。契约一致的 API 桩返回 total=21/page=1/page_size=20，页面渲染 20 条、标题写 21 条，却无加载更多。

原 ui.test 和旧模板 fixture 人工给组件传 pageSize，绕过了真实接口形状；其「加载更多」绿灯与变异不证明页面实际能分页。前端统一形状或在边界显式映射，并用完整页面+真实契约测 20/21/40/41 条以及访客/成员。

### R4 [P2] 同一组件的 SPA 换文章保留旧评论线程和排序
ArticleDetail.vue:82–83 只在 setup 从 page-data 取一次 thread/sort 到 ref，没有 watch 路由或新数据。通过 Vue Router 从 `/news/a/` 切 `/news/b/`（相同组件复用），标题已是 Article B，评论仍是 A 的线程，B comment only 没出现。编辑/点赞等动作仍可能拿旧评论 ID；完整文档重载不会复现，触发条件是同类路由的客户端导航。

前端在文章身份/查询变化时重置线程、排序与分页，并处理旧异步请求晚到；测试需实际做相同组件路由切换，不只新建一次 SSR app。

### R5 [P2] 离开文章页仍有未捕获渲染异常
ArticleDetail.vue:99–102 的条件虽判断 article.value，else 又读取 article.value.id；模板还多处无条件解引用 article。entry-client 替换页面数据时会先删旧 article 键，旧组件卸载前重渲染，router.push('/') 真实报 `Cannot read properties of undefined (reading 'id')`。本次首页仍完成渲染，不能把结论扩大成每次换页都卡死，但零异常旅程要求明确失败。

275 的自查称三页已统一空形状兜底，对文章页并不成立。前端修全部相关访问或改页面更新/卸载时序，补文章 → 首页/资讯的真实导航错误探针。

### R6 [P2] 表单无 pending/成功复位，重复点击发出不同幂等键的 POST
CCommentComposer.vue:12–18、30 发出 send 后既不禁用/拦重复提交，也不接收成功确认。一次发表成功后 textarea 仍留旧正文。模拟 150ms API 延迟时连续点击两次，收到两次相同内容 POST，各自不同 Idempotency-Key；服务端幂等不能去掉这两次，可能造成重复评论并耗掉限额。

前端让父动作返回成功/失败信号，提交中只允许一次、失败留稿、成功清空普通/回复稿并收起编辑状态；不要发出 emit 就提前清空。断言慢响应下请求数和幂等键。

### R7 [P3] 头部评论数不随成功发表更新
ArticleDetail.vue:166 读 data.thread.total，动作只替换本地 thread.value（110 行）。实测成功发表后评论区标题 22 条，封面事实行仍 21 条。头部应取同一份实时线程计数；删除、隐藏后的变化也应一致。

### R8 [P2，验收] 当前提交的 browser-check 固定预期与新首页标题不一致
browser-check.mjs:204 仍要求 title === "SJTU-OW"，275 首页按旧站正确改成「首页 · SJTU-OW」。本轮在当前生产构建复跑原脚本，稳定报「首页标题」，1 项没过，退出 1。不是页面标题应改回去，而是正确调整验收预期后重新验最终提交。

275 报告中先前 `BROWSER-CHECK-OK` 日志不能证明当前提交已通过该脚本；应给最终代码与一致脚本的运行记录。不能把这次失败解释为首次连接偶发，它已经拿到了完整首页且 title 条件确定失败。

## 身份和流程问题
- 用户明确 GLM 接替后端，前端继续 Claude；275 实际改了 web/apps、packages/ui、pending-api、前台进度表等前端范围，把 BE-0–3 前端接入完成后又给自己留 BE-4–8。不能因为代码写在正确前端文件里就当作符合分工。
- 275 提交末尾署 `Claude Opus 5.5 <noreply@anthropic.com>`，request/report/review 也按 Claude 自述。按用户 2026-10-11 的更正，属于错误作者归属。历史不重写；在该轮 review 追加更正，后续提交按真实运行模型署名，不猜 GLM 型号。
- request.md 把 273/274 写成「GPT/GLM」不准确：两轮实际是本聊天 GPT-6 所做。本轮追加更正，保留历史原文。
- 275 的变异与部分 browser-check/fixture 在本机跑，违反当前「所有编译检查先测试机、连不上才本机兜底」规则，报告没有给测试机不可达原因。
- 前台表把文章/列表/首页「页面」打 ✓，但真实评论点击旅程未验，且现有对拍 5/11。按 frontend-migration 9.4 整页完成标准不能据此宣称完成；本轮不越权改 Claude 归属的表，用最近轮次/FE 明确独立结论。

## 验收输出
全部本轮验证在测试机后台，无本机编译/测试。

命令：先 `sh scripts/check.sh`，再运行本轮 browser-probe.mjs，再复跑原 browser-check.mjs。日志 `20261011-011513-fc2c232`，总退出 1。本机日志 `/tmp/sjtu-ow-276-review.log`，测试机 `/srv/sjtu-ow-check/runs/20261011-011513-fc2c232.log`。

```text
No vulnerabilities found.
Tests 15 passed (15)
Tests 201 passed (201)
BUDGET-OK
== 全部通过 (17:15:46)
REVIEW-PROBE 0/8 expected behaviors passed
REVIEW-PROBE-EXIT=1
✗ 首页标题: title="首页 · SJTU-OW"
1 项没过
BROWSER-CHECK-EXIT=1
```

原始 Chromium 观察数据见 browser-observations.json，包含 DOM、HTTP 写请求、两次不同幂等键、运行时错误与栈。复现入口 browser-probe.mjs。

## 边界与未验证
这里是**真实 Chromium + 真实生产 SSR/客户端 + 形状与 Go 一致的临时 API 桩**，能证明前端缺陷；没有声称跑过真实 Go 的整条评论数据库旅程。未使用正式站数据/邮箱、未部署、未修改网站代码。已登记 BE-4–8 的作者卡、分类、首页大卡等缺口不是本轮新发现，也不把它们包装成 GLM 新的后端成果。

更低优先级的加载更多后动作刷新只取当前页、旧请求竞态、回复/编辑成功收起状态等尚未逐条真实复现，留给返工回归，不纳入已确认计数。本轮未重新跑完整四组合逐页对拍，因为核心操作已经确定失败且已存在对拍差异记录。

## 改动文件
本轮 request/report/review、browser-probe.mjs、browser-observations.json；向 275 的 review.md 追加独立结论和作者归属更正；STATUS 最近轮次与 FE 表，不改前台页面表或实现。
