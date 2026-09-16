# 025 实现报告

> 本轮由实现方（Claude）自己做，用户外出。下面所有输出都是真实跑出来的。

## 结论

**完成。** 019 自己认下的「24 小时那一档重试没有真实验证过」补上了：用真实 worker 进程 + 真实 HTTP 接收端，把三种情况都跑了一遍。

**过程中我把开发库跑坏了**，原因和处理写在最后一节。数据没有损失（真实数据早就清空了，脚手架用 `init_site` 重建），但这是个值得记下来的事故。

## 验收输出

### 1. 检查与测试

```
$ ruff check . && ruff format --check .
All checks passed!
204 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ uv run python -m pytest -q
536 passed in 37.72s

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

本轮新增 4 个测试。

### 2. T1：真实 worker 执行到期的延时任务

造一条「第 7 次重试、25 小时前就该发」的投递，入队，然后起一个真实的 `manage.py run_worker`：

```
worker 日志：
Task id=c1fc535c-... path=integrations.tasks.deliver_webhook state=RUNNING
Task id=c1fc535c-... path=integrations.tasks.deliver_webhook state=SUCCESSFUL

接收端收到：
  签名校验 : True
  事件 ID  : cd5c5d3a-a0c6-4c16-9018-c9067faeef61
  事件类型 : ping
  内容     : T1 第 7 次重试到期（25 小时前），worker 应该投递

投递记录：
  id=1 succeeded 尝试=7 码=200
```

**第 7 次重试（也就是 24 小时那一档）由真实 worker 投递成功，签名校验通过。**

### 3. T3：没到点的不投递

同一个 worker 同时拿到一条「还差 20 小时到期」的任务：

```
Task id=991184f5-... state=RUNNING
Task id=991184f5-... state=SUCCESSFUL      ← 任务跑了

投递记录：
  id=2 pending 尝试=6 下次=2026-09-17 11:03:58   ← 但没投递

接收端总共收到 1 条请求                        ← 只有 T1 那条
```

任务被执行了，但 `deliver_webhook` 发现还没到点，重新排期而不是投递。**接收端一条都没多收。**

### 4. T2：任务丢了，兜底扫描捞回来

这才是 24 小时那一档的真正保障——排在一天后的任务，中间经历 worker 重启、部署、机器重启的概率不低。

模拟「任务彻底丢了」：只建投递记录，**不入队**。

```
建了一条到期的投递 id= 3 ，队列里没有对应任务
队列里 deliver_webhook 的就绪任务数: 1        ← 这 1 条是 T3 重排的，不是它

兜底扫描捞到: 1 条
扫描后就绪任务数: 2                            ← 捞回来了
```

再起 worker：

```
  第 1 条  签名=True  T1 第 7 次重试到期（25 小时前），worker 应该投递
  第 2 条  签名=True  T2 任务丢了，靠兜底扫描捞回来

投递记录：
  id=3 succeeded 尝试=8 码=200
```

第 8 次（最后一次）也投递成功了。

### 5. T4：24 小时那一档的时间计算

写成了测试 `test_the_last_retry_is_scheduled_a_day_out`：连续失败 7 次之后，断言落库的 `next_attempt_at` 距现在在 23 小时 59 分到 24 小时之间。019 验的是间隔序列常量，这条验的是**真正写进数据库、worker 会照着做的那个值**。

另外三条测试覆盖兜底扫描：捞到期的、不碰没到期的、不碰已完成的。

### 6. 清理

投递记录、客户端、调用日志全删，worker 和接收端进程都停了。全库计数只剩脚手架。

## 为什么 T1 和 T3 没有写成测试

它们依赖真实的 worker 进程和真实的 HTTP 服务，写成测试要么很慢（起进程、轮询），要么很脆（时序、端口占用）。这类验证一次做实、把输出贴进报告，比放进 CI 天天抖要好。

能写成测试的部分（时间计算、兜底扫描的筛选逻辑）都写了。

## 事故：把开发库跑坏了

### 发生了什么

第一次做 T1 的时候，接收端一直收不到东西。查下来是**机器上有 5 个 `run_worker` 进程**——都是我自己这个 session 前几轮验证时起的，一直没停。其中某个没有 `WEBHOOK_ALLOW_INSECURE_URLS=1`，抢到任务后正确地拒绝了 `http://` 地址。

为了让环境干净，我用 `pkill -f "manage.py run_worker"` 一次性把 5 个全杀了。

下一条命令就报：

```
django.db.utils.DatabaseError: file is not a database
```

文件头被写坏了（前 16 字节本该是 `SQLite format 3`，实际是一页数据），`sqlite3 .recover` 也打不开。

### 损失

**没有损失。** 库里只剩脚手架：6 个页面、5 个文章分类、5 个游戏模式、9 条排版规则、站点设置、权限组——真实数据和验证数据在前几轮早就清空了。

`migrate` + `createcachetable` + `init_site` 重建之后，逐项对过和坏之前完全一致：

```
ArticleCategory: 5 ['公告', '赛事通知', '攻略', '战报', '心得']
GameMode      : 5
TypographyRule: 9
页面树:  Root / 首页 / 资讯 / 用户协议 / 隐私政策 / 关于我们
integrity_check: ok
journal_mode   : wal
```

坏掉的文件没有删，移出了仓库，留在本次会话的 scratchpad 里备查（`db.sqlite3.corrupted-20260916`）。仓库里不留数据库文件——即使是坏的，它也有 1.7MB 且不在 `.gitignore` 的匹配范围内。

### 三条教训

1. **`pkill` 一次性杀多个 SQLite 写入进程是危险操作。** 后面重做的时候改成逐个 `kill -TERM`（优雅退出），完事再查一次 `integrity_check`，两次都是 `ok`。
2. **我 022 轮刚做完备份命令，023 轮清理时把备份全删了。** 真出事的时候，唯一能救我的东西恰好不在。「清理验证数据」这条纪律不该延伸到删掉安全网——**开发库现在一份备份都没有**。
3. **验证用的进程要当场收掉。** 5 个 worker 从 19:41 一直挂到 23:00，横跨好几轮，既污染了任务队列（019 和 025 都被它们抢过任务），也是这次事故的直接起因。

前两条已经落到了「需要确认/建议」里。第三条这轮就改了：收尾时逐个停掉并确认 `剩余 worker: 0`。

## 需要确认

1. **要不要给开发库也排一次备份？** 比如 `manage.py backup --output backups/dev` 每天一次，或者至少在跑破坏性操作前手动跑一次。生产有 cron 兜着，开发库现在裸奔。
2. 前面几轮的五个问题仍未定。

## 改动文件

```
integrations/tests/test_webhooks.py   新增 4 个测试：24 小时档的落库值、兜底扫描的三种情形
```

（代码没有改动——这轮是补验证，019 的实现本身是对的。）
