# 167 表单里的编号乱填时不再 500，把探测变成常驻测试（报告）

## 做了什么

1. `core/converters.py`：`as_id(value)`，最多 18 位数字的才是编号，否则 None
2. 改用 `as_id` 的地方：
   - 前台：`teams/views.py` 移出成员、转让队长；`scrims/services.py` 报名时选的游戏 ID、后台勾选上场（`set_selection` 原来 `int()` 每个值）
   - 后台：`teams/wagtail_hooks.py` 指定队长；`accounts/wagtail_hooks.py` 功能权限按人筛选和新建时预填；`tournaments/teams_admin.py` 解散临时队伍；`tournaments/review_admin.py` 按赛事筛选、批量通过、导出时记日志（原来 `int()`）
3. `core/tests/test_garbage_input.py`（新，3 条）：遍历项目自己的全部地址（Wagtail、allauth 自己的不算），填上真实的编号；访客、成员 POST 7 组乱填的数据，超级管理员对后台地址也 POST 一遍；三种身份各带一组乱填的查询参数 GET 一遍；不能有 500。账号注销、解散这类地址排在最后。`as_id` 的单元测试

## 怎么发现的

166 之后临时写了一个 POST 探测（没提交），访客和成员各对每个地址 POST 6 组数据，1176 次里三处 500（见请求）。改成常驻测试、加上超级管理员以后又找到四处：

```
('get', '/admin/registrations/export.csv', [...])        导出记日志时 int(tournament_id)
('post', '/admin/registrations/bulk-approve/', [...])    批量通过时 filter(pk=任意值)
```

以及 `set_selection` 的 `int(value)`。另外一开始 `/healthz` 也被算进去了：测试里没有 worker 心跳，它返回 503，这是它该给的回答，只把 500 算作崩溃。

第一次跑变异，勾选上场、指定队长、解散临时队伍三处改回去没被抓到：这三个是后台地址（`admin/scrims/…`、`admin/teams/…`、`admin/tournaments/…`），填编号时只认 `scrims/` 这类开头，后台地址里填的是 1，找不到对象就 404，根本没走到表单处理。去掉 `admin/` 前缀再匹配以后都抓到了。

## 命令输出

变异（测试机，11 处，全部被抓到）：

```
baseline green, 3 tests
caught anything is an id -> test_what_counts_as_an_id
caught anything is an id -> test_garbage_posts_never_crash
caught member removed raw -> test_garbage_posts_never_crash
caught captain passed on raw -> test_garbage_posts_never_crash
caught scrim game ID raw -> test_garbage_posts_never_crash
caught players picked raw -> test_garbage_posts_never_crash
caught new captain raw -> test_garbage_posts_never_crash
caught feature rules filtered raw -> test_garbage_queries_never_crash
caught team dissolved raw -> test_garbage_posts_never_crash
caught reviews filtered raw -> test_garbage_queries_never_crash
caught export logged raw -> test_garbage_queries_never_crash
caught bulk approve raw -> test_garbage_posts_never_crash
restored and green; missed: none
```

两条遍历测试在测试机上约 6 秒和 2 秒（`--durations`）。

整组检查（测试机）：

```
1626 条测试分成 4 片
分片 1：407 passed in 38.21s
分片 2：407 passed in 42.20s
分片 3：406 passed in 35.13s
分片 4：406 passed in 34.55s
== 全部通过 (03:08:29)
```

演示站升级后，在服务器上用测试客户端以一个演示成员给「周日下午 · 新人友好场」报名，游戏 ID 填「abc」：

```
乱填游戏 ID 报名: 302 /scrims/7/ 报名数没变: True
```

## 没做

- 遍历测试只用固定的几组乱填数据，不是随机生成；新加的表单字段名不在这几组里的话，测不到。以后加了按编号查的表单字段，记得用 `as_id`
