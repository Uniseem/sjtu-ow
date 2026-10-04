# 165 定时发布的文章可以「上线时通知全体成员」（报告）

## 做了什么

1. `core.models.Broadcast.waits_for_publish`（迁移 `core/0019`）：已安排、等文章上线才发
2. `core/services.py`
   - `going_live_at(kind, obj)`：设了计划、还没上线的文章的上线时间（看版本上的 `approved_go_live_at`）；别的情况返回 None
   - `announcement_problem()`：没上线但有计划的文章不再拦；已安排过的提示「已经安排在上线时通知全体成员，同一篇只发一次」
   - `announce()`：有计划的文章只建记录（`waits_for_publish=True`，人数先记 0），不排队发信；日志里多记 `on_publish`
   - `send_waiting(kind, obj)`（新）：把等着的那条改成不等、记上此刻的收信人数，再排队发出；没有等着的就什么都不做
3. `content/signals.on_page_published`：文章上线时调 `send_waiting`（定时发布、手动发布都走这里）
4. `content/wagtail_hooks.py`：有计划的文章在页面列表和编辑页「更多」里是「上线时通知全体成员」。先看页面自己的 `go_live_at`（不用查询），在将来才去查版本，列表里的草稿不会每行多一次查询
5. 预览页（`announce.html`）：有计划时写「这篇文章 X 月 X 日 HH:MM 上线，到时自动发出。收信人数按上线那一刻算，现在是 N 人」，按钮「上线时发」；成功提示换成「已安排……」
6. 设计 v6.54（10.4）；README；后台手册内容编辑「定时上线和下线」那一步加一句
7. `core/tests/test_announcements.py` 加 2 条

## 命令输出

变异（测试机，11 处，全部被抓到）：

```
baseline green, 3 tests
caught planned articles refused -> test_a_planned_article_is_announced_when_it_goes_live
caught planned articles refused -> test_publishing_a_planned_article_by_hand_sends_it_too
caught drafts count as planned -> test_drafts_and_other_roles_cannot_announce_articles
caught sent at once -> test_a_planned_article_is_announced_when_it_goes_live
caught sent at once -> test_publishing_a_planned_article_by_hand_sends_it_too
caught counted when planned -> test_a_planned_article_is_announced_when_it_goes_live
caught planned twice -> test_a_planned_article_is_announced_when_it_goes_live
caught never sent on publish -> test_a_planned_article_is_announced_when_it_goes_live
caught never sent on publish -> test_publishing_a_planned_article_by_hand_sends_it_too
caught sent again on every publish -> test_publishing_a_planned_article_by_hand_sends_it_too
caught count kept from planning -> test_a_planned_article_is_announced_when_it_goes_live
caught no button for planned articles -> test_a_planned_article_is_announced_when_it_goes_live
caught button says send now -> test_a_planned_article_is_announced_when_it_goes_live
caught preview without the time -> test_a_planned_article_is_announced_when_it_goes_live
restored and green; missed: none
```

整组检查（测试机）：

```
1620 条测试分成 4 片
分片 1：405 passed in 35.71s
分片 2：405 passed in 36.09s
分片 3：405 passed in 34.58s
分片 4：405 passed in 36.64s
No changes detected
== 全部通过 (02:38:08)
```

演示站升级（迁移 `Applying core.0019_broadcast_waits_for_publish... OK`）后，在服务器上以演示站的内容编辑「林间小鹿」（测试客户端 `force_login`）建一篇明天上线的公告草稿、看列表和预览页，再删掉：

```
内容编辑: 林间小鹿
列表里有「上线时通知全体成员」: True
预览: None
提示: 还没有配置邮件（全站设置里的 SMTP），发不出去。
按钮: True
删掉了: True 通知记录: 0
```

演示站没配 SMTP，预览页显示的是这条提示（有问题时不显示上线时间那句，按钮是灰的），和当场发的情况一样。真的到点发信只在测试里验证。

## 写测试时改的

「再上线一次不会再发」第一版没包 `django_capture_on_commit_callbacks`，提交后的回调根本不执行，改坏了也照样绿。包上以后变异「每次上线都发」被抓到。

## 没做 / 未验证

- 取消计划（Wagtail 的「取消计划」）后，已安排的通知还留着，等文章哪天手动发布时照样发出。没做「取消安排」：只发一次、发在文章上线时，这个行为和按钮名字一致
- 只做了文章：赛事、内战没有定时发布
