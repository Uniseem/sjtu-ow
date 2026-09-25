# 070 实现报告

## 结论

**完成。** 设计 v1.7.1；`Registration.team` 可空，临时队伍是没有战队的已通过报名；后台「队伍编排」页照内战的拖拽页做，服务端校验整张版面；退出、解散、三封邮件、账号注销的连带处理都落地。40 条新测试，18/18 处守卫变异被抓到，全量测试通过。

## 逐条结果

| 任务 | 结果 |
|---|---|
| 设计 v1.7.1 | 8.8.2 去掉「070 轮实现」标记并补两句（移回散人池记 `sync_roster`；缺段位标出）；12.8.2 `team` 可空、`team_name` 非空约束、唯一约束说明；12.8.4 三个动作、`member` 操作方、快照说明；10.2 三封邮件、赛事取消的收件人；13.4 `/registrations/<id>/leave/`；13.13.4 事件；14.2 报名审核只读说明和「队伍编排」行；附录 B、D |
| 模型与迁移 | `Registration.team` `null=True`（PROTECT 不变），检查约束 `registration_has_a_name`，`is_adhoc` 属性；`RegistrationAction` 加 `form_team` / `member_left` / `dissolve`，`ActorType` 加 `member`；`IndividualSignup.rank_pairs` 供编排页；迁移 `tournaments/0007_adhoc_teams` |
| `form_teams()` | 输入是整张版面（每支临时队伍的队名和散人 id 列表，可带一支新队伍）。先校验：散人属于本赛事、一人一队、每队不超过 `roster_max`、队名 1–16 字且在本赛事有效报名里唯一、版面内不同名；再逐人跑 `member_problems()` 和 `existing_roster_conflict()`。写入分两步：**先把要离开的人从各队移出**（否则一个人从 A 队挪到 B 队会撞「同一赛事每人只在一个有效名单」的唯一约束），再建队或改队。新队记 `form_team`；改动记 `sync_roster`（版本 +1）；没变化不写。和保存前比较名单，所以「有人被移出」也算改动 |
| `leave()` / `dissolve()` | 退出**删名单行**（`_set_status` 会整体重写 `is_active`，标记会复活）、散人记录回池、日志 `member_left`（操作方队员）、版本 +1；最后一人退出自动解散（系统，备注写明）。解散：成员回池，状态改「已撤回」，日志 `dissolve`。`withdraw()` 对临时队伍拒绝 |
| 假设 `team` 非空的地方 | `_refresh_public_pages`（无战队页可刷）、`roster_differs_from_team`（返回 False）、`visible_to`（只查名单）、`notifications_registration._captain` 改为 `recipients()`（临时队伍 = 在册成员）、`services.active_registration_captains` 改为 `cancellation_recipients()`（含临时队伍成员）、`approved_teams` 加 `is_adhoc`、`review_admin.local_actions` 对临时队伍不给按钮、`review_detail` 不比对战队成员、模板三处 |
| 编排页 | `tournaments/teams_admin.py` + `templates/tournaments/admin/teams.html`、`_zone.html`、`_card.html`；`static/js/tournament-teams.js`（从 `scrim-split.js` 派生：满员拒绝、`data-blocked` 的卡片拒绝、低于下限标红、按钮移动）；复用 `scrim-split.css` 加 `tournament-teams.css`；固定一个空的「新队伍」区块；解散是单独的表单。赛事列表「队伍编排」按钮（开放个人报名的赛事）；审核详情页指回编排页 |
| 邮件 | `core.mail.emails_for_groups()` 从 `moderation.notifications.reviewer_emails()` 泛化（moderation 改用它）；`adhoc_team_formed`（每个新编入的成员）、`adhoc_members_returned`（移回或解散）、`adhoc_member_left`（赛事管理员组 + 超管）。裸主题 |
| 账号 | 注销时对草稿或已发布赛事里的临时队伍先 `leave(enforce_deadline=False)` 再删个人报名 |
| 前台 | 报名详情页临时队伍分支（无战队链接、「退出队伍」）；赛事页已报名列表临时队伍不带链接、标「临时队伍」；散人名单只显示还没编入的人（069 的 `individual_pool()` 加了过滤） |
| 测试 | `tournaments/tests/test_adhoc_teams.py` 40 条：建队与邮件、赛事页显示、不进战队列表、九种拒绝、低于下限可存、移动成员、改名、同版面不写、清空即解散、解散、战队报名不能解散和退出、退出（截止前后、路人、最后一人、退出后再编入、撤回被拒）、前台三条、编排页六条（权限、契约属性、保存、拒绝、解散、审核页只读）、取消赛事邮件、注销、预渲染、两支队伍共存、导出 |

