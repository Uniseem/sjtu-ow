# 013 实现报告

> 用户外出期间由 Claude 实现 + 自查。**M3 到此完成。**

## 结论

T0–T7 已完成：先修掉 012 自查记下的邮件隐私问题，然后做完组队大厅——游戏模式、车帖的发布 / 编辑 / 状态 / 过期、需要登录的列表（静态外壳 + HTMX 列表 + 30 秒自动刷新）、相对时间和复制按钮、首页真实数量、AI 审核接入、后台关闭车帖。270 个测试通过（本轮新增 25 个）。

## 逐条结果

### T0 邮件隐私（012 的 B3）

`teams/notifications.py` 和 `moderation/notifications.py` 的群发改成**逐封发送**，收件人再也看不到彼此的邮箱。两处都加了测试（解散一支 2 人战队发 2 封、每封只有 1 个收件人；高风险通知同理）。

### T1 游戏模式

`core.GameMode` snippet（名称、排序、是否启用），后台主菜单「游戏模式」。`init_site` 写入五个初始模式，可重复执行（测试断言两次调用拿到同样的 5 条）。`init_site` 的「后续里程碑」清单里去掉了这一项。

### T2 车帖数据表

`LfgPost` 按设计 12.7.1：车主、游戏 ID（级联删除）、模式（PROTECT）、三个位置布尔、开车时间、过期时间、状态、备注，索引 `(expires_at, status)`。**没有定时任务**，过期只靠列表查询条件。

### T3 发车与编辑

- 游戏 ID 只能选自己的、模式只能选启用的、位置至少一个、开车时间在「前 10 分钟 ~ 7 天后」之间、备注 200 字。
- `lfg_post` 功能权限 + 至少一个游戏 ID + 未过期车帖不超过上限（后台默认 3）。
- 过期时间 = 开车时间 + 2 小时（后台可调）；**改开车时间会重算过期时间**（测试断言）。
- 「招人中 / 已满」可来回切；关闭后不能重开（测试断言）；非车主改不动。
- 限流每人每小时 10 次（测试：第 11 次不再入库）。

### T4 列表

`/lfg/` 需要登录才能看到车帖；只显示未过期、未关闭、车主未停用的；**已满排在后面**（`Case/When` 注解排序）；模式单选、位置多选（满足任一）、只看招人中三种筛选；每 30 秒自动刷新（`hx-trigger="change, submit, load, every 30s"`）。卡片显示模式、开车时间（浏览器算相对时间）、状态、缺的位置、游戏 ID + 复制按钮、车主昵称、备注，车主自己还能看到编辑 / 标记已满 / 关闭。

### T5 半静态与占位

- `/lfg/` 注册为预渲染目标，但**只有外壳**：静态文件里没有任何车帖数据（验收 3）。
- 列表走 `/_fragments/lfg/`，登录检查在这个请求里做——未登录返回「登录后查看」卡片。
- 首页「组队大厅」占位改成 `lfg.slots.home_lfg_slot`：登录用户看到真实的招人中数量，未登录仍是「登录后查看」（测试断言两种情况）。

### T6 AI 审核

车帖备注在发布和修改时送审（`lfg_note`）。送审失败只记日志，不影响发车。

### T7 后台

「社区 → 车帖」：列表 + 检查视图（只读），行内「更多」里有「关闭车帖」（带确认页）。权限和内容审核队列一致（内容编辑 + 超级管理员）。

## 验收输出

### 1. 检查与测试

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
194 files already formatted

$ uv run python -m pytest -q
270 passed in 16.37s

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

新增 25 个测试：过期时间计算与重算、时间窗口、数量上限、权限与游戏 ID、位置必选、别人的游戏 ID、状态切换、关闭不可逆、非车主不能动、过期 / 关闭 / 停用车主从列表消失、已满排后面、三种筛选、列表需要登录、外壳无数据、备注送审、首页占位两种情况、限流、后台关闭、后台权限、游戏模式幂等、以及 T0 的两条邮件隐私测试。

### 2. 浏览器真实走一遍

未登录打开 `/lfg/`：外壳 + 筛选栏 + 「登录后查看」，网络面板里只有一次 `/_fragments/lfg/?mode=` 请求。

登录后发车（竞技（角色限定）、缺输出、备注「差一个输出，钻石局，欢迎上车。」）→ 列表立刻出现：

