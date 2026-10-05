# 198 AI 巡查：没看成的不算看过、不长时间占着 worker、长文章逐块送（自查）

**结论：通过。** Claude 实现并自查，未经独立复核。

| 要求（`request.md` 验收标准） | 结果 |
|---|---|
| 失败的那条还是「还没看」、正文还在，接口好了就看完；满 3 次才放弃，连不上不计数 | `test_a_failed_review_leaves_the_item_waiting_with_its_text`、`test_failures_the_content_may_cause_give_up_at_three`；400 与 401/404/429/500 的区分 `test_only_a_plain_400_may_be_the_content` |
| 失败的结论不被沿用 | `test_a_verdict_the_ai_did_not_give_is_never_reused`（放弃的、v7.2 以前「调用失败」的都不沿用，真结论照常沿用） |
| 第一次失败就停；一分钟到了排到后面、不重复排 | `test_the_first_failure_ends_the_round`、`test_a_patrol_stops_starting_requests_when_its_minute_is_up`、`test_a_long_piece_waits_for_the_next_go_too`、`test_the_rest_is_queued_behind_other_work_and_the_beat_waits` |
| 批的大小跟着最多输出；长文章逐块、高风险提前停 | `test_a_batch_is_as_large_as_the_output_limit_holds`、`test_a_long_piece_goes_a_chunk_per_request_and_a_high_risk_ends_it` |
| 待办、巡查记录页、「试一下 AI」 | `test_the_owner_hears_when_the_ai_cannot_be_reached`、`test_the_review_list_says_what_is_waiting_and_why`、`test_trying_says_what_to_change` |
| 拆掉就红、整组全绿、升级前备份 | 37 处变异全部被抓到（第一次漏的一处补了测试后重跑）；测试机 1811 条全过；备份后升级 |

## 自己挑的刺

- **「一分钟」量的是什么时候不再发新请求，不是硬上限**：每发一个请求（短内容一批、长文章一整篇）之前看一次。一个请求最坏要 超时 × 3 + 4 秒（默认 94 秒），一篇很长的文章要把所有块看完才让出 worker。这是故意的：在块中间停下，下次从第一块重来，一篇长文章可能永远看不完
- **HTTP 400 算内容的失败**：服务商的内容拦截是 400，不算的话一条被拦的内容会每轮都排第一、把巡查永远卡住。代价：附加请求参数填错（服务商不认的参数也是 400）的那段时间，每轮会让一批内容的次数加一，满 3 次的记成「无法判定」，以后不会自动重看。待办和「试一下 AI」会马上带着服务商的原话显示 400，一般在第三轮之前就会被发现
- **截断也算内容的失败**：思考模式没关导致的截断其实是配置问题，同上，次数会慢慢涨。好在一轮只花一次调用，又按失败次数排在后面，积压的内容是一轮一条地摊开试，不是一下子全放弃
- **接着看的任务和提醒信**：积压很多时（`moderate_scan` 之后）一轮会接着看几个小时，到当天额度用完。信最多晚 30 分钟（最早一条可疑内容等满 30 分钟就先发）
- **「每条约 60 token」是估的**：没在 DeepSeek 的真回答上量过；正式站填了密钥以后，巡查记录里的输出 token 数可以拿来核对
- 「超时」的提示认的是 Python 报错里的英文 `timed out`
