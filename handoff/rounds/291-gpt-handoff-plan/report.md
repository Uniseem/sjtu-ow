# 291 实现报告

## 结论

完成（仅文档）。用户的四项拍板已写进权威位置；新增收尾批次执行文档 `docs/final-batch.md`，供接手的 GPT 一次做完剩余工作。

## 逐条结果

| 编号 | 结果 |
|---|---|
| T1 批次文档 | 新增 `docs/final-batch.md`。各节内容：<br>0 用户决定与授权边界<br>1 开工<br>2 正式站 cron（10-20 前完成，含回退）<br>3 编码阶段：3.1 读码复核 290 的九个风险面；3.2 验收工具 a–k；3.3 前台补齐；3.4 后台六组；3.5 割接材料<br>4 测试阶段：4.1–4.11，含两次真实旧库演练<br>5 出口<br>6 收尾与问用户<br>7 不做<br>附 STATUS 待办对照表：STATUS 里的每个「待」都对到某一节，或列在问用户的清单里 |
| T2 拍板入文档 | 用户原话写在本轮 request。<br>迁移文档改了这几处：第 10 节第 6 件改为不做试用站；11.1 F10 的出口改成两条旅程、两次演练、由用户授权；11.2 第 8 包；11.6 改为指向批次文档。<br>`docs/README.md` 导航加了入口。<br>STATUS 改了头部（milestone、round、next_frontend、blocked_on）、前台迁移说明和运维表四行。`next_backend` 归后端，没有改 |
| T3 STATUS 修正 | 按代码修正以下各行，验收列都没动：<br>• `/unsubscribe/<token>/` 接口列：`server/internal/notify/api.go:77-83`，Caddy 已转<br>• `/_styleguide/emails/`：`web/apps/site/src/routes.ts:50`<br>• sitemap、robots：`server/internal/content/api.go:273-274`；图标 301：`deploy/Caddyfile.new:137-141`<br>• A6 头像、资料不全、待发信数：BE-10 已在 290 接上<br>• 底座最后一行：A13、B7、B5 代码已齐<br>另外删掉了已经失效的 287–289 草稿说明（289 已一并提交）和 290 的追加说明；290 摘要补记了 CI |
| T4 归档 | 288、286 的摘要原文移到 `handoff/archive/status-recent-288.md`、`status-recent-286.md`，历史入口已加链接。现在最近轮次是 291、290、289 |
| T5 整组 | 测试机 `20261012-012243-c099f6c` 退出 0 |

另外在 290 的 review.md 末尾追加了「291 轮补记：CI」：af2ae4c 对应 run 38157411476，结果 success。

## 验收输出

- 相对链接检查：在本机用 Python 只读检查了 7 个改动或新增的 md 文件，输出 `links ok`。这只是文件存在性检查，不是编译或测试。
- 整组：测试机后台跑 `bash scripts/remote-check.sh`，运行编号 `20261012-012243-c099f6c`，日志是 `full-check.log`，结果「== 全部通过」`EXIT=0`。
  - Go：gofmt、vet、staticcheck；govulncheck 输出「No vulnerabilities found.」；`go test` 各包 ok。
  - Web：Vitest 18 + 259 + 28 全部 passed；site 和 admin 构建通过。
- 整组开始后，又改了 `docs/final-batch.md` 两处文字（演练示例命令、287 冷却的范围）。`scripts/check.sh` 和各项测试都不读这些文档（已用 grep 核对），所以不影响整组结果。

## 设计偏差

无代码变更。设计层面只有一处变化：检查点 B 干部试用站改为不做。这是用户本轮拍板的，已写进迁移文档第 10 节第 6 件和 11.1；`design-next.md` 没有涉及试用站，所以没改。

## 未完成 / 顺带发现 / 需要确认

- 「不做这个」是用户在「什么时候部署试用站」这个问题里填的其他答案。本轮的理解是：不部署 IP 试用站，也不安排干部试用；割接条件改成对拍和旅程全绿、两次演练通过，割接时间由用户定。割接前是否另要人工验收，留在收尾批次第 6 节问用户。
- 顺带发现，都已写进批次文档：
  - `deploy/rehearse.sh` 在给的路径不存在时会静默改用空库，而且没有 `import-media` 这一步（3.2 i）。
  - `deploy/crontab.example` 的 `DC=` 只带一个 `-f`，而正式站要带 vps 覆盖文件（第 2 节）。
  - `/admin/settings/prerender/` 现在只是客户端跳转，不是第 10 节第 5 件要求的 301（3.4）。
  - 样张页缺 266、267 的大部分组件（3.3）。
  - 对拍工具没有后台行，四类身份以外的身份没展开（3.2 a、b）。
  - `scripts/journey.mjs` 停在 260（3.2 f）。
- 没有登录任何服务器。cron 的修改授权交给批次文档第 2 节，由 GPT 执行。

## 改动文件

- 新增：`docs/final-batch.md`、`handoff/archive/status-recent-288.md`、`handoff/archive/status-recent-286.md`、本轮目录下的 request、report、review 和 full-check.log
- 修改：`docs/frontend-migration.md`、`docs/README.md`、`handoff/STATUS.md`、`handoff/rounds/290-f6-f9-full-frontend/review.md`（追加）
