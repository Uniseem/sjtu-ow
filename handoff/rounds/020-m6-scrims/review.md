# 020 复核结果

> 实现方自查（用户外出）。等用户回来，008–020 可以一起交给 Grok 做独立复核。

## 结论

**通过。** 自查中修掉 **1 个在真实浏览器里才暴露的功能失效**（「修改报名」按钮点了没反应），并按前两轮的教训对新测试做了**变异测试**，确认它们真的会红。另外发现一个前几轮遗留的后台观感问题（gravatar 被 CSP 挡），没有自作主张改，留给用户拍板。

## 验证记录

| 验证 | 方法 | 结果 |
|---|---|---|
| 检查与测试 | `ruff`、`pytest`、`makemigrations --check`、生产 `check --deploy` | 461 passed，部署检查干净 |
| 变异测试 | 故意改坏 3 处实现 | 3 个测试各自失败 ✓ |
| 完整流程 | 真实浏览器：建活动 → 发布 → 报名 → 修改 → 取消 | 全部走通，服务器日志有对应 POST |
| 草稿 | 匿名直接访问 URL | 404，列表里也搜不到 |
| 已取消 | 匿名访问 | 详情页 200 并显示「已取消」，不在列表里 |
| 隐私 | 整页 HTML 搜段位 / 游戏 ID / 邮箱 / QQ | 全是 0 次 |
| 分队失效 | 造出「已分到 A 队」再取消报名 | 人被移出，`teams_are_stale` 变 True |
| 两套段位规则 | 角色限定缺段位 / 不限位置只有一个段位 | 前者拒绝、后者通过 |
| 七个前置条件 | 逐条构造 | 各自给出对应提示 |
| 邮件 | 真实触发 | 提醒和取消两封，内容正确 |
| 幂等 | 提醒任务连跑两次 | `sent:1` 然后 `already_sent`，只发一封 |
| 控制台 | 真实浏览器 | 修完之后无错误 |
| 容器 | `docker build`、`caddy validate` | 都通过 |
| 清理 | **全库计数** | 业务表全 0，只剩骨架 |

## 自查中发现并已修掉

### A1 「修改报名」按钮点了没反应（功能失效）

我在报名框里写了：

```html
<button type="button" x-data x-on:click="$refs.editform.hidden = !$refs.editform.hidden">修改报名</button>
```

单元测试全绿，页面也渲染得好好的。但在真实浏览器里点下去什么都没发生，控制台是：

```
Alpine Expression Error: Cannot read property of null or undefined
Expression: "$refs.editform.hidden = !$refs.editform.hidden"
```

原因：本站装的是 **Alpine 的 CSP 构建**（`static/vendor/alpine.csp.min.js`，README 里写着「自托管前端脚本（不走 CDN）」）。CSP 构建**不会**对属性里的表达式求值——那需要 `eval` 一类的能力，正是 CSP 要禁的。要用 Alpine 得先 `Alpine.data()` 注册组件再引用它的方法。

查了一下，**本项目此前一个 `x-data` 都没有**，我是第一个用的，也第一个踩到。

修法：根本不用脚本。`<details>` / `<summary>` 就是浏览器原生的展开收起，任何 CSP 下都能用：

```html
<details class="mt-2">
  <summary class="btn btn-outline btn-sm min-h-11 font-button">修改报名</summary>
  <div class="mt-3">{% include "scrims/slots/_form.html" %}</div>
</details>
```

修完在真实浏览器里点开确认：表单展开，带着当前的游戏 ID 和已勾选位置，控制台干净。

加了一条测试守住它：断言页面 HTML 里**不出现** `x-data` / `x-on:` / `x-ref` / `@click`，并且确实有 `<details>`。

### A2 按 019 的教训，这次先做了变异测试

019 的教训是「状态码 200 不算验证过」。这轮 40 个测试第一次跑就全绿，这本身值得怀疑，所以我故意改坏了三处实现：

| 改坏 | 应该失败的测试 | 实际 |
|---|---|---|
| 角色限定的段位校验改成空列表（永远通过） | `test_role_queue_requires_a_rank_for_every_ticked_role` | 失败 ✓ |
| 取消报名不再盖 `roster_changed_at` | `test_cancelling_after_the_split_marks_the_teams_stale` | 失败 ✓ |
| 列表改成 `exclude(DRAFT)`（不再排除已取消） | `test_the_list_shows_published_and_recently_finished` | 失败 ✓ |

三次都红了，每次只红该红的那个。测试确实咬得住实现。

**这一步值得固化成惯例**：新写的关键测试，至少挑两三条做一次变异测试再交。比事后被复核方指出来便宜得多。

### A3 `teams_are_stale` 一开始会误报

第一版用 `scrim.updated_at > scrim.teams_generated_at` 判断「分队有变化」。但 `updated_at` 是 `auto_now`，管理员改个标题、改个说明都会动它，于是分完队之后随便编辑一下就会跳出「分队有变化」，而名单一个人都没少。

改成单独的 `roster_changed_at`，只在报名真的变动（取消、换游戏 ID）时盖。

### A4 URL 命名空间撞车

`scrims/urls.py` 第一版写了 `app_name = "scrims"`，`manage.py check` 报 `urls.W005`：Wagtail 的 ModelViewSet 已经注册了 `scrims` 这个命名空间。`tournaments` 早就踩过，所以前台 URL 用的是平铺名字（`tournament_index` 而不是 `tournaments:index`）。照抄了这个做法。

**顺带说明**：这个警告只有 `manage.py check` 会报，`pytest` 不会。如果只跑测试就交了，这条会漏过去。

## 建议修 / 等用户定

1. **Wagtail 后台头像被 CSP 挡**（前几轮就有，不是本轮引入）。后台每个页面都会去 `www.gravatar.com` 取头像，被 `ADMIN_CSP` 的 `img-src 'self' data: blob:` 拦下，控制台常年几条错误，头像空白。

   两条路：放行 gravatar（等于给后台加一个外部请求，还把管理员邮箱的 MD5 发给第三方），或者 `WAGTAIL_GRAVATAR_PROVIDER_URL = None` 关掉。**我倾向关掉**——本站 CSP 本来就不让外部图片，把管理员邮箱哈希送给 Gravatar 和隐私政策的口径也不一致。但这是个产品选择，等用户定，没有自己改。

2. **`ScrimSignup.game_account` 用的是 `PROTECT`**。配合这轮补的 `deletion_blocked_reason`，用户在前台删游戏 ID 会被友好地拦下。但如果哪天有别的路径直接 `account.delete()`，会抛 `ProtectedError` 而不是友好提示。021 做分队页时留意一下。

## 认可的判断

1. 草稿用 **404 而不是 403**：403 等于承认「这个 ID 上有东西，只是你不能看」。
2. live 页面和插槽片段共用同一个 `actions_context()`——015 踩过「实时渲染的页面显示匿名插槽」的坑，这次从一开始就共用。
3. 取消报名时连 `is_selected` / `team` / `assigned_role` / `rating_used` 一起清掉，而不是只删报名行——021 的分队页不用再处理「队伍里有个已经不存在的人」。
4. 报名用的游戏 ID 在活动结束前不能删（`accounts/services.py` 里留了两轮的 M6 待办，这轮补上了）。

## 文档更新

- `docs/design.md` 本轮**没有改动**。
- `README.md` 加了「内战」一节。
- `handoff/STATUS.md` 轮次表加 020，M6 标记为进行中。
