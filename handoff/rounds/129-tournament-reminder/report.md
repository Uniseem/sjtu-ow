# 129 赛事开始前提醒参赛队员（报告）

## 做了什么

1. `Tournament.reminder_sent_at`（迁移 tournaments/0010）、全站设置 `tournament_reminder_hours`（默认 24，「社区参数」里，迁移 core/0018）
2. `tournaments/services.py`：`reminder_offset_hours()`、`reminder_time()`、`schedule_reminder()`；`after_change()`（发布、保存都走这里）末尾安排提醒。没填比赛时间、不是已发布、已经发过、比赛时间已过的不安排
3. `tournaments/tasks.py`（新）：`send_tournament_reminder`，照内战提醒，重读赛事：
   - 没了、不是已发布、没时间、发过了、已开赛就不发
   - 还没到时间就改到该发的时候
   - 发出去至少一封才记 `reminder_sent_at`
4. `tournaments/notifications.py`：`tournament_reminder_letter()`（每人一封：比赛时间、你的队伍、你的游戏 ID，临时队伍写「告诉赛事管理员」，战队写「告诉队长」）、`tournament_reminder()`（已通过报名、占名额的名单行，账号在用且有邮箱）；`_moment` 改名 `moment` 给报名信用
5. 「报名已通过」的信：填了比赛时间就加一行「比赛时间」
6. 邮件样张页加「赛事开始提醒」；样张赛事带上比赛时间（「报名通过」样张也显示出来）
7. 设计 v6.24
8. 顺带修的（不在 request 里，都是这轮踩到的）：
   - **`/healthz` 碰到只读数据库会 500**：整组检查时分片里冒出来的。读心跳走数据库缓存，缓存读到过期条目会顺手删掉，数据库只读时这一删就抛异常。`run_health_checks()` 用 `_reported()` 包住心跳和积压两项，数据库出错时报「数据库出错：……」、整体 503。新测试 `test_a_read_only_database_with_an_expired_heartbeat_still_answers` 先写一条过期的心跳再把库变只读，稳定复现
   - **0008 的迁移测试不迁回去**：`test_the_old_switch_becomes_the_mode` 把库退到 0008 就结束，后面同进程的测试用的是缺新列的表。以前 0008 之后的迁移没改表结构所以没事，0010 加了列就红了。现在断言用 0008 时的模型，`finally` 迁回最新
   - `scripts/remote-check.sh`：退出码改在任务脚本外面写，任务脚本本身起不来时本机也能结束（试过 `exit 3` 和语法错，分别退出 3 和 2）

## 演示站：误删了 `docker-compose.vps.yml`，已恢复

部署时报：

```
open /srv/sjtu-ow/deploy/docker-compose.vps.yml: no such file or directory
```

原因在我：127 推送后对齐服务器时，我删了「除 `Caddyfile.vps` 和 `.env.bak*` 以外的全部未跟踪文件」，之前看的 `git status --porcelain | head` 正好截在第 10 行，没看到 `deploy/docker-compose.vps.yml` 和它的备份 `.bak-202610032012`（另一个会话 10-03 调资源时留的），两个都删了。运行中的容器不受影响，演示站一直能访问；129 第一次部署的构建、迁移、重启都失败了。

恢复：照本会话前面读到过的全文重写（含另一个会话加的 `web: cpu_shares: 2048`）；备份是同样内容去掉最后的资源分配三行，写出来 674 字节，和原备份的大小一致。之后：

```
config-ok
 Image sjtu-ow-web Built 
sjtu-ow-web 2026-10-03 21:48:09 +0200 CEST
  Applying core.0018_tournament_reminder... OK
  Applying tournaments.0010_tournament_reminder... OK
全量生成完成：成功 46，失败 0，删除 0；目录占用 1606 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"}, "disk": {"ok": true,
2048
domain 200
```

（`2048` 是 `docker inspect` 读到的 `CpuShares`）

防再犯：
- 服务器 `.git/info/exclude` 加了这三样本机文件
- `/root/deploy_ship.sh` 先检查 Compose 配置、再检查清单在不在
- 新的 `/root/align_after_push.sh N` 只放回清单里的文件再 `git pull`
- AGENTS.md 记了这件事

演示站上已发布、比赛时间在以后的两场赛事补安排了提醒（升级前发布的赛事要保存一次才会安排）：

```
2 2026 新生杯 2026-11-08 13:00:00+08:00 提醒时间 2026-11-07 13:00:00+08:00
1 2026 秋季校内杯 2026-10-25 13:00:00+08:00 提醒时间 2026-10-24 13:00:00+08:00
```

worker 能跑这个新任务（立刻排一个，还没到时间，它自己改期）：

```
SUCCESSFUL rescheduled ['tuMeVYe5L8rwVEBImS8DuqKq6UXyuWGx']
```

## 命令输出

变异（测试机，16 处，第一次全部被抓到）：

```
baseline green, 8 tests
caught saving does not arrange it -> test_publishing_arranges_it_a_day_before
caught the setting is ignored -> test_publishing_arranges_it_a_day_before
caught arranged without a start time -> test_no_start_time_no_reminder
caught the task runs without a start time -> test_no_start_time_no_reminder
caught sent twice -> test_each_approved_player_gets_their_own
caught cancelled still reminds -> test_a_later_start_or_a_cancellation_holds_it
caught early, not rescheduled -> test_a_later_start_or_a_cancellation_holds_it
caught marked sent with nobody to tell -> test_only_approved_rosters_hear
caught pending rosters hear too -> test_only_approved_rosters_hear
caught players who left hear too -> test_players_who_left_or_were_deactivated_are_skipped
caught deactivated accounts hear too -> test_players_who_left_or_were_deactivated_are_skipped
caught the letter leaves out the game ID -> test_each_approved_player_gets_their_own
caught the approval leaves out the time -> test_the_approval_says_when_to_show_up
caught a rejection gives a time too -> test_the_approval_says_when_to_show_up
caught /healthz lets a database error through -> test_a_read_only_database_with_an_expired_heartbeat_still_answers
caught no specimen -> test_the_reminder_is_on_the_specimen_page
restored and green; missed: none
```

（baseline 那行是加 `/healthz` 那一处之前跑的第一遍打的；加上之后又整个跑了一遍，最后四行是第二遍的输出，同样 `missed: none`）

整组检查（测试机）：

```
1496 条测试分成 4 片
分片 1：374 passed in 31.04s
分片 2：374 passed in 31.74s
分片 3：374 passed in 32.59s
分片 4：374 passed in 31.41s
== 迁移 (19:45:32)
No changes detected
== 生产配置 (19:45:33)
System check identified no issues (0 silenced).
== 错误页和模板一致 (19:45:34)
== Docker 镜像 (19:45:35)
构建成功：5d5ded22d9c1
== 全部通过 (19:45:35)
```

## 没做 / 未验证

- 演示站没配 SMTP，提醒到时候发不出去（会在 worker 日志里记失败）
- `schedule_reminder` 里「已经发过」「比赛时间已过」两个提前返回没有专门的测试：去掉它们，任务自己也会判断后什么都不做（等价）
- 整队报名的队员仍然收不到「通过 / 驳回」（8.3 的分工），提醒解决的是「参没参上、几点开始」
