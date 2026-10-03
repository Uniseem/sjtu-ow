# 123 活动通知：新赛事、新内战一键群发（报告）

## 做了什么

1. **设计 v6.19**（先改文档）：新增 10.4「活动通知」；10.2 加两行、推翻「第一版不提供退订」（只有活动通知能退订）；10.3 主题；12.3.1 `accepts_announcements`；14.2 赛事、内战活动两行；3.8 导出加这个开关
2. **成员的开关**：`User.accepts_announcements`（默认开，迁移 `accounts/0008`）；「账号安全」新增「邮件通知」一栏（`me_notifications`，POST）；导出个人信息里有它
3. **退订**：`/unsubscribe/<签名>/`（`core.views.announcements_unsubscribe`，不用登录）：GET 问一句，POST 关掉；签名用 `django.core.signing`，篡改或账号停用返回 404；为了邮件客户端的一键退订（RFC 8058，POST 不带 CSRF 令牌）免 CSRF，地址里的签名就是凭证。路径加进首页子页面的保留词
4. **信**：`Letter.unsubscribe`：正文底部「退订活动通知：链接」，HTML 页脚「不想再收到？退订活动通知」，信头 `List-Unsubscribe`、`List-Unsubscribe-Post`；`new_tournament_letter`（「新赛事：赛事名」，比赛时间、报名截止、报名方式、限交大，报名还没开始时写开始时间）、`new_scrim_letter`（「新内战：内战名」）；两封进邮件样张页
5. **发送**（`core/services.py`）：`announcement_recipients`（在用、主邮箱已验证、开着开关；限交大的只发交大成员）；`announcement_problem`（没发布、发过了、没配 SMTP）；`announce`（权限、检查、建 `Broadcast` 记录——`core/0016`，`kind`+`object_id` 唯一约束兜底并发——写操作记录，事务提交后排任务）；`deliver`（任务里逐人发，每人自己的退订链接，期间关掉的人跳过）；`core.tasks.send_broadcast`
6. **后台**：`/admin/announce/<类型>/<编号>/` 预览页（收信人数、主题、写给自己的正文）再确认发出；赛事、内战列表的「更多」在已发布时有「通知全体成员」；发布确认页「发布后同时通知全体成员（N 人）」，默认不勾，不能发时写原因
7. **其他**：隐私政策草稿加一句活动通知和怎么关；README（赛事一节）；README 里 119 已经改掉的「人数下限保存后警告」顺手更正

## 命令输出

变异（`mutate.py`，17 处）。第一次漏了一处：「同一场再发」去掉服务里的检查后，数据库唯一约束照样挡住，测试只查了抛错没查是哪一层，改成认服务自己的说法后整组重跑：

```
baseline green, 12 tests
caught people who turned it off still get it -> test_only_active_verified_members_who_left_it_on
caught people who turned it off still get it -> test_people_who_turned_it_off_meanwhile_are_skipped
caught unverified addresses get it -> test_only_active_verified_members_who_left_it_on
caught SJTU-only events tell everyone -> test_sjtu_only_events_tell_sjtu_members_only
caught deactivated accounts can use old links -> test_a_deactivated_account_link_is_dead
caught anyone may announce -> test_no_smtp_no_drafts_no_strangers
caught drafts can be announced -> test_no_smtp_no_drafts_no_strangers
caught announcing without SMTP -> test_no_smtp_no_drafts_no_strangers
caught the same event twice -> test_a_manager_tells_everyone_once
caught nothing is queued -> test_a_manager_tells_everyone_once
caught letters carry no unsubscribe header -> test_a_manager_tells_everyone_once
caught letters carry no unsubscribe link -> test_a_manager_tells_everyone_once
caught letters carry no unsubscribe link -> test_both_notices_are_on_the_specimen_page
caught the unsubscribe link does nothing -> test_the_unsubscribe_link_asks_then_turns_it_off
caught mail clients hit the CSRF check -> test_a_mail_client_can_unsubscribe_in_one_click
caught publishing ignores the box -> test_publishing_can_tell_everyone
caught publishing always announces -> test_publishing_can_tell_everyone
caught the account switch always turns it on -> test_members_switch_it_in_account_security
caught the worker sends nothing -> test_the_worker_task_delivers
caught the worker sends nothing -> test_people_who_turned_it_off_meanwhile_are_skipped
restored and green; missed: none
```

整组检查：

```
All checks passed!
299 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
1467 passed in 186.78s (0:03:06)
```

演示站（镜像时间 `2026-10-03 19:43:25 +0200`，`Applying core.0016_broadcast... OK`，全量生成「成功 46，失败 0」）：

```
recipients 40 problem: 还没有配置邮件（全站设置里的 SMTP），发不出去。
GET 200
确定不再接收活动通知
```

（经域名打开一个演示用户的退订链接只看了 GET，没有提交。）

## 没做 / 未验证

- 真发信没验证：演示站没配 SMTP，本机用测试邮箱看了内容和信头
- 发信服务商的每日上限没有处理（成员多时一天可能发不完，失败按 10.1 重试），写在设计 10.4 里
- 文章（公告）的群发没做：这次只做用户举的赛事和内战
