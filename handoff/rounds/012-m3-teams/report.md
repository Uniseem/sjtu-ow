# 012 实现报告

> 用户外出期间由 Claude 实现 + 自查。M3 第一部分。

## 结论

T1–T8 已完成：战队的创建、编辑、申请、审批、成员管理、转让、退出、解散全流程可用，接进了功能权限、限流、AI 审核、半静态渲染和 sitemap。243 个测试通过（本轮新增 38 个）。

## 逐条结果

### T1 数据表

`Team` / `TeamMembership` / `TeamApplication`，约束都按设计 12.6 落到数据库：

- 未解散战队的队名 `Lower(name)` 部分唯一
- (team, user) 唯一、`role = captain` 时 team 唯一（每队一个队长）
- `status = pending` 时 (team, applicant) 唯一

### T2 创建与编辑

队名 2–16 字、简介 500 字、队标（JPG/PNG/WebP、5MB、显示时 `fill-64x64` / `fill-96x96` 正方形裁剪）、招募中默认开。`team_create` 功能权限、队长数量上限（读「设置 → 全站设置」）、同名检查都在 `teams/services.py` 里；创建限流每人每天 3 次。创建者自动成为队长，创建后直接进管理页。

### T3 战队主页与列表

- `/teams/`：只列未解散的，`?recruiting=1` 只看招募中，卡片是队标 / 队名 / 人数 / 招募状态。
- `/teams/<id>/`：队标、队名、简介、人数、招募状态、队长、成员列表（昵称 + 队长标识 + 入队时间）。**成员的游戏 ID 和段位只在管理页显示**，主页没有（测试断言）。
- 已解散：主页顶部「该战队已解散」，不进列表、不进 sitemap、静态文件被删。

### T4 入队申请

意向位置至少选一个、留言 200 字、条件逐条校验（登录、`team_apply`、至少 1 个游戏 ID、不是成员、招募中、未满员、没有待审批申请），限流每人每天 20 次。申请页写明「提交申请后，队长可以看到你的游戏 ID 和段位」。

审批在一个写事务里 `select_for_update` 后**再查一遍**满员和是否已是成员——满员时拒绝并提示，已是成员时把申请置为已取消。通过 / 拒绝都发邮件给申请人，被拒后可以再申请，申请人可以在 `/me/teams/` 撤回。

### T5 成员管理与解散

退出（队长不能直接退出，提示先转让或解散）、移除成员（不能移除自己，发邮件）、转让队长（只能转给现有成员，检查对方的队长数上限，发邮件）、超级管理员指定队长（对方不是成员时先加入再转让）。

解散：队长或超级管理员；`disband_blockers()` 现在返回空列表，**M4 在这里接上「有效报名」检查**（注释写明了规则）。解散后软删除、清空成员、待审批申请转已取消、给全体成员发邮件、删除静态页面。

### T6 个人中心

`/me/teams/` 列出我所在的战队（含队长标识、管理 / 退出入口）和我的入队申请（状态、拒绝原因、撤回按钮）。005 留下的「即将开放」已经换掉，导航项变成可点。

### T7 接入已有机制

- **AI 审核**：队名和简介在创建 / 修改时送审，入队留言在提交时送审（`target_type` 用设计里已有的 `team_name` / `team_description` / `application_message`）。送审失败只记日志，不影响业务动作。
- **半静态渲染**：`/teams/` 和 `/teams/<id>/` 进预渲染；创建、修改、成员变动、招募状态变化都会重新生成，解散会立即删除静态文件。「申请加入」区域是占位 `team-join:<id>`，静态页里是「登录后申请」，登录用户由片段接口换成「申请加入 / 你已是成员 / 管理战队 / 不能申请的原因」。
- **sitemap**：未解散的战队进 sitemap，解散后移除。

顺带把两处做成了注册表，避免 `core` 反向依赖各个业务 app：预渲染页面清单（`core.prerender.register_targets`）和占位区域（`core.slots.register`），`content` 和 `teams` 在各自的 `AppConfig.ready()` 里注册。

### T8 后台

「社区 → 战队」（超级管理员可见）：列表、编辑、**指定队长**、**解散**（后两个是列表行「更多」里的独立页面，都带确认）。

## 验收输出

### 1. 检查与测试

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
185 files already formatted

$ uv run python -m pytest -q
243 passed in 15.02s

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

本轮新增 38 个测试：创建者成为队长、队名大小写唯一、解散后队名可复用、队长数量上限、`team_create` 被禁用、申请条件逐条、满员不能申请、重复申请、必须选位置、申请邮件、审批加人 + 邮件、审批时再查满员、非队长不能审批、拒绝后可再申请、撤回、队长不能退出、成员可退出、不能移除自己、移除邮件、转让互换角色 + 邮件、只能转给成员、超管指定队长、解散清空成员和申请 + 邮件、非队长不能解散、列表隐藏已解散、主页不显示游戏 ID、已解散提示、未登录看到「登录后申请」、成员的占位内容、管理页仅队长、管理页显示游戏 ID、`/me/teams/`、创建限流、改动触发审核和预渲染、sitemap、后台仅超管、后台指定队长、后台解散。