```
竞技（角色限定）  3 分钟前  招人中  缺输出
Driver013#5678  复制   车主 车主验收
差一个输出，钻石局，欢迎上车。
编辑 | 标记已满 | 关闭
```

点「标记已满」→ 徽章变成「已满」，按钮变成「改回招人中」。关闭后：

```
关闭前列表里有: 1 条
关闭后状态: closed | 列表里有: 0 条
尝试重开 → closed
列表里还看得到吗: False
```

相对时间和复制按钮（JS 在外部文件里，CSP 不受影响）：

```js
{text: "2 分钟前", title: "9月16日 19:37", copyButtons: 1}
```

### 3. 静态外壳没有车帖数据

```
prerendered/lfg/index.html  字节: 6156
  含车帖数据: False        含CSRF token: False
  含HTMX 列表请求: True    含30 秒刷新: True
  含昵称: False
```

### 4. 自动刷新

页面停留 35 秒后：

```js
{count: 2, gaps: [30]}   // 两次 /_fragments/lfg/ 请求，间隔 30 秒
```

### 5. 手机宽度

375px：`{width: 375, inline: 0, overflow: false}`，筛选栏自动换行，卡片可读。

### 6. 回归

```
/        200    /news/   200    /teams/  200
/lfg/    200    /about/  200    /healthz 200（worker 起来之后）
```

### 7. docker / caddy

```
Successfully built 1182e4cb7beb
Valid configuration
```

### 8. 清理

验收用的车帖和账号 `lfg013@example.com` 都已删除；预渲染目录重新生成（10 个页面，含 `/lfg/` 外壳）。

## 设计偏差

**没有改设计文档。** 实现按第 6 章、12.7、12.4.2、13.13.1 做。几个实现选择：

1. **列表片段的地址是 `/_fragments/lfg/`**：设计 13.13.2 规定 `/_fragments/` 开头的请求直接转给 Django，正好符合「列表永远实时」。
2. **相对时间和复制按钮写在 `static/js/app.js` 里**（外部文件、事件委托），没有内联脚本，CSP 不用放宽。
3. **后台车帖列表是只读的**（`exclude_form_fields = []` + 关闭 add/edit），管理员唯一能做的动作是「关闭」，符合设计 6.2。
4. 首页的组队大厅数量对未登录访客仍然是「登录后查看」，登录用户由占位区域填充——静态首页因此不含任何数量信息。

## 未完成 / 不同意

1. 设计 6.3 说「排序：按开车时间从早到晚，已满的排在后面」——我按「先按是否已满，再按开车时间」实现，符合字面意思。
2. 车帖没有单独的详情页（设计里也没有），列表卡片就是全部信息。
3. 组队大厅没有接入「我的车帖」页面（设计 13.4 的路由表里没有这一条），车主在列表里管理自己的车帖。

## 顺带发现

1. **开发环境的浏览器会缓存 `/static/js/app.js`**：改完 JS 后页面行为没变，是缓存不是代码问题（生产静态文件带哈希，不受影响）。验收时要记得强制刷新。
2. `ModelViewSet` 即使只做只读也必须给 `form_fields` / `exclude_form_fields`，否则启动直接报 `ImproperlyConfigured`。
3. 全量测试里 `test_reprocess_clears_old_slice_files` **偶发失败过一次**，之后连跑 5 次（含单独跑）都通过，没能复现。已经给这个测试加上对返回值的断言（`== "done"`），下次再出现能直接看出是不是被「同一时间只处理一个字体」挡住了。

## 需要确认

无。

## 改动文件

新增：`lfg/models.py`、`services.py`、`forms.py`、`views.py`、`urls.py`、`slots.py`、`prerender_targets.py`、`wagtail_hooks.py`、`migrations/0001_initial.py`、`templates/lfg/**`、`tests/test_lfg.py`；`core/migrations/0007_game_mode.py`。

修改：`lfg/apps.py`、`core/models.py`（GameMode）、`core/services.py`、`core/wagtail_hooks.py`、`core/management/commands/init_site.py`、`content/models.py`（首页数量）、`teams/notifications.py`、`moderation/notifications.py`、`static/js/app.js`、`sjtu_ow/urls.py`、`README.md`、`handoff/STATUS.md`、`core/tests/test_fonts.py`（断言加固）、`teams/tests/test_teams.py`、`moderation/tests/test_moderation.py`。
