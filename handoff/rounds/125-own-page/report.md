# 125 成员找到并整理自己的主页（报告）

## 做了什么

1. `templates/me/base.html`：页头昵称后面「我的主页」（能登录的人都验证过邮箱，都在成员展示里，所以链接一定有页面）
2. `members/views.member_detail` 传 `is_owner`；`members/detail.html`：本人看到「编辑资料」（链到基本资料），没写宣言时「还没写个人宣言，写一句」、没选位置时「还没选常用位置，去选」、没进战队时「去找一支招募中的」
3. 设计 v6.21（6.4）

## 命令输出

变异（`mutate.py`，5 处）。第一次漏了一处：「没进战队」的提示被去掉后，测试查的 `/teams/` 链接页头导航里每页都有，照样通过；改成查提示本身后整组重跑：

```
baseline green, 3 tests
caught no way from the personal centre -> test_the_personal_centre_links_to_my_page
caught everyone is the owner -> test_only_the_owner_sees_edit_and_hints
caught no motto hint -> test_only_the_owner_sees_edit_and_hints
caught the role hint shows anyway -> test_filled_in_parts_need_no_hint
caught no team hint -> test_only_the_owner_sees_edit_and_hints
restored and green; missed: none
```

整组检查：

```
All checks passed!
302 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
1475 passed in 222.63s (0:03:42)
```

演示站已升级（全量生成「成功 46，失败 0」，健康检查 ok）。

## 没做 / 未验证

- 没截图看「编辑资料」按钮在手机宽度下的位置
