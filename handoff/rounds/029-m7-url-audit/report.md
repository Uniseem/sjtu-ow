# 029 实现报告

## 结论

**完成，没有发现缺失。** 设计里写到的 27 个地址全部存在，且由预期的 view 处理；5 个公开页面真的渲染出内容。

**第一版测试是假的**，写完变异测试才发现——见下。

## 逐个核查

```
  ✓ /healthz                     → healthz
  ✓ /lfg/                        → lfg_index
  ✓ /lfg/new/                    → lfg_create
  ✓ /lfg/1/edit/                 → lfg_edit
  ✓ /me/                         → me_profile
  ✓ /me/contacts/                → me_contacts
  ✓ /me/game-accounts/           → me_game_accounts
  ✓ /me/registrations/           → me_registrations
  ✓ /me/security/                → me_security
  ✓ /me/teams/                   → me_teams
  ✓ /me/scrims/                  → me_scrims
  ✓ /registrations/1/            → registration_detail
  ✓ /scrims/                     → scrim_index
  ✓ /scrims/1/                   → scrim_detail
  ✓ /submit/                     → submit
  ✓ /teams/                      → team_index
  ✓ /teams/1/                    → team_detail
  ✓ /teams/1/apply/              → team_apply
  ✓ /teams/1/manage/             → team_manage
  ✓ /teams/new/                  → team_create
  ✓ /tournaments/                → tournament_index
  ✓ /tournaments/1/              → tournament_detail
  ✓ /tournaments/1/register/     → tournament_register
  ✓ /_fragments/state/           → state_fragment
  ✓ /api/v1/ping                 → api:ping
  ✓ /api/v1/docs/                → api:docs
  ✓ /api/v1/schema/              → api:schema
```

匿名访问公开页面：

```
  200 /              200 /news/      200 /about/
  200 /terms/        200 /privacy/   200 /lfg/
  200 /scrims/       200 /teams/     200 /tournaments/   200 /submit/
  302 /me/           → /accounts/login/?next=/me/
  403 /api/v1/docs/
  503 /healthz       ← 见下
```

### `/healthz` 返回 503 是对的

```
ok: False | status: error
  database          {'ok': True, 'detail': 'ok'}
  disk              {'ok': True, 'detail': 'free space 30.5%'}
  worker_heartbeat  {'ok': False, 'detail': '心跳缺失'}
  task_backlog      {'ok': True, 'detail': 'ok'}
```

只有 worker 心跳这一项失败——因为 025 轮之后我把所有 worker 都停了。数据库、磁盘、任务积压都正常。**健康检查正确地报出了「worker 死了」**，这正是它该做的事。

## 第一版测试是假的

第一版只断言 `resolve(path)` 不抛 `Resolver404`。做变异测试时删掉 `/scrims/<id>/` 的路由，**测试照样全绿**。

原因：

```
删掉路由之后 /scrims/1/ 解析到: wagtail_serve
```

`wagtail_urls` 挂在 URLconf 最后，是个兜底，**任何路径都能解析成功**。所以「能解析」这个断言恒真，等于什么都没测。

改成断言解析到的 view 名字。再做同样的变异：

```
AssertionError: 设计里写到的 /scrims/1/ 现在由 wagtail_serve 处理，应该是 scrim_detail。
（落到 wagtail_serve 说明路由被删了或改名了，Wagtail 的兜底路由会接住一切，不会报 404。）
```

**这是第五次同类错误**（019 文档页、021 单种子、023 首页体积、026 邮件主题、029 这次）。前四次的共同点是「断言了容易断言的东西」；这次多了一层：**断言看起来很对，但环境里有个兜底让它恒真**。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!

$ uv run python -m pytest -q
581 passed

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

新增 35 个测试（27 个地址各一条 + 5 个公开页面 + 3 条）。

## 改动文件

```
core/tests/test_documented_urls.py   新增
```
