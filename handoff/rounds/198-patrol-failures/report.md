# 198 AI 巡查：没看成的不算看过、不长时间占着 worker、长文章逐块送（报告）

## 做了什么

用户 10-05 问超时和返回结果怎么处理，回答里列了三处毛病，用户：「修吧」。

1. **设计**（先改文档，v7.2）：5.5.3 改「结构化输出」「长文本分块」「增量巡查」三条，新加「一批几条按输出上限算」「没看成的不算看过」「不长时间占着 worker」三条，「关闭思考模式」补一句思考没关时会怎样；5.5.4 提醒信和「试一下」；12 章全站设置表「最多输出 token」；12.14.1 加三个字段；14.1 待办；附录 D
2. **服务商**（`moderation/providers.py`）：`ProviderResult` 多了 `error`（这次请求没拿到能用的回答）和 `counts`（失败可能是内容引起的）；`Verdict` 多了 `error`（回答漏掉了这一条）
   - 算「没拿到」的：试满 3 次仍连不上、超时、HTTP 错误、响应不是 JSON（`counts` 只有 HTTP 400 为真）；`finish_reason=length` 的截断回答（不管内容看着全不全）；不符合约定结构；回答里一条对得上编号的都没有（后三种 `counts` 为真）
   - 模型拒答、空回答仍是「无法判定」的结论（设计原来就这么定，留给人看）
   - HTTP 错误带上服务商自己的说明：`调用失败：HTTP 400：Content Exists Risk`（取 `error.message`，最多 160 字）
3. **记录**（`ModerationItem` 加 `attempts`、`last_error`、`failed_at`，迁移 `moderation/0006`，只加字段）
4. **`moderation/services.py`**
   - `note_failure()`：不填审核完成时间、不清整篇正文，记下原因和时间；`counts` 为真才加次数，满 `GIVE_UP_AFTER = 3` 次记成「无法判定」，理由「AI 没看成（试了 3 次）：原因」
   - `recent_verdict()`：不拿「AI 没看成」的，也不拿 v7.2 以前「调用失败：」的
   - `batch_size()`：最多输出 ÷ 60，夹在 1 到 20 之间；`pending_short_items()`：没算过失败的按时间凑一批，没有了才拿一条算过失败的单独送（按失败次数、失败时间排）；`pending_long_items()` 也按失败次数排在后面
   - `waiting()`：还没看的条数、其中上次没看成的条数和最近一次的原因
   - `try_hint()`：「试一下 AI」的提示，原来的 401/403/404 之外加了截断（调大最多输出或关思考）、超时（调大超时或关思考）
5. **`moderation/patrol.py`**
   - 短内容一批一个请求、长文章一块一个请求（有一块高风险就停，token 数累加）；请求没拿到回答就 `note_failure` 并返回「停」，这一轮到此为止
   - `review_pending()` 返回 `Round(reviewed, stopped)`；每发一个请求（短内容一批、长文章一篇）之前看有没有到 `PATROL_SECONDS = 60` 秒
   - `run()`：因为到点停的，`follow_up()` 把剩下的排成优先级 -10 的巡查任务（默认 0，worker 按优先级取），并刷新巡查的缓存键，定时巡查不再另排；提醒信等这一轮看完再发，除非最早一条可疑内容已经等了 30 分钟
6. **哪里能看到**：超管首页待办「AI 审核有 N 条内容没看成（原因），下次巡查再试；检查全站设置里的 AI 审核，点「试一下 AI」」，链到全站设置，AI 审核关着时不显示；巡查记录页「还有 N 条等着看」和一条黄色提示（原因、提示、满 3 次才记成「无法判定」）；后台手册一句措辞
7. README「AI 内容审核」：批的大小、没看成的不算看过、超时是整个回答生成完的时间、不长时间占着 worker

v7.2 以前已经记成「调用失败」的记录没有重新打开（整篇正文已经清掉了，重看只能看前 2000 字）；正式站上这类记录是 0 条（见下）。

## 测试

