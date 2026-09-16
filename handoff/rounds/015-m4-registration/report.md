# 015 实现报告

> 用户外出期间由 Claude 实现 + 自查。M4 第二部分。

## 结论

T0–T7 已完成：赛事说明改成富文本、文章可以关联赛事；报名的三张表、8 项校验、名单快照、同步、状态机、前台三个页面、两类邮件都做完了，014 留的四处接口也接上了。314 个测试通过（本轮新增 26 个）。

## 逐条结果

### T0 补 014 的落差

1. 赛事「详细说明」换成 Wagtail `RichTextField`（features 限定为 h2/h3/加粗/斜体/列表/链接/分隔线），详情页用 `richtext` 渲染。
2. `ArticlePage` 加「关联赛事」外键，编辑面板里可选；赛事详情页显示关联文章列表。

### T1 数据表

`Registration`、`RegistrationMember`、`RegistrationStatusLog` 按设计 12.8.2–12.8.4，关键约束：

- (tournament, team) 唯一
- **`is_active = true` 时 (tournament, user) 唯一**——「同一赛事每人只能代表一支战队」的数据库兜底，测试里直接插重复行验证过
- 日志表只增不改，带名单版本和完整快照

### T2 提交报名

报名页列出战队全部成员、每人一个游戏 ID 下拉（只有一个时就是唯一选项），并在每人旁边显示预检查问题。

`registration.submit()` 在一个写事务里：`select_for_update` 取已有报名 → 跑 8 项校验 → **一次性收集全部问题**（`RegistrationError.problems`）→ 全通过才写报名、名单快照、日志。事务提交后发「报名已提交」邮件，并留了 Webhook 调用点（M5）。

八项对应关系：1 时间窗口、2 队长与未解散、3 人数区间、4 资料完整、5 账号启用且有 `tournament_register` 权限、6 仅限交大、7 游戏 ID 归属、8 同赛事重复报名。

### T3 名单锁定与同步

名单写进快照（昵称、游戏 ID、是否交大、三个位置段位、是否队长），之后改昵称或段位都不影响（测试断言）。同一入口既是首次提交，也是重新提交和同步名单：已有报名且在有效状态时记 `sync_roster`，否则记 `resubmit`，两种都让版本加 1、状态回到待审核、日志存完整名单。报名详情页在成员集合和名单不一致时提示「可能需要同步」。

### T4 状态机

`approve` / `reject`（含撤销通过）/ `withdraw` / 重新提交覆盖设计 8.5 的全部转换：

- 本站审核：管理员通过 → 已通过；两级审核：管理员通过 → 待上游确认，再由上游确认 → 已通过
- 上游审核模式下本站管理员被拒绝（「这项赛事由上游审核，本站不能改状态」）
- 驳回和撤销通过必须填备注
- 队长的撤回和同步受报名截止时间限制，管理员不受限
- 转到已驳回 / 已撤回时，名单的 `is_active` 一起置为假——**名额立刻释放**，同一个人可以随别的战队报名（测试覆盖）

### T5 前台页面

`/tournaments/<id>/register/`（队长，可切换自己带的多支战队）、`/registrations/<id>/`（队长和名单成员可见，其他人 404）、`/me/registrations/`（名单成员也能看到自己参加的报名）。赛事详情页的报名入口换成真实按钮，已报名时显示状态和「查看报名」。

### T6 邮件

「报名已提交 / 重新提交 / 名单已同步」和「报名状态有更新」（带备注）都发给队长，逐封发送，走已有的队列邮件后端。

### T7 接上 014 的接口

`has_registrations`、`active_registration_captains`（取消赛事时发信）、`approved_teams`（赛事详情页的已通过战队和人数）都接上了。

## 验收输出

### 1. 检查与测试

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
210 files already formatted

$ uv run python -m pytest -q
314 passed in 19.39s

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

新增 26 个测试：8 项校验逐条、多问题一次列出、数据库兜底、名单冻结、同步加版本、本站 / 两级 / 上游三种审核模式、驳回必须填备注、撤回与重新提交、撤回后名额释放、截止后队长不能操作、两类邮件、三个页面的可见性、已通过战队出现在赛事页、取消赛事发信、实时页与片段显示一致。

