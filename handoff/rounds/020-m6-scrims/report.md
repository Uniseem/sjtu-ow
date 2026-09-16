# 020 实现报告

> 本轮由实现方（Claude）自己做，用户外出。下面所有输出都是真实跑出来的；没跑的会写「未验证」。

## 结论

**完成。** 内战的活动管理和报名做完了，分队算法留给 021。实现过程中在真实浏览器里发现「修改报名」按钮点了没反应——我用了 Alpine 的内联表达式，而本站装的是 Alpine **CSP 构建**，根本不会求值。已改成不需要脚本的 `<details>`。

## 逐条结果

### T1 数据表

`Scrim` 和 `ScrimSignup` 按设计 12.9，唯一约束 `(scrim, user)`，另加一条 CHECK 保证至少勾了一个位置。迁移 `scrims/migrations/0001_initial.py`。

### T2 后台活动管理

Wagtail「社区 → 内战」，列表 / 新建 / 编辑，加发布、标记已结束、取消三个动作。发布和编辑都会重新安排提醒任务。

### T3 / T4 前台列表与详情

`/scrims/` 只列已发布的和最近 30 天内已结束的；已取消的不在列表里，详情页保留并显示「已取消」；**草稿是 404**。详情页显示标题、时间、规格、说明、截止时间、报名统计和名单——**名单只有昵称和能打的位置**。

### T5 报名

七个前置条件都在服务层查。角色限定和不限位置两套段位规则。截止前可改可取消；取消或换游戏 ID 时，如果已经被勾选上场或分过队，就清掉分队字段并盖 `roster_changed_at`，后台据此显示「分队有变化」。

顺手把 `accounts/services.py` 里留了两轮的 M6 待办补上了：**报名用到的游戏 ID 在活动结束前不能删除**。

### T6 半静态渲染

列表页和详情页注册进预渲染目标；报名框走 `scrim-actions:<pk>` 插槽，live 页面和 `/_fragments/scrims/<pk>/actions/` 共用同一份 `actions_context()`（015 的教训）。

## 验收输出

### 1. 检查与测试

```
$ ruff check . && ruff format --check .
All checks passed!
191 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ uv run python -m pytest -q
461 passed in 26.03s

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

本轮新增 40 个测试。

**对新测试做了变异测试**（改坏实现，看测试会不会红）：

| 改坏的地方 | 结果 |
|---|---|
| 角色限定的段位校验改成永远通过 | `test_role_queue_requires_a_rank_for_every_ticked_role` 失败 ✓ |
| 取消报名不再盖 `roster_changed_at` | `test_cancelling_after_the_split_marks_the_teams_stale` 失败 ✓ |
| 列表不再排除已取消的活动 | `test_the_list_shows_published_and_recently_finished` 失败 ✓ |

### 2. 真实浏览器走一遍

建活动（草稿）→ 后台发布 → 玩家登录报名 → 修改报名 → 取消报名，全部在真实 dev server 上点完。服务器日志佐证：

```
POST /accounts/login/   302
POST /scrims/1/signup/  302
POST /scrims/1/cancel/  302
```

报名后详情页显示「已报名 · 验证玩家甲#1234 · 坦克 / 输出」，带「取消报名」和「修改报名」；点开「修改报名」，表单带着当前的游戏 ID 和已勾选的位置。

### 3. 草稿与已取消

```
匿名 GET /scrims/1/（草稿）-> 404
列表页里 "020 验证内战" 出现 0 次
```

### 4. 详情页不含段位和游戏 ID

匿名访问 `/scrims/1/` 的整页 HTML 里检索：

```
  #1234        : 0 次
  钻石          : 0 次
  白金          : 0 次
  @example.com : 0 次
  987654321    : 0 次   （QQ）
  内联 style    : 0 个
```

名单部分的真实 HTML：

```html
<h2 class="mt-10">报名情况</h2>
<p class="mt-2 text-sm text-base-content/80">
  共 <span class="font-numeric">1</span> 人 ·
  坦克 <span class="font-numeric">1</span> ·
  输出 <span class="font-numeric">1</span> ·
  支援 <span class="font-numeric">0</span>
</p>
<ul class="mt-4 divide-y divide-base-300 rounded-box bg-base-200">
  <li class="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
    <span>验证玩家甲</span>
    <span class="flex gap-1">
      <span class="badge badge-outline badge-sm">坦克</span>
      <span class="badge badge-outline badge-sm">输出</span>
    </span>
  </li>
</ul>
```

游戏 ID 只出现在**本人自己的报名框**里，不在公开名单里。

### 5. 取消报名会把人从分队里移出

先手动造一个「已上场、已分到 A 队输出」的状态并盖上 `teams_generated_at`，然后在浏览器里点「取消报名」：

```
点之前  teams_are_stale: False
点之后  报名数: 0
        teams_are_stale: True
        roster_changed_at:   2026-09-16 13:44:08
        teams_generated_at:  2026-09-16 13:44:05
```

### 6. 两封邮件

```
--- 提醒邮件 ---
收件人: ['v020-p1@example.com']
主题: [交大守望先锋] 内战提醒：020 验证内战
内战「020 验证内战」就要开始了。

