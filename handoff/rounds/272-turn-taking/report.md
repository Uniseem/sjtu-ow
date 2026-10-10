# 272 实现报告

## 结论

完成。Claude 和 GPT 轮流干、共用一个检出目录，写进了 `AGENTS.md`「Claude 和 GPT 分开做」。

## 逐条结果

- `AGENTS.md`：271 的「两个助手同时开工就不能共用一个工作目录，各用一个克隆」换成「轮流干，共用一个检出目录」：同一时间只有一个助手在干；交班时工作区必须干净（提交推送或删掉，草稿不留）；接班先 `git status`，干净就 `git pull --rebase` 开工，不干净就停下来问用户、不替对方提交或删除；要同时开工先问用户，那时再各用一个克隆。小标题「同时干活时防冲突」改成「轮流干，防冲突」
- 271 `report.md`：「GPT 在哪个目录干活要你定」前加「272 轮更正」，原文保留
- `STATUS.md`：「最近轮次」加 272；`next_frontend` 的文章页顺延为 273

## 验收输出

- 测试机整组 `20261010-221733-de3b2c7`：Go 五项通过（govulncheck 无漏洞），Web 15 + 171 条通过，BUDGET-OK，`== 全部通过`，退出 0（只改文档，照规矩跑）
- 交班前的 `git status`：见提交说明（推送后为空）

## 设计偏差

无。

## 改动文件

`AGENTS.md`、`handoff/STATUS.md`、`handoff/rounds/271-claude-gpt-scopes/report.md`（加更正）、本轮 `request.md`、`report.md`、`review.md`
