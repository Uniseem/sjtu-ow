# 281 实现报告

## 结论

BE-5/6 后端实现与前端接入完成、自查通过；40处Go变异、5处Web变异、最终整组、浏览器与严格对拍全绿。首页访客/成员、资讯访客四组合3/3通过，最大像素差0.001586%，资讯四组合像素差均0。真实业务旅程与全身份边界未全部验证，不标整页完成。

## 逐条结果

1. 导入 `content_articleindexpage` 到 pages/news_index，保留已发布简介、SEO、发布时间、父编号、live/unpublished 标志；栏目修订独立导入，最新修订引用指向最新草稿。重复导入不覆盖已发布值；读写失败返回错误，单个栏目事务回滚。
2. 资讯 API 只读已发布公开 news 栏目与其直属文章，分类过滤按旧 named()/sort_order/name；简介由唯一 Markdown 渲染器输出，标题/SEO照已发布值。文章按首发/最近发布倒序（含微秒），超页/负页回最后页；public URL 的零页/非法/大整数由 loader 按旧 paginator 语义转换。空结果为数组。
3. 文章卡批量补公开作者头像与编号，默认头像按位置图库选择，停用账号不出头像；复用默认封面池，包含子目录。News与Home接生成类型，BE-5临时类型删除；相关文章也使用同一批量卡投影。
4. 首页删除不存在的 takes_individuals/article_revisions/home_pins 字段引用与吞错路径，使用真实字段；查询错误传播。成员统计只计活跃、邮箱已验证；成立年龄按上海日期、平年闰日周年落2月28日，未来日期不显示。
5. 推荐赛事复用领域阶段/公开规则与请求时钟；开放最先截止，未结束最先开始，最近结束。真实对拍发现截止并列的旧默认排序是报名开始/编号倒序，已修并补独立并列回归，取消/草稿不入推荐。事实行的月日、开赛日、已通过/已编成队数照旧模板。
6. 未来已发布内战最多5、截止/5v5与6v6容量/报名人数正确；资讯最多4、最多3篇置顶且去重；公告最多5、战队只读未解散的最多6。日期显示复用上海时间函数，月初日期保留前导零，空日期不造0。
7. 首页复用 agenda.Items，访客/停用返回[]，成员仅有本人的安排；报名链接修成旧 `/registrations/<id>/`。独立agenda接口仍保留，Home loader移除额外agenda请求，页面接口+session两请求预算有SSR回归。
8. 首页推荐默认封面保留旧漂移动效类，显式封面保持静止；有真实SSR输出和拆掉类就红的Web变异。
9. 新契约由测试机 `sjtuow apigen` 生成取回；未加依赖、未改旧站、未部署。长期分工不变，前端接入范围例外记录在request。

## 验收输出

全部在测试机后台执行，日志 `/srv/sjtu-ow-check/runs/`，本机 `/tmp/sjtuow-281-*.log`，未用本机兜底。

- `20261011-130002-f954a64`：原有 content/agenda/tournaments 整包通过，apigen成功，退出0。
- `20261011-130459-457ee45`：新增回归退出1，测试数据漏必填 battletag/报名位置，直接DROP被外键保护拒绝。补齐真实必填数据，读取故障注入改为重命名表，保留外键保护。
- `20261011-130841-dab2074`：新增后端回归与apigen全绿，退出0。
- `20261011-131517-73d46f4`：变异“简介直接输出原文”使html变量未使用，编译失败，退出1；修为保留变量使用。不把编译失败算抓到规则。
- `20261011-131652-c46e0e7`：38处可编译Go变异全部抓住，随后Web退出1；新增SSR夹具宣称24篇却给空列表，导致不渲染分页器。修为13篇且末页1篇。
- `20261011-131914-9a99d87`：整组、4处Web变异、browser-check（评论23/23）通过，但home/news严格对拍退出1，只有资讯1/3通过。首页在截止并列时选了个人赛而旧站选整队赛；正文、链接、像素差揭示真实实现缺陷。保留 `parity-before-tie-fix.md/json`，修成旧Meta排序并补两处Go变异。
- `20261011-132423-86d14f6`：最终40处可编译Go变异全部抓住；新动效测试退出1，仅因Vue合并类名的顺序不同。改为验证真实类集合，未删断言。
- `20261011-132700-977329a`：最终整组通过（Web 15+206、生产构建、apigen对比，预算96703字节）；5处Web变异通过；`BROWSER-CHECK-OK`、`COMMENTS-BROWSER-CHECK 23/23`、`PARITY 3/3 通过`，整个后台串行任务退出 **0**。所有对拍正文/链接/控件/状态/标题与坏图检查均通过，原始结果见 `parity-results.json`，汇总见 `parity.md`。此次严格对拍发生在最终SUT上。

| 地址/身份 | 1280浅 | 375浅 | 1280深 | 375深 |
|---|---|---|---|---|
| 首页访客 | 0.001586% | 0.000685% | 0.000142% | 0.000685% |
| 首页成员 | 0.000619% | 0.000589% | 0.000128% | 0.000589% |
| 资讯访客 | 0% | 0% | 0% | 0% |

实际命令：

```sh
# 后端专项/生成
cd server && go test ./internal/content ./internal/agenda ./internal/tournaments && go run ./cmd/sjtuow apigen
# Go规则变异
uv run python handoff/rounds/281-be-news-home/mutate.py
# 最终收尾（通过 remote-check.sh run 在后台执行）
sh scripts/check.sh && uv run python handoff/rounds/281-be-news-home/mutate-web.py && cd web/apps/site && node browser-check.mjs /usr/bin/chromium && cd ../../.. && bash e2e/parity/run.sh --only=home,news --wide --strict
```

## 设计偏差

无新产品设计。并列赛事排序依据旧Tournament.Meta与真实对拍修正；旧模板与数据库校验保持原样。

## 未完成 / 顺带发现

- 全内容公开入口与评论读写的完整访问限制矩阵、BE-4/7/8前端完整类型接入、评论真实Go写操作旅程仍未验证；首页和资讯的截图证据不能代替这些。
- F2真实图片样张与默认池场景全量视觉验收仍待补，不能因给了图片ID就标完成。
- 本轮为自查，未做独立复核。推送后检查精确SHA对应CI，结果在交班消息报告。

## 改动文件

content：news/import_news/news_authors/home_store与DTO、导入、相关文章卡投影及回归；agenda链接、tournaments推荐候选；Home/News/pending-api及SSR回归；apigen生成index.ts；12号规格、STATUS和本轮证据。
