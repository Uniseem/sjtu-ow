# 014 实现报告

> 用户外出期间由 Claude 实现 + 自查。M4 第一部分（共三部分）。

## 结论

T1–T7 已完成：赛事的数据表、后台管理（含发布 / 结束 / 取消）、前台列表与详情、报名入口占位、预渲染与 sitemap、AI 审核接入、赛事管理员权限。288 个测试通过（本轮新增 18 个）。报名相关的四处留了明确的接口，015 接上。

## 逐条结果

### T1 数据表

`Tournament` 按设计 12.8.1，三条约束都落到数据库：

- `1 <= roster_min <= roster_max <= 20`
- `registration_opens_at < registration_closes_at`
- `external_id` 不为空时唯一

`source_client`（指向 M5 的 `ApiClient`）本轮先不建 FK，注释写明 M5 再接；`external_id` 字段已经有了，上游推送时能直接用。另外加了 `published_at`，用来判断「发布过的赛事不能删除」。

### T2 后台管理

「社区 → 赛事」，权限是 Django 的 `tournaments.*` 模型权限（`init_site` 分给「赛事管理员」组）：

- 编辑面板分三组：内容、时间、报名规则。
- 保存后如果参赛人数下限 > 全站战队人数上限，弹出警告（不阻止保存）。
- 行内「更多」：草稿可「发布」、已发布可「标记为已结束」、未取消的可「取消赛事」（取消页要填说明）。
- `services.can_delete()` 判定「从未发布过的草稿才能删」。
- **留给 015 的接口**：`has_registrations()`（有报名后锁定审核模式）、`active_registration_captains()`（取消时通知队长）、`approved_teams()`（详情页的已通过战队）。

### T3 前台页面

- `/tournaments/`：四组（报名中 / 即将开始报名 / 已截止 / 已结束），组内排序各自合理（报名中按截止时间、即将开始按开始时间、已截止和已结束按时间倒序）。
- `/tournaments/<id>/`：封面、标题、阶段徽章、人数要求、是否仅限交大、报名和比赛时间、详细说明、已报名战队区块。草稿 404，已取消可访问并提示。
- 报名入口是占位区域 `tournament-actions:<id>`：未登录「登录后报名」；登录但不是队长「需要由队长为战队报名」；是队长且在报名时间内列出自己的战队 +「报名功能即将开放」；不在报名时间内「当前不在报名时间内」；已取消「赛事已取消，不再接受报名」。

### T4 半静态与 sitemap

已发布和已结束的赛事进预渲染和 sitemap；草稿和已取消的不生成、并从静态目录删除。`schedule_phase_refresh()` 在报名开始和截止两个时间点各排一个延时任务，重新生成详情页和列表页（设计 13.13.4 的「报名开始、报名截止……时间点到达时」）。

### T5 AI 审核

赛事的详细说明在创建和修改时送审（`tournament_description`）。

### T6 初始化

`init_site` 给「赛事管理员」组分配 `tournaments` 的增删改查权限，输出「已分配赛事权限：赛事管理员 可创建和编辑赛事」；「后续里程碑」清单里去掉了这一项。

### T7 导航

顶部导航的「赛事」现在指向真实页面。

## 验收输出

### 1. 检查与测试

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
203 files already formatted

$ uv run python -m pytest -q
288 passed in 17.51s

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

新增 18 个测试：三条数据库约束、四个阶段的判定、列表分组与隐藏草稿 / 已取消、草稿 404 与已取消可访问、报名入口的四种身份、sitemap、发布 / 结束 / 取消的状态规则、发布过不能删除、人数下限警告、预渲染与送审、取消后不再列出、后台权限、后台发布、后台取消。

### 2. 浏览器真实走一遍

后台创建（赛事管理员账号）→ 发布：

```
创建: 200 | 2026 春季校园赛 | 状态: draft | 创建人: 赛事验收
发布后状态: published | published_at: True
```

