# 069 实现报告

## 结论

**完成。** 设计 v1.7 新增 8.8 节（8.8.1 个人报名本轮实现，8.8.2 编队写明 070 实现）；`IndividualSignup` 表、报名与取消服务、前台入口和名单、个人中心、账号侧连带处理全部落地。37 条新测试，13/13 处守卫变异被抓到；全量测试通过（一条和本轮无关的计时测试在全量跑时偶发失败，单独重跑通过，见下）。

## 逐条结果

| 任务 | 结果 |
|---|---|
| 设计 v1.7 | 新增 8.8 节；1.2、1.5（个人报名、临时队伍两个术语）、3.8（导出和注销）、4.4、8.1（字段）、8.2（名单和入口）、12.1（ER 图）、12.8.1、12.8.5（新表）、12.11、13.4（两条路由）、13.13.4（两行事件）、附录 D |
| 模型与迁移 | `Tournament.allow_individual_signup`；`IndividualSignup(tournament, user, game_account PROTECT, role_*, registration 可空 SET_NULL, created_at, updated_at)`，唯一 (tournament, user)，检查约束至少一个位置；迁移 `tournaments/0006_individual_signup` |
| 服务 | `individual_problems()`（开关、时间窗、`member_problems()`、`existing_roster_conflict()`）、`individual_pool()`、`pool_counts()`、`sign_up_individual()`（创建或更新；别人的游戏 ID、零位置、已编入都拒绝；并发重复用唯一约束兜底）、`cancel_individual()`（没报、已编入、截止后拒绝）、`_refresh_tournament_page()`（只刷公开赛事）、`my_individual_signups()` |
| 前台 | `/tournaments/<id>/signup/`（GET 表单带预检查，POST 提交）、`/tournaments/<id>/signup/cancel/`；槽位 `tournament-actions` 重排分支：取消 → 未登录 → 队长（原流程）→ 已个人报名（等待编队 / 已编入，截止前有「修改」和「取消个人报名」）→ 开放个人报名（不在时间内 / 问题清单 / 「个人报名」按钮）→ 「需要由队长为战队报名」；赛事页「个人报名」区块（人数、各位置人数、昵称和位置）；`/me/registrations/` 新「个人报名」区 |
| 账号侧 | `deletion_blocked_reason()` 拦未结束赛事的个人报名；`delete_account()` 在删游戏 ID 前删个人报名；`personal_data()` 加 `individual_signups`；`refresh_nickname_pages()` 刷有个人报名的公开赛事页 |
| 后台 | 赛事面板「报名规则」加开关，列表筛选加开关 |
| 测试 | `tournaments/tests/test_individual_signup.py` 37 条：报名与更新、人数统计、九种拒绝、取消三种、公开页只有昵称和位置、开关关闭时不显示、静态页无 CSRF 无「退出」、槽位五种情况（散人入口、已报名、问题清单、开关关、队长不变）、页面往返、页面显示问题、登录与草稿 404、我的报名、预渲染触发（报名、取消、未公开不触发、改昵称）、账号侧四条、后台表单有开关、不发邮件；`test_documented_urls.py` 加两条路由 |

## 验收输出

```
$ uv run ruff format . && uv run ruff check .
219 files left unchanged
All checks passed!

$ PYTHONUTF8=1 uv run pytest -q
FAILED scrims/tests/test_teaming.py::test_6v6_finishes_within_a_second - Asse...
1 failed, 769 passed in 149.02s (0:02:29)

$ PYTHONUTF8=1 uv run pytest -q scrims/tests/test_teaming.py -k finishes_within
1 passed, 39 deselected in 1.72s

$ PYTHONUTF8=1 uv run pytest -q tournaments/tests/test_individual_signup.py
37 passed in 9.48s

$ uv run python manage.py makemigrations tournaments --name individual_signup
  tournaments\migrations\0006_individual_signup.py
    + Add field allow_individual_signup to tournament
    + Create model IndividualSignup
```

那条计时测试是 AGENTS.md 里记过的「机器繁忙时偶发失败」项（6v6 分队 1 秒内），和本轮改动无关，单独重跑通过。`makemigrations --check` 和 `check --deploy` 在提交前的最后一次检查里跑（见 review）。

**变异（脚本 `mutate_069.py`，本轮目录）**

```
✓ 被抓到 开关不再检查 | 1 failed, 36 passed in 10.20s
✓ 被抓到 时间窗不再检查 | 2 failed, 35 passed in 10.36s
✓ 被抓到 队员校验（权限、资料、仅限交大）不再复用 | 4 failed, 33 passed in 9.33s
✓ 被抓到 名单冲突不再检查 | 1 failed, 36 passed in 9.73s
✓ 被抓到 别人的游戏 ID 也收 | 1 failed, 36 passed in 9.48s
✓ 被抓到 零个位置也收 | 2 failed, 35 passed in 9.63s
✓ 被抓到 已编入的还能改 | 1 failed, 36 passed in 10.03s
✓ 被抓到 截止后还能取消 | 1 failed, 36 passed in 9.70s
✓ 被抓到 报名不再刷新页面 | 1 failed, 36 passed in 9.61s
✓ 被抓到 未公开的赛事也刷新 | 1 failed, 36 passed in 9.80s
✓ 被抓到 删除游戏 ID 不再看个人报名 | 1 failed, 36 passed in 9.86s
✓ 被抓到 改昵称不再刷新散人名单 | 1 failed, 36 passed in 9.62s
✓ 被抓到 槽位对散人不再给入口 | 2 failed, 35 passed in 9.81s
---
13/13 mutations caught
```

## 设计偏差

无。

## 未完成 / 顺带发现

- 「已编入」的分支（槽位、个人中心、报名页的提示）现在只能靠测试里直接写 `registration` 外键来触发，070 做编队后再走一遍真实流程
- `sign_up_individual()` 对散人的段位不做要求，编队页要把「未填段位」标出来（070）
- `delete_account()` 直接删掉个人报名；已编入临时队伍的人注销时应按 8.8.2 退出队伍并释放名额，070 接手

## 需要确认

无。

## 改动文件

`docs/design.md`、`README.md`、`handoff/STATUS.md`、`handoff/rounds/069-individual-signup/`；`tournaments/models.py`、`tournaments/migrations/0006_individual_signup.py`（新）、`tournaments/registration.py`、`tournaments/registration_views.py`、`tournaments/urls.py`、`tournaments/views.py`、`tournaments/slots.py`、`tournaments/wagtail_hooks.py`、`tournaments/templates/tournaments/slots/actions.html`、`tournaments/templates/tournaments/detail.html`、`tournaments/templates/tournaments/individual_signup.html`（新）、`tournaments/tests/test_individual_signup.py`（新）；`templates/me/registrations.html`；`accounts/services.py`；`core/tests/test_documented_urls.py`
