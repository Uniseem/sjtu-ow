# 158 定时发布真正生效（报告）

## 做了什么

1. `content.services.publish_due_pages()`：有 `approved_go_live_at` 已过的版本、或 `expire_at` 已过还在线的页面时，执行 Wagtail 的 `publish_scheduled`（输出丢掉），返回是否执行了
2. `core.worker._heartbeat_loop()`：写完心跳后调用它，各自一个 `try`，出错记日志 `Failed to publish scheduled pages`，循环照常；`run_worker` 的说明跟着改
3. `core/admin_manual.py`：内容编辑加「定时上线和下线」；认证作者那一步改对位置（「推荐」→ 右侧「状态」面板的「设置计划」）
4. 设计 v6.50（12.5、16.5）；README「定时维护」
5. `content/tests/test_scheduled_publishing.py`（5 条）

## 怎么确认的问题

- `deploy/crontab.example`、演示站的 `/etc/cron.d/sjtu-ow`、整个仓库都没有 `publish_scheduled`；Wagtail 的定时发布只靠这个命令
- 在测试机上渲染文章编辑页：`go_live_at` 在 `id="schedule-publishing-dialog"` 的对话框里，打开它的按钮是「设置计划」，字段名「上线日期/时间」「过期日期/时间」；不在「推荐」标签页
- 演示站升级前 `publish_scheduled --dryrun`：没有待上线、待过期的页面，所以升级不会让旧计划突然生效

## 写测试时改掉的

1. worker 循环每步之后 `close_old_connections()`，在测试线程上直接跑循环会把测试自己的数据库连接关掉（`Cannot operate on a closed database`）。测试里把它换成空函数
2. 第一版让假的 `publish_due_pages` 自己设停止标志来结束循环。变异「worker 不调用它」时没人设标志，循环每 30 秒一轮永远不停，变异脚本卡了 10 分钟（在测试机上手动结束了那个进程）。改成由心跳设停止标志：不管 `publish_due_pages` 做什么，循环跑一轮就结束；以后真改坏了，CI 也不会卡住

## 命令输出

变异（测试机，8 处，全部被抓到）：

```
baseline green, 5 tests
caught never runs the command -> test_a_scheduled_article_goes_live_when_its_time_comes
caught never runs the command -> test_an_article_comes_down_when_it_expires
caught runs it every time -> test_a_scheduled_article_goes_live_when_its_time_comes
caught go-live times not looked at -> test_a_scheduled_article_goes_live_when_its_time_comes
caught expiry not looked at -> test_an_article_comes_down_when_it_expires
caught the worker does not call it -> test_the_worker_does_it_on_every_beat
caught a failure kills the loop -> test_a_failure_does_not_stop_the_heartbeat
caught the manual sends editors nowhere -> test_the_admin_manual_says_where_the_schedule_is
caught authors told the old place -> test_the_admin_manual_says_where_the_schedule_is
restored and green; missed: none
```

整组检查（测试机）：

```
1599 条测试分成 4 片
分片 1：400 passed in 35.02s
分片 2：400 passed in 35.53s
分片 3：400 passed in 35.84s
分片 4：399 passed in 34.05s
== 迁移 (00:59:17)
No changes detected
== 生产配置 (00:59:18)
System check identified no issues (0 silenced).
== 错误页和模板一致 (00:59:19)
== Docker 镜像 (00:59:20)
构建成功：cdbbe7949c23
== 全部通过 (00:59:20)
```

演示站升级后实测（时间是北京时间，服务器 `date` 是柏林时间）：建一篇公告草稿，「上线时间」设在一分钟后，点发布：

```
CREATED 30 live: False go_live_at: 09:02:56 now: 09:01:56
上线前公网地址: 404
03:03:24 公网地址: 200
CHECK live: True first_published_at: 09:03:21 log: wagtail.publish.scheduled 09:03:21 url: /news/scheduled-check-158/
```

到点后 25 秒由 worker 发布（日志动作是定时发布）。再过 35 秒看静态页：

```
/var/lib/docker/volumes/sjtu-ow_prerendered/_data/news/scheduled-check-158/index.html
首页静态页里有这篇: 2
资讯列表静态页里有这篇: 1
```

然后删掉这篇测试文章，40 秒后：

```
DELETED True
静态页还在: 0
首页里还有: 0
列表里还有: 0
删除后公网地址: 404
```

## 没做 / 未验证

- 过期下线只在测试里验证过（拨时钟），演示站上没有真等一篇过期
- 审核流程里通过一篇带上线时间的投稿，没有单独测。看过 Wagtail 源码：审核通过走 `wagtail/workflows.py:27` 的 `revision.publish()`，和编辑页发布一样进 `PublishRevisionAction`，上线时间在未来时只写 `approved_go_live_at`（`actions/publish_revision.py:119-123`），轮询看的就是这个字段