开始时间：2026-09-16 22:29
规格：角色限定 5v5

活动页面：http://localhost:8000/scrims/1/

--- 取消邮件 ---
收件人: ['v020-p1@example.com']
主题: [交大守望先锋] 内战已取消：020 验证内战
内战「020 验证内战」已取消。

原定时间：2026-09-16 22:29
规格：角色限定 5v5

活动页面：http://localhost:8000/scrims/1/
```

提醒任务第一次返回 `sent:1`，第二次返回 `already_sent` 且不再发信。

### 7. 控制台

修完 Alpine 那个问题之后，内战页面控制台无错误，网络请求全部指向本站静态文件。

### 8. 回归 + docker / caddy

```
$ uv run python -m pytest -q
461 passed in 26.03s

$ docker build -t sjtu-ow:020 .
sha256:410c4b157794841c083e398e8f654bb3f145b4ad898d7cfe3bdc2096ab3d3483

$ docker run --rm -v ./deploy:/etc/caddy:ro caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile
Valid configuration
```

### 9. 清理（查了全库）

删除内战 1 个、报名 1 条、账号 3 个、会话 1 条。全库计数只剩骨架：6 个页面、5 个分类、站点设置、5 个游戏模式、9 条排版规则，加 Wagtail 自己的结构。`Scrim`、`ScrimSignup`、`User` 都是 0。

`DBTaskResult` 248 条是任务队列本身（019 已说明），清理任务的 30 天规则会处理。

## 设计偏差

**没有改设计文档。** 三点说明：

1. **多了一个字段 `Scrim.roster_changed_at`**。设计 9.2 要求「管理员在后台能看到『分队有变化』的提示」但没说怎么存。一开始我想复用 `updated_at`，但那样管理员改个标题也会被当成「分队有变化」，所以单开一个字段只在名单真的变动时盖。
2. **换游戏 ID 也算分队失效**。设计只说取消报名要移出，但换 ID 会换掉段位分数，原来的分队是按旧分数算的，所以一并清掉。
3. **前台 URL 不用命名空间**：`scrims/urls.py` 没有 `app_name`，因为 Wagtail 的 ModelViewSet 已经占了 `scrims` 这个命名空间（和 `tournaments` 的做法一致）。第一版加了 `app_name` 会触发 `urls.W005`。

## 未完成 / 不同意

1. **分队算法、后台分队页、拖拽调整、复制结果是 021**（设计 9.3–9.6）。`ScrimSignup` 的 `is_selected` / `team` / `assigned_role` / `rating_used` 四个字段这轮已经建好但还没有业务逻辑。
2. `Scrim.teams_generated_at` 同理，这轮只有取消报名的路径会读它。

## 顺带发现

1. **Alpine 的 CSP 构建不吃内联表达式**，详见 `review.md` A1。本项目此前一处 `x-data` 都没用过，我是第一个，也第一个踩到。
2. **Wagtail 后台的用户头像被 CSP 挡了**：后台页面会去 `www.gravatar.com` 取头像，而 `ADMIN_CSP` 的 `img-src` 只有 `'self' data: blob:`，所以控制台每页都有几条拦截，头像显示为空。**这是前几轮就有的问题，不是本轮引入的**，只影响后台观感。要修的话，要么在 `ADMIN_CSP` 里放行 gravatar（会给后台加一个外部请求，且把管理员邮箱的哈希发给第三方），要么关掉 Wagtail 的 gravatar（`WAGTAIL_GRAVATAR_PROVIDER_URL = None`）。**建议后者，但这是个要拍板的选择，没有自作主张改。**

## 需要确认

1. **要不要关掉 Wagtail 后台的 gravatar 头像？**（见「顺带发现」第 2 条）我倾向于关掉：本站 CSP 本来就不让外部图片，而且把管理员邮箱的 MD5 发给 Gravatar 和隐私政策的口径不太一致。
2. 018 / 019 留下的三个问题仍未定（报名可见范围、错误码总表、`manage.py backup`）。

## 改动文件

```
scrims/models.py                       Scrim、ScrimSignup、规格与位置常量
scrims/migrations/0001_initial.py      新增
scrims/services.py                     可见性、报名校验、报名与取消、提醒安排、后台动作
scrims/notifications.py                新增：提醒邮件、取消邮件
scrims/tasks.py                        新增：提醒任务
scrims/views.py                        列表、详情、报名、取消、我的内战、插槽片段
scrims/slots.py                        新增：报名框插槽
scrims/prerender_targets.py            新增
scrims/urls.py                         新增
scrims/apps.py                         注册预渲染目标和插槽
scrims/wagtail_hooks.py                新增：后台活动管理
scrims/templates/scrims/               index / detail / me / slots / admin
scrims/tests/test_scrims.py            新增 40 个测试
accounts/services.py                   补上 M6 待办：游戏 ID 被内战报名占用时不能删
core/models.py                         scrim_reminder_hours 不再是「后续里程碑使用」
core/migrations/0008_*.py              新增（help_text 变更）
sjtu_ow/urls.py                        接入 scrims.urls
README.md                              内战一节
```
