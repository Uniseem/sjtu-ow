# 132 「我的报名」和报名详情页写比赛时间（报告）

## 做了什么

1. `tournaments/templates/tournaments/_starts_at.html`（新）：比赛时间或「未定」，两张表共用
2. `templates/me/registrations.html`：两张表第二列「比赛时间」（`data-starts`）
3. `tournaments/templates/tournaments/registration_detail.html`：页头在状态后面写「比赛 日期 时间」（`data-detail-starts`）
4. 设计 v6.27：8.6「显示」一行、8.8.1、13.5，头部版本号
5. `tournaments/tests/test_my_registrations.py`（3 条）

## 命令输出

变异（测试机，5 处，全部被抓到）：

```
baseline green, 3 tests
caught team entries without the time -> test_team_entries_show_the_start
caught individual entries without the time -> test_individual_entries_show_the_start
caught only the date -> test_team_entries_show_the_start
caught only the date -> test_individual_entries_show_the_start
caught the registration page leaves out the time -> test_the_registration_page_says_when
caught no 未定 -> test_team_entries_show_the_start
restored and green; missed: none
```

整组检查（测试机）：

```
1509 条测试分成 4 片
分片 1：378 passed in 34.60s
分片 2：377 passed in 36.20s
分片 3：377 passed in 34.93s
分片 4：377 passed in 32.08s
== 迁移 (20:18:59)
No changes detected
== 生产配置 (20:19:00)
System check identified no issues (0 silenced).
== 错误页和模板一致 (20:19:01)
== Docker 镜像 (20:19:02)
构建成功：88259ea5520e
== 全部通过 (20:19:02)
```

演示站已升级（没有迁移）。

## 没做 / 未验证

- 表格没有按比赛时间排序（战队报名仍按提交时间倒序）：已结束的、取消的混在一起时，按比赛时间排反而乱
- 没在浏览器里看手机宽度下多一列后的样子（`c-table--stack` 在手机上每行竖排，多一行标签不会撑宽）