### 2. 浏览器真实走一遍

创建（队长验收 `cap012`）：填队名「交大验收队」+ 简介 → 跳转到管理页，成员 1/10，队长带 `Cap012#1234`。

匿名访客看战队主页：

```
交大验收队
1 / 10 人 · 招募中 · 队长 队长验收
验收用的战队，欢迎加入。
登录后申请
成员：队长验收（队长）2026年9月16日 加入
```

**没有任何游戏 ID**。

申请（申请验收 `app012`）：勾选「输出」+ 留言「打输出位，钻石段，每天晚上在线。」→ 提交后主页显示「你对这支战队还有一条待审批的申请」，`/me/teams/` 里出现这条申请和「撤回」。

队长侧（同一套视图，用测试客户端把剩下的动作跑完）：

```
申请状态: pending | 意向位置: ['输出'] | 留言: 打输出位，钻石段，每天晚上在线。
管理页可见申请人游戏 ID: True | 可见留言: True
审批后: approved | 成员数: 2
转让后队长: 申请验收 | 原队长还在队里: True
原队长退出后成员数: 1
解散: True | 成员数: 0 | 待审批申请数: 0
解散后主页提示: True
列表里还有吗: False
```

### 3. 手机宽度

375px 打开战队主页：

```js
{width: 375, inline: 0, overflow: false, join: "你已是成员 退出战队"}
```

没有横向滚动、没有内联样式，占位区域正确。战队列表卡片在手机上单列、桌面两列。

### 4. 预渲染文件

```
prerendered/teams/2/index.html
  含 CSRF: False | 含游戏 ID: False | 含 team-join 占位: True | 含「登录后申请」: True
prerendered/teams/index.html
  含 CSRF: False | 含游戏 ID: False
```

解散后 `prerendered/teams/2/` 被删除（全量生成时 `删除 1`）。

### 5. 回归

```
/            200     /news/       200
/teams/      200     /about/      200
/me/teams/   302（未登录）        /healthz 200
```

前台两个页面在干净标签页里 **0 条控制台消息**、`[style]` 为 0。

### 6. docker / caddy

```
Successfully built c9b552e37808
Valid configuration
```

### 7. 清理

验收用的两支战队、两个账号、相关申请和成员记录都已删除；预渲染目录重新生成为 9 个页面。

## 设计偏差

**没有改设计文档。** 本轮实现完全按设计第 7 章、12.6 和 13.4 做。几个实现选择记在这里：

1. **队标存成 Wagtail 图片**，放在默认（根）集合里，用 `fill-64x64` / `fill-96x96` 做正方形裁剪。设计只说了格式和大小，没说存在哪里。
2. **`disband_blockers()` 现在返回空列表**：设计 7.5 的「有效报名」检查要等 M4 的 `Registration` 表，函数里写清了规则，M4 只要填这一处。
3. **两处注册表**（预渲染清单、占位区域）是为了让 `core` 不反向依赖业务 app，属于实现结构，不影响设计描述。
4. 战队主页的「参赛记录」目前是「即将开放」占位（M4 接入）。

## 未完成 / 不同意

1. **组队大厅**（车帖）是 013 那一轮。
2. **战队解散时的「有效报名」检查**见上，M4 接。
3. **战队主页的参赛记录**同上。
4. 设计 7.2 提到「招募中且未满员时显示申请加入」——满员时占位区域显示的是「战队人数已满」这类原因文字，比不显示按钮更清楚。

## 顺带发现

1. `transaction.on_commit` 里发的邮件在 pytest 的事务测试里默认不会执行，要用 `django_capture_on_commit_callbacks(execute=True)`，否则会误以为没发信。
2. Wagtail 列表行「更多」里的按钮用的是 `wagtail.admin.ui.menus.MenuItem`（不是主菜单的 `wagtail.admin.menu.MenuItem`），两者构造参数不一样。
3. daisyUI 的 `card-body` 自带 `flex-direction: column`，想要横向排版要在里面再套一层 flex，直接在 `card-body` 上加 `flex-row` 会被覆盖。

## 需要确认

无。设计里这一章写得很完整。

## 改动文件

新增：`teams/models.py`、`services.py`、`forms.py`、`views.py`、`urls.py`、`notifications.py`、`images.py`、`slots.py`、`prerender_targets.py`、`wagtail_hooks.py`、`migrations/0001_initial.py`、`templates/teams/**`、`tests/test_teams.py`；`core/slots.py`、`content/prerender_targets.py`、`templates/me/teams.html`。

修改：`teams/apps.py`、`content/apps.py`、`core/apps.py`、`core/views.py`、`core/prerender.py`、`content/views.py`（sitemap）、`accounts/views.py`（`me_context` 与导航）、`sjtu_ow/urls.py`、`README.md`、`handoff/STATUS.md`。
