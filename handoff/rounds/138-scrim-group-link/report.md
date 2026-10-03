# 138 内战说清楚分队结果发到哪个群（报告）

## 做了什么

1. `scrims/services.community_group_url()`：全站设置的 `qq_group_url`
2. `scrims/slots.actions_context()`：报了名才给 `group_url`；`slots/actions.html` 在「当前分队」下面一行
3. `scrims/notifications.scrim_reminder_letter(scrim, placement, group_url)`：有链接加「社团 QQ 群」一行；`scrim_reminder()` 读一次传给每封
4. 邮件样张「内战开始提醒」带上分队和群链接
5. 设计 v6.33，README 内战一节
6. `scrims/tests/test_my_placement.py` 加 3 条

## 命令输出

变异（测试机，5 处，第一次全部被抓到）：

```
baseline green, 3 tests
caught the slot gets no link -> test_signed_up_players_are_told_which_group
caught the slot leaves it out -> test_signed_up_players_are_told_which_group
caught said even with no link -> test_no_group_link_set_nothing_said
caught the reminder leaves it out -> test_the_reminder_links_the_group
caught the reminder is not given the link -> test_the_reminder_links_the_group
restored and green; missed: none
```

整组检查（测试机）：

```
1538 条测试分成 4 片
分片 1：385 passed in 34.36s
分片 2：385 passed in 34.99s
分片 3：384 passed in 33.50s
分片 4：384 passed in 34.89s
== 迁移 (21:06:45)
No changes detected
== 生产配置 (21:06:46)
System check identified no issues (0 silenced).
== 错误页和模板一致 (21:06:47)
== Docker 镜像 (21:06:48)
构建成功：c06f6603703a
== 全部通过 (21:06:48)
```

演示站已升级（没有迁移）。演示站全站设置里 QQ 群链接还没填（122 的上线清单里列着），所以现在看不到这一行。

## 没做 / 未验证

- 「群号」只有链接没有号码：全站设置里只有链接这一项