前台列表（匿名）：

```
赛事
报名中
2026 春季校园赛
面向全体交大学生与校友的 6v6 比赛。
5–6 人
报名 9月15日 19:56 至 9月23日 19:56
```

前台详情（匿名）：

```
2026 春季校园赛
报名中  5–6 人
报名时间 2026年9月15日 19:56 至 2026年9月23日 19:56
比赛时间 2026年9月30日 19:56
登录后报名
赛制：小组赛 + 淘汰赛。详情见群公告。
已报名战队：暂时还没有通过审核的战队。
```

控制台 0 条消息。

取消：

```
状态: cancelled
列表里还有吗: False
详情仍可访问: 200 | 显示已取消: True
sitemap 里还有吗: False
静态文件还在吗: False
```

### 3. 静态详情页

```
静态详情页字节: 5130
  含CSRF token: False
  含未登录报名入口: True
  含报名占位: True
  含标题: True
列表静态页: True
```

### 4. 回归

```
/            200    /news/         200    /teams/   200
/lfg/        200    /tournaments/  200    /healthz  200
```

### 5. docker / caddy

```
Successfully built 0845e4d140c1
Valid configuration
```

### 6. 清理

验收赛事和账号 `tm014@example.com` 已删除；预渲染目录重新生成（11 个页面）。

## 设计偏差

**没有改设计文档。** 实现按 8.1、8.2、12.8.1 做。几个实现选择：

1. **新增 `published_at` 字段**：设计 8.1 说「发布过的赛事不能删除」，但 12.8.1 的表里没有能判断「是否发布过」的字段（状态可以从已发布改回……实际不能，但取消之后就看不出来了）。加一个首次发布时间最省事。
2. **`source_client` 本轮不建 FK**：`ApiClient` 表要等 M5。`external_id` 和它的部分唯一约束已经建好，M5 只需加一个 FK 字段和迁移。
3. **详细说明用纯文本字段**：设计 8.1 写的是「富文本」。本轮先用 `TextField` + `whitespace-pre-line` 渲染，M5 之前会换成 Wagtail 的 `RichTextField`——**这一条要在 015 或 016 补上**，因为换字段会带迁移。
4. 报名入口在「是队长且报名中」时显示的是「报名功能即将开放」徽章，015 换成真正的按钮。

## 未完成 / 不同意

1. **报名**（提交、名单快照、状态机、审核）是 015；后台报名审核和邮件是 016。
2. **上游推送赛事**（`PUT /api/v1/tournaments/external/{external_id}`）是 M5。
3. **详细说明还不是富文本**（见设计偏差 3）。
4. 赛事详情页的「关联文章」（设计 8.2）还没做——`ArticlePage` 的关联赛事外键要等这一轮之后补，计划放在 015。

## 顺带发现

1. 007 有一条测试断言 `/admin/tournaments/` 返回 404（当时这个后台还不存在）。本轮它变成了「投稿者被挡回后台首页」，测试已更新为断言重定向链。
2. `ModelViewSet` 的自定义视图类不能写成 `ModelViewSet().add_view_class`（实例化时没有 model 会报错），要直接继承 `wagtail.admin.views.generic.CreateView` / `EditView`。
3. 没有后台访问权限的普通用户打开后台 URL 时，`follow=True` 会进入登录跳转循环，测试里断言 302 就够了。

## 需要确认

无。

## 改动文件

新增：`tournaments/models.py`、`services.py`、`views.py`、`urls.py`、`slots.py`、`notifications.py`、`prerender_targets.py`、`wagtail_hooks.py`、`migrations/0001_initial.py`、`templates/tournaments/**`、`tests/test_tournaments.py`。

修改：`tournaments/apps.py`、`core/management/commands/init_site.py`、`content/views.py`（sitemap）、`content/tests/test_submissions.py`、`sjtu_ow/urls.py`、`README.md`、`handoff/STATUS.md`。