- 新文件 `moderation/tests/test_patrol_failures.py`，20 个测试函数（参数化后 24 条）：没拿到回答是错误不是结论、只有 400 算内容的（400/401/404/429/500 各一次）、截断、结构不对、拒答仍是结论、漏掉的一条再试；失败后记录还在等、正文还在、接口好了就看完；可能怪内容的满 3 次放弃、连不上不计数；没看成的结论不沿用；第一次失败就停；算过失败的单独送、排在后面（短、长各一条）；漏掉的一条留着、其余照常记；批的大小跟着最多输出；长文章逐块、高风险提前停、token 累加；到点不再发请求（短、长）；到点排一个低优先级任务、定时巡查不再另排、因为别的原因停的不排；接着看时信等满 30 分钟；「试一下」的三种提示；巡查记录页的条数和提示
- 改了的旧测试：`review_pending()` 现在返回 `Round`（3 处 `.reviewed`，1 处 mock 返回值）；超管待办那条改测「N 条内容没看成」（还在等的才算、看完就少、AI 关着不显示、内容编辑看不到）

## 命令输出

测试机整组检查：

```
== pytest (06:20:50)
1811 条测试分成 4 片
分片 1：453 passed in 57.56s
分片 2：453 passed in 58.20s
分片 3：453 passed in 55.96s
分片 4：452 passed in 58.80s

== 迁移 (06:21:55)
No changes detected

== 生产配置 (06:21:57)
System check identified no issues (0 silenced).

== 错误页和模板一致 (06:21:58)

== Docker 镜像 (06:21:59)
构建成功：8b51204d8955

== 全部通过 (06:21:59)
```

变异（测试机，`mutate.py`，37 处、39 次检查）。第一次漏了一处：

```
MISSED read items counted as waiting -> test_the_review_list_says_what_is_waiting_and_why
```

巡查记录页那条测试里所有记录都还没看，「数全部」和「数没看的」一样多。加了一条已经看过的记录，本机先确认这一处会红：

```
baseline 0
mutated 1
restored 0
```

再在测试机上整套重跑：

```
mutations: 37 not applying: none
baseline green, 21 tests
caught read items counted as waiting -> test_the_owner_hears_when_the_ai_cannot_be_reached
caught read items counted as waiting -> test_the_review_list_says_what_is_waiting_and_why
restored and green; missed: none
```

（日志 `/srv/sjtu-ow-check/runs/20261005-142447-9f8ba96.log`：39 行 `caught`、0 行 `MISSED`。）

浏览器（测试机，`journey.py pages`）：

```
看了 163 个地址，0 处有问题
全部走通
```

## 部署（正式站）

有迁移，先备份：

```
已备份到 /app/backups/sjtu-ow-20261005-143256.tar.gz（210.8 MB）
```

`deploy_ship.sh 198`（14 个文件，这轮没有删文件）：

```
 Image sjtu-ow-worker Built 
 Image sjtu-ow-web Built 
  Applying moderation.0006_patrol_failures... OK
 Container sjtu-ow-worker-1 Started 
全量生成完成：成功 12，失败 0，删除 0；目录占用 280 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

```
sjtu-ow-web 52 seconds ago
sjtu-ow-worker 52 seconds ago
sjtu-ow-worker-1 Up 41 seconds
sjtu-ow-web-1 Up 41 seconds (healthy)
```

正式站真实数据上只读检查（`/root/smoke198.py`，请求工厂调视图；前两行是状态码、地址、页面里有没有「等着看」「没看成」）：

```
200 /admin/moderation/ False False
200 /admin/ False False
old failed calls on record: 0
waiting / failed / last: (0, 0, '')
batch size: 10 patrol seconds: 60
to-do: (0, '') enabled: False
columns: ['attempts', 'last_error', 'failed_at']
```

正式站还没有 AI 密钥，没有在等的内容，所以两页都不显示新的两行，符合预期。

## 没做 / 没验证

- 没有真的接 DeepSeek（正式站没有密钥，测试里服务商都是假的）。「每条回答约 60 token」是按提示要求的字段估的，没在真回答上量过；估少了，一批会被截断一次，这批的内容之后改成一条一条送，不丢内容，只是多花几次调用
- 长文章失败时不记已经看过的块，下次从第一块重来
- 流式接收没做（`request.md`「不做」）