### 2. 浏览器真实走一遍

登录队长 → 赛事详情显示「为战队报名」→ 报名页列出两名队员和各自的游戏 ID → 提交：

```
报名详情
报名验收赛 · 报名验收队
待审核   名单版本 1
同步名单 | 撤回报名
名单快照：报名队长（队长）RegCap#1111 交大 / 报名队员 RegMate#2222 交大
状态历史：2026年9月16日 20:11 提交报名 → 待审核
```

接着走完整个生命周期：

```
通过后: approved | 名单占名额: 2
赛事页出现战队: True | 人数: True
同步前提示需要同步: True
同步后: pending | 版本: 2 | 名单人数: 3
状态历史: [('提交报名', '待审核'), ('通过', '已通过'), ('同步名单', '待审核')]
撤回后: withdrawn | 占名额人数: 0
```

### 3. 多个校验同时失败

```
一次性列出的问题：
  - 该赛事要求 5 到 6 人，你的战队现在有 3 人
  - 报名队员 的资料不完整（缺少联系方式）
  - 该赛事仅限交大用户参加，报名队员 不符合
```

### 4. 回归

```
/                200    /news/         200    /teams/   200
/lfg/            200    /tournaments/  200    /healthz  200
/me/registrations/ 302（未登录）
```

### 5. docker / caddy

```
Successfully built 152dbc4c5f59
Valid configuration
```

### 6. 清理

验收用的赛事、报名、名单、日志、战队和三个账号都已删除。

## 设计偏差

**没有改设计文档。** 实现按 8.3–8.6、12.8.2–12.8.4 做。几处说明：

1. **提交、重新提交、同步名单走同一个入口**：三者的校验和写入完全一样，只有日志里的 `action` 和版本处理不同。设计 8.4 也是这么描述的。
2. **「已驳回 / 已撤回不占名额」通过把名单行的 `is_active` 置为假实现**，正好让数据库的部分唯一约束自动放行——不用删快照，历史仍然完整。
3. **上游那半留了参数**：`approve` / `reject` 都接受 `actor_type`，M5 的 API 只要传 `ActorType.UPSTREAM`。日志表的 `actor_client` 字段等 `ApiClient` 建表后再加。
4. 报名页的名单顺序是队长在前、其余按入队时间。

## 未完成 / 不同意

1. **后台报名审核界面**（列表、详情、批量通过、CSV 导出）是 016。
2. **Webhook 投递**是 M5，服务层留了两个调用点（提交后、状态变化后）。
3. **`RegistrationStatusLog.actor_client`** 等 M5 的 `ApiClient` 表。
4. 报名详情页的状态历史按设计「不显示具体是哪位管理员」，所以只显示动作和结果。

## 顺带发现

1. **赛事详情页曾经有一处真实缺陷**：模板里直接 `include` 报名入口占位，但视图没给占位需要的上下文，导致登录队长在实时渲染的页面上看到的是「需要由队长为战队报名」。现在视图和片段共用同一个 `actions_context()`，并加了断言两边一致的测试。这类「占位区域在实时页和片段里不一致」的问题以后每接一个占位都要查一遍。
2. `accounts.services.profile_gaps()` 返回的是三元组列表，不是字符串列表。
3. 测试里要触发数据库约束（而不是应用层校验）时，必须用 `@pytest.mark.django_db(transaction=True)`，否则 `IntegrityError` 会让外层事务进入不可用状态。

## 需要确认

无。

## 改动文件

新增：`tournaments/registration.py`、`registration_views.py`、`notifications_registration.py`、`templates/tournaments/{register,registration_detail}.html`、`templates/me/registrations.html`、`tests/test_registration.py`、`migrations/0002_alter_tournament_description.py`、`migrations/0003_registration_registrationmember_and_more.py`、`content/migrations/0002_articlepage_tournament.py`。

修改：`tournaments/models.py`、`services.py`、`views.py`、`urls.py`、`slots.py`、`notifications.py`、`templates/tournaments/{detail.html,slots/actions.html}`、`content/models.py`、`accounts/views.py`（导航）、`README.md`、`handoff/STATUS.md`、`tournaments/tests/test_tournaments.py`。
