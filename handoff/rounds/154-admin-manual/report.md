# 154 后台手册（报告）

## 做了什么

1. `core/admin_manual.py`（新）：`Step`、`Part`，五部分的内容；`parts_for(user)`；`manual_view`
2. `core/templates/core/admin/manual.html`（新）：目录按钮、每部分一个有序列表，步骤后面带「入口 →」
3. `core/wagtail_hooks.py`：`ManualMenuItem`（`is_shown` 看有没有部分）、地址 `manual/`
4. 设计 v6.47（14.1 菜单表和说明），README 新增「后台手册」一节（提醒改了后台入口要同步改手册）
5. `core/tests/test_admin_manual.py`（3 条）

写之前核对了每个链接的地址名（`tournaments:add`、`registration_review_index`、`scrims:add`、`moderation_index`、`avatar_review`、`comments:index`、`wagtailsnippets_members_membergroup:list`、`wagtailusers_users:index`），都能解析。

## 命令输出

变异（测试机）。第一次 7 处漏了 2 处：
- 「投稿者看到菜单」：投稿者的后台菜单本来就只留首页和图片（14.3），菜单项自己的判断对他们是重复的，等价，从清单里拿掉并注明
- 「步骤丢了链接」：测试断言的地址在左侧菜单里也有，改成断言步骤里那个带「→」的链接

重跑：

```
baseline green, 2 tests
caught everyone gets the tournament part -> test_each_role_gets_its_parts
caught superusers miss the content part -> test_each_role_gets_its_parts
caught no owner part -> test_each_role_gets_its_parts
caught authors get nothing -> test_each_role_gets_its_parts
caught submitters open the page -> test_the_page_and_its_menu
caught steps lose their links -> test_the_page_and_its_menu
restored and green; missed: none
```

整组检查（测试机）：

```
1585 条测试分成 4 片
分片 1：397 passed in 38.84s
分片 2：396 passed in 39.68s
分片 3：396 passed in 39.15s
分片 4：396 passed in 39.88s
== 迁移 (23:52:50)
No changes detected
== 生产配置 (23:52:52)
System check identified no issues (0 silenced).
== 错误页和模板一致 (23:52:53)
== Docker 镜像 (23:52:54)
构建成功：7cf4dac3623f
== 全部通过 (23:52:54)
```

演示站已升级（没有迁移）。

## 没做 / 未验证

- 没截后台手册页的图（Wagtail 后台样式）
- 手册内容是文字写死在代码里的，后台入口改了要人记得同步（README 里写了）
