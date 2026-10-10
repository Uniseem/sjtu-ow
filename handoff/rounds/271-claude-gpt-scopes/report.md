# 271 实现报告

## 结论

完成。Claude 和 GPT 各自能改什么、怎么把要对方做的事交过去、同时开工怎么不撞车，写进了 `AGENTS.md`「Claude 和 GPT 分开做」；STATUS、`handoff/README.md`、`pending-api.ts` 的头注释都指过去，没有第二份规则。

## 逐条结果

1. **`AGENTS.md`**：270 的那一句换成一节，三部分：
   - **归属表**，按路径分。要点：`web/` 归 Claude，但 `web/packages/api/src/gen/` 和 `docs/api-reference.md` 归 GPT，只由 `sjtuow apigen` 生成、谁都不手改（CI 本来就比对生成物），这是两边的接口契约；`server/`、新栈的部署文件、`e2e/caddy/`、`docs/cutover.md` 归 GPT；对拍和浏览器验收工具归 Claude（GPT 改了 `sjtuow import`/`session`/`import-media` 的参数时可以只改调用那一行）；`scripts/check.sh`、CI 按 Go/Web 两段分；设计文档谁的轮次要改谁改（本来就要用户拍板）；`STATUS.md` 按段分；旧站冻结；调研记录不改。表外的东西先问用户
   - **越界的事写进对方的表**：前端要的 Go 字段写 BE（`pending-api.ts` + STATUS）；GPT 做完一条只标「✓」，**不动 `pending-api.ts` 和页面**，Claude 下一个前端轮次删那段、跑对拍、标「已接」（270 原来写的是让后端删，改了）；后端改页面已经在读的字段**只许加**，要改名、删除先登记一条 FE，等前端换过去再删旧字段
   - **同时开工防冲突**：不能共用一个工作目录（`remote-check.sh` 会把对方没提交的改动一起打包上测试机，`git add` 也会带上对方的文件），各用一个克隆、都在 `main`；开工前、推送前各 `pull --rebase`；`git add` 只写自己的路径；轮次号撞了把自己的改成下一个空号，目录名前端 `NNN-f<阶段>-`、后端 `NNN-be-`；测试机排队；署名各署各的
2. **`handoff/STATUS.md`**：`next` 拆成 `next_frontend`、`next_backend`（各改各的，原来的部署一句并进后端那行）；「交给后端（GPT）」加「状态」一栏（四条都是「待做」），引言改成新的交接方式；新加「交给前端（Claude）」表（暂无）
3. **`handoff/README.md`**：做法表加「前后端分开连做」一行，指向 AGENTS
4. **`web/apps/site/src/pending-api.ts`**：头注释改成「后端标完成后，下一个前端轮次删掉这里的一段」

## 验收输出

测试机整组（`bash scripts/remote-check.sh`，和 CI 同一组）：

- `20261010-221237-52ebb5d`：Go 五项通过（govulncheck 无漏洞），Web 15 + 171 条通过，首页壳 gzip 95016 字节 BUDGET-OK，`== 全部通过`，退出 0

这一轮只改了一个 TS 文件的注释，其余是文档；没有跑对拍和变异（没有可测的行为变化）。

## 设计偏差

无。

## 未完成 / 需要确认

- **272 轮更正**：用户定了「轮流干的」，共用一个检出目录、交班时工作区必须干净，规则改在 AGENTS「Claude 和 GPT 分开做」。下面是当时的原文
- **GPT 在哪个目录干活要你定**：266–270 期间两边用的是同一个目录，GPT 没提交的草稿就留在里面。规则写的是「同时开工各用一个克隆」；建议 GPT 用另一个克隆（比如 `~/Desktop/coding/sjtu-ow-gpt`）。如果两边永远是轮流干、不同时开工，共用一个目录也行，但开工前工作区必须是干净的
- 没写自动检查（比如按提交的署名核对改了哪些路径）。如果以后真的撞车，再考虑加
- 下一个前端轮次的号顺延成 272（文章页）

## 改动文件

`AGENTS.md`、`handoff/STATUS.md`、`handoff/README.md`、`web/apps/site/src/pending-api.ts`（注释）、本轮 `request.md`、`report.md`、`review.md`
