# 194 AI 审核改成增量巡查（报告）

## 做了什么

1. **保存只记一笔**：`moderation.services.submit()` 建记录后不再排队送 AI；长内容的整篇正文存进新字段 `ModerationItem.full_text`（迁移 `moderation/0005`），`record()` 写入判断时把它清空，之后只留 2000 字快照
2. **巡查**（`moderation/patrol.py`，新）：
   - `review_pending()`：短内容每批 20 条，长内容逐条整篇分块，直到看完或今天的额度用完（剩下的留给下一次）
   - `send_patrol_alert()`：把看过、可能不妥（低、中、高；「无法判定」不算）、还没提醒过的列成**一封**信，发出后记 `notified_at`，同一条不再提醒
   - `enqueue_if_due()`：靠共享缓存里一个 30 分钟过期的键，最多 30 分钟排一次 `moderation.tasks.patrol`
   - 原来 `tasks.py` 里 `review_item`、`review_short_items` 的逻辑搬到这里，按巡查的方式组织
3. **worker 的心跳**：`core/worker.py` 抽出 `beat()`（心跳、定时发布、巡查排队，各自出错不影响别的），循环每 30 秒调一次
4. **收件人**：全站设置「AI 审核」里新加「巡查提醒发到」（`moderation_alert_email`），没填就发给所有在用的超级管理员；删掉「高风险内容通知」（`moderation_high_risk_notify`）和它的选项类（迁移 `core/0020`）
5. **去掉**：
   - 高风险立即发信（`record()` 里不再发）、每日汇总（`send_digest`、`moderate_scan --digest`、`deploy/crontab.example` 那一行）
   - 后台「全量扫描」按钮、它的地址和视图、夜间扫描任务和锁
   - 首页待办里「N 条内容等待复核」、审核标签「内容」上的件数
   - `moderate_scan` 命令留着，改成「把现有内容记进待看列表」
6. **后台记录页**改叫「巡查记录」，写明巡查频率、提醒发给谁、标不标处理结果都行；邮件样张页换成巡查提醒的信
7. 设计 5.5（巡查、提醒、默认信任）、10 章两张通知表、12 章设置表和记录表、14.2、19 章的设置表，附录 D v6.72；README 的 AI 一节

## 命令输出

变异（本机，11 处，全部被抓到）：

```
baseline green, 9 tests
caught long text not kept -> test_saving_puts_content_on_record_without_calling_the_ai
caught long text not kept -> test_a_patrol_reads_long_pieces_whole_and_then_forgets_them
caught full text kept for ever -> test_a_patrol_reads_long_pieces_whole_and_then_forgets_them
caught the patrol reads only the excerpt -> test_a_patrol_reads_long_pieces_whole_and_then_forgets_them
caught long pieces past the cap -> test_a_patrol_stops_at_the_daily_cap
caught unreadable counts as a finding -> test_unreadable_is_not_a_finding_and_nothing_is_mailed_on_its_own
caught a patrol every beat -> test_the_worker_queues_a_patrol_at_most_every_half_hour
caught the setting ignored -> test_the_letter_goes_to_the_address_set_in_the_settings
caught an empty letter -> test_one_letter_lists_what_a_patrol_found
caught told again and again -> test_one_letter_lists_what_a_patrol_found
caught the beat forgets the patrol -> test_the_workers_beat_queues_the_patrol
caught the page keeps quiet about the mail -> test_the_record_page_has_no_scan_button_and_says_how_alerts_come
restored and green; missed: none
```

整组检查（本机；测试机仍连不上）：

```
All checks passed!
366 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
1758 passed, 1 skipped in 321.42s (0:05:21)
```

`check --deploy` 本轮未重跑（设置模块没动）。

### 正式站

升级前备份：`已备份到 /app/backups/sjtu-ow-20261005-010005.tar.gz（210.2 MB）`。`deploy_ship.sh 194`：

```
 Image sjtu-ow-web Built 
 Image sjtu-ow-worker Built 
sjtu-ow-web 2026-10-04 19:00:18 +0200 CEST
  Applying moderation.0005_ai_patrol... OK
 Container sjtu-ow-worker-1 Starting 
 Container sjtu-ow-worker-1 Started 
全量生成完成：成功 12，失败 0，删除 0；目录占用 280 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

之后：

- `/etc/cron.d/sjtu-ow` 第 20 行是 `30 3 * * * root $DC exec -T web python manage.py moderate_scan --digest`。改前复制到 `/root/sjtu-ow-backups/cron-before-194`，用 `sed` 删掉这一行，`grep -c moderate` 变成 0。不删的话，`--digest` 参数已经没了，每天夜里都会报错
- 两个迁移都在（`True True`）；worker 升级后半分钟内排了第一次巡查，状态 `SUCCESSFUL`。正式站的 `.env` 里没有 `MODERATION_API_KEY`（`grep -c` 是 0），AI 没开，巡查什么也不做；「巡查提醒发到」是空的，有提醒时会发给超级管理员

## 没做 / 顺带发现

- 头像、投稿直接公开：195
- 图片（头像、队标、投稿图片）不送 AI，和以前一样；195 头像改成上传就生效后，只能靠管理员在后台看
- 记录列表上「无问题、已处置、忽略」这些标记和「要求作者修改」还在，都不是必做的；后台重写时再看留不留
- 正式站要用 AI 巡查，得在 `.env` 里设 `MODERATION_API_KEY`（DeepSeek 的密钥），再在全站设置里打开 AI 审核
