# 137 赛事的选手联系方式（报告）

## 做了什么

1. `tournaments/models.py`：`Tournament.participant_contact`（迁移 tournaments/0011），说明里提醒别写进公开的详细说明
2. `tournaments/wagtail_hooks.py`：后台表单在「报名规则」后面
3. `tournaments/registration.takes_part()`
4. `tournaments/slots.actions_context()`：`participant_contact`（报了名才有）；`slots/actions.html` 在报名区最后一行显示
5. `registration_detail.html`：报名有效时，页面上方一条提示
6. 信：`notifications.contact_fact()`，开赛提醒、散人提醒用；`notifications_registration._contact()`，被报名、通过（只在通过时）、编队用
7. 邮件样张的示例赛事带上联系方式
8. 设计 v6.32，README 赛事一节
9. `tournaments/tests/test_participant_contact.py`（6 条）

## 命令输出

变异（测试机，9 处，第一次全部被抓到）：

```
baseline green, 6 tests
caught left rosters still take part -> test_who_takes_part
caught the pool does not take part -> test_the_pool_sees_it_too
caught everyone signed in sees it -> test_the_tournament_page_shows_it_to_participants_only
caught the slot leaves it out -> test_the_tournament_page_shows_it_to_participants_only
caught dead registrations show it -> test_the_registration_page_shows_it_while_live
caught the registration page leaves it out -> test_the_registration_page_shows_it_while_live
caught letters leave it out -> test_the_letters_to_participants_carry_it
caught a rejection carries it too -> test_the_letters_to_participants_carry_it
caught not in the admin form -> test_the_admin_form_has_it
restored and green; missed: none
```

整组检查（测试机）：

```
1535 条测试分成 4 片
分片 1：384 passed in 37.00s
分片 2：384 passed in 36.74s
分片 3：384 passed in 34.19s
分片 4：383 passed in 35.08s
== 迁移 (21:00:37)
No changes detected
== 生产配置 (21:00:38)
System check identified no issues (0 silenced).
== 错误页和模板一致 (21:00:39)
== Docker 镜像 (21:00:40)
构建成功：bbcef137d931
== 全部通过 (21:00:40)
```

演示站升级，迁移已应用：

```
 [X] 0011_participant_contact
```

## 没做 / 未验证

- 管理员后来才填联系方式时，已经发出的信不会补发；报了名的人在赛事页和报名详情页能看到
- 散人取消个人报名后就看不到了；已经看过的管不了