## 验收输出

```
$ uv run ruff format . && uv run ruff check .
221 files left unchanged
All checks passed!

$ PYTHONUTF8=1 uv run pytest -q tournaments/tests/test_adhoc_teams.py tournaments/tests/test_individual_signup.py
77 passed in 25.31s

$ PYTHONUTF8=1 uv run pytest -q
811 passed in 118.48s (0:01:58)

$ uv run python manage.py makemigrations --check --dry-run; echo $?   →  0
$ ... uv run python manage.py check --deploy; echo $?                →  0

$ uv run python manage.py makemigrations tournaments --name adhoc_teams
  tournaments\migrations\0007_adhoc_teams.py
    ~ Alter field team on registration
    ~ Alter field action on registrationstatuslog
    ~ Alter field actor_type on registrationstatuslog
    + Create constraint registration_has_a_name on model registration
```

**变异（脚本 `mutate_070.py`，本轮目录；分两次跑，第一次前 7 个，第二次 `MUTATE_START=7` 跑剩下的）**

```
✓ 被抓到 超员不再拒绝 | 2 failed, 38 passed in 25.13s
✓ 被抓到 队名为空也收 | 2 failed, 38 passed in 35.92s
✓ 被抓到 队名超长也收 | 1 failed, 39 passed in 23.93s
✓ 被抓到 队名重复也收 | 1 failed, 39 passed in 23.92s
✓ 被抓到 同一版面里同名不查 | 1 failed, 39 passed in 24.05s
✓ 被抓到 一人两队不查 | 1 failed, 39 passed in 23.67s
✓ 被抓到 别的赛事的散人也收 | 1 failed, 39 passed in 23.96s
✓ 被抓到 编队时不再跑队员校验 | 1 failed, 39 passed in 23.48s
✓ 被抓到 编队时不再查名单冲突 | 1 failed, 39 passed in 23.99s
✓ 被抓到 解散不再限于临时队伍 | 1 failed, 39 passed in 24.47s
✓ 被抓到 退出不再限于临时队伍 | 1 failed, 39 passed in 24.12s
✓ 被抓到 不在名单里也能退出 | 1 failed, 39 passed in 23.46s
✓ 被抓到 截止后还能退出 | 1 failed, 39 passed in 24.45s
✓ 被抓到 最后一人退出不再解散 | 1 failed, 39 passed in 24.68s
✓ 被抓到 临时队伍也能撤回 | 1 failed, 39 passed in 23.80s
✓ 被抓到 审核页对临时队伍也显示按钮 | 1 failed, 39 passed in 23.04s
✓ 被抓到 取消赛事不再通知临时队伍成员 | 1 failed, 39 passed in 24.32s
✓ 被抓到 注销时不再退出临时队伍 | 1 failed, 39 passed in 20.99s
---
18/18 mutations caught
```

## 设计偏差

无。「移回散人池」的日志记 `sync_roster` 而不是新动作，8.8.2 补了一句。

## 未完成 / 顺带发现

- 拖拽本身没有在真实浏览器里点过（和 032 一样，测试只钉住脚本依赖的 DOM 属性和表单契约）。074 部署到测试机后要真拖一次
- 编排页对「散人池里的人后来被战队报了名」只标出、不能编入；他被战队名单移除后卡片自动恢复可编入，没有专门测试
- `individual_pool()` 从本轮起只列还没编入的人；069 的两条测试没受影响，但 069 报告里「名单」的说法要按这个理解

## 需要确认

无。

## 改动文件

`docs/design.md`、`README.md`、`AGENTS.md`、`handoff/STATUS.md`、`handoff/rounds/070-adhoc-teams/`；`tournaments/models.py`、`tournaments/migrations/0007_adhoc_teams.py`（新）、`tournaments/registration.py`、`tournaments/services.py`、`tournaments/review_admin.py`、`tournaments/registration_views.py`、`tournaments/urls.py`、`tournaments/wagtail_hooks.py`、`tournaments/teams_admin.py`（新）、`tournaments/notifications_registration.py`、`tournaments/templates/tournaments/admin/teams.html`、`_zone.html`、`_card.html`（新）、`tournaments/templates/tournaments/admin/review_detail.html`、`tournaments/templates/tournaments/registration_detail.html`、`tournaments/templates/tournaments/detail.html`、`tournaments/tests/test_adhoc_teams.py`（新）；`static/js/tournament-teams.js`、`static/css/tournament-teams.css`（新）；`core/mail.py`、`core/tests/test_chapter15_audit.py`、`core/tests/test_documented_urls.py`；`moderation/notifications.py`；`accounts/services.py`
