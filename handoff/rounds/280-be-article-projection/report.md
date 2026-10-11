# 280 实现报告

## 结论

BE-4 后端投影完成、自查通过。文章访客/成员四组合对拍 2/2 通过，最大像素差 0.153032%（阈值 0.5%）；真实 Go 评论写操作旅程与 BE-7/8 前端类型接入仍未验证，不标整页完成。

## 逐条结果

1. `Service.ArticlePage` 组合完整投影；HTTP 只调用服务。添加作者公开卡、公开文章数、最近发布时间、评论总数、同栏目上下篇、同分类相关文章、分类 slug、默认封面、关联赛事卡和 SEO。原字段保留，NewsItemOut 只追加可空默认封面字段。
2. 作者头像包含自上传与默认位置图库选择；停用账号保留公开昵称/宣言但不出头像。只输出作者卡字段，不输出邮箱、联系方式。空作者为 null、无日期为 null、无相关文章为 []。
3. 相邻文章用直属父页面区分栏目，允许分类不同，严格比较首发时间；相关文章同分类（含 NULL 分类）、排除自己、首发及最近发布倒序取三篇。新公开投影均排除草稿/受限文章。UTC 排序补齐到九位小数，保留微秒，并兼容 Z/.000000Z 表示同一时间。未知父栏目时不猜上下篇。
4. 评论头部与列表共享旧 thread 的顶层可见性：有存活回复的墓碑保留，回复不计头部总数；版主也排除已删且无存活回复的顶层和已删回复。真实 API 的访客/成员计数 4、版主/超管 6、停用超管 4；新回归与原评论包整组通过。
5. 关联赛事复用 `Tournament.IsPublic` 和 `Phase(ctx.Now())`；草稿/不存在为 null，发布/完成/取消按旧规则，整队/个人报名标签正确，不输出参赛联系方式。
6. 新 00020 迁移保存文章直属父编号及图片集合父子关系。图库含根、子目录、孙目录，按图片 ID 升序挑图：文章 ID、赛事 ID+13 模池大小。导入按树顺序写入，根固定 key 由最上层同名集合占用，重名子目录不抢根。旧编号、微秒、重复导入与既有库升级均有回归；既有行新列 NULL，不虚构旧关系。新建文章使用已导入的 news 栏目。
7. 类型由测试机 apigen 生成并取回；API 手册重新生成无差异。前端 pending-api 和页面未改，长期分工不变。12 号实现文档补投影与树关系语义。

## 验收输出

全部在测试机后台跑，未用本机测试兜底。测试机日志在 `/srv/sjtu-ow-check/runs/`，本机日志在 `/tmp/sjtuow-280-*.log`。

- 初轮 `20261011-123105-5ae71a0`：`cd server && go test ./internal/content ./internal/comments ./internal/platform/media ./internal/platform/db && go run ./cmd/sjtuow apigen`，退出 1。新增测试把项目 `clock.Fixed` 类型错误写成含 T 字段的 struct；修正为 `clock.Fixed(time.Date(...))`。comments/media/db 通过。
- 专项 `20261011-123251-47196bc`：同命令退出 **0**，四包及生成成功；包括真实 HTTP 投影、头像/时间/分类/赛事/评论边界、父子关系导入两次、既有库从 00019 升级两次。
- 首次整组与对拍 `20261011-123552-280258a`：`cd server && go test ./internal/content ./internal/comments ./internal/platform/media ./internal/platform/db && cd .. && uv run python handoff/rounds/280-be-article-projection/mutate.py && sh scripts/check.sh && bash e2e/parity/run.sh --only=article --wide`，退出 **0**。35 处变异先编译成功，再被回归抓住，`MUTATIONS-OK 35`；整组通过；对拍 `PARITY 2/2 通过`。
- 最终补保护后 `20261011-123917-2538c42`：`uv run python handoff/rounds/280-be-article-projection/mutate.py && sh scripts/check.sh`，退出 **0**。最终 **36** 处可编译变异全部抓住，`MUTATIONS-OK 36`；gofmt、vet、staticcheck、govulncheck、全部 Go 测试、apigen 比对、Web 15 + 202 条与生产构建全绿，预算 96649 字节，`BUDGET-OK`、「全部通过」。新增未知栏目保护后重跑整组有明确代码变更依据。
- 对拍在最终保护前执行；仅后加保护作用于 NULL 父栏目。对拍库只读核查 `parity_parent_evidence.py` 确认全部测试文章的父编号等于旧 Wagtail 父编号，输出 `PARITY-PARENT-OK`，退出 **0**，证明新增 NULL 保护不改变这些截图数据。未重复排对拍。

真实像素差（百分比，所有正文/链接/控件/状态/标题比较无问题）：

| 身份 | 1280 浅 | 375 浅 | 1280 深 | 375 深 |
|---|---|---|---|---|
| 访客 | 0.036268% | 0.152764% | 0.036331% | 0.153032% |
| 成员 | 0.032825% | 0.131488% | 0.032883% | 0.131719% |

原始逐组合结果见 `parity-results.json`，汇总见 `parity.md`，最终保护与对拍数据的关系证据见 `parity-parent.txt`。本次对拍用 `--wide`，未用 `--strict`；所有实际行与组合均通过，不借退出码单独证明对拍成功。

## 设计偏差

无新增产品设计。保存父栏目/图库父子关系是实现旧站选择规则所必需；现有 Go 行未知关系不做猜测，正确关系由从旧库重建导入恢复。保留原草稿编辑读取行为，不在本轮扩大为整个内容公开门的重构。

## 未完成 / 顺带发现

- BE-5（分类条、简介导入/渲染、列表默认封面）、BE-6（首页聚合与 agenda）留后续轮次。
- 文章公开详情、首页、sitemap、评论读写的完整公开门矩阵仍要核查；本轮只保证新增公开相关文章/计数/相邻篇的筛选，不能把搜索可见标记的测试当作全站访问限制迁移证明。
- 旧 Go 库未知父栏目没有上下篇，须从旧库重新导入重建；新建文章的 news 栏目要由下一轮 BE-5 栏目导入补齐。
- BE-4/7/8 生成类型前端接入、真实 Go 评论写操作旅程未验证；文章对拍仅覆盖当前种子的访客/成员，不声称全身份全边界已完成。
- 本轮自查，不称独立复核；推送后检查精确 SHA 对应 CI，结果在交班消息报告。

## 改动文件

- content 的 api/article_page/store/import 与投影、导入回归。
- comments.store 的共用顶层规则与计数。
- media.pools 默认图库选择。
- 00020 迁移与迁移回归、apigen 的 gen/index.ts。
- 12 号规格、本轮 request/report/review/变异/对拍证据、STATUS、移出的最近轮次摘要。
