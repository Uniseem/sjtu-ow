# 149 「我的战队」写队内联系方式（报告）

## 做了什么

1. `templates/me/teams.html`：表头加「队内联系方式」，每行一格（`data-member-contact`），手机上 `c-table--stack` 竖排带标签
2. 设计 v6.42（7.1）
3. `teams/tests/test_member_contact.py` 加 1 条

## 命令输出

变异（测试机，3 处，第一次全部被抓到）：

```
baseline green, 1 tests
caught the contact is not shown -> test_my_teams_lists_how_to_reach_each
caught no word when the captain has not filled it -> test_my_teams_lists_how_to_reach_each
caught the captain is not sent to fill it -> test_my_teams_lists_how_to_reach_each
restored and green; missed: none
```

整组检查（测试机）：

```
1576 条测试分成 4 片
分片 1：394 passed in 34.52s
分片 2：394 passed in 32.25s
分片 3：394 passed in 33.74s
分片 4：394 passed in 34.73s
...
== Docker 镜像 (23:01:22)
构建成功：9be795869231
== 全部通过 (23:01:22)
```

演示站已升级（没有迁移）。

## 没做 / 未验证

- 没截这一页（表格多一列，手机上是竖排的一行标签加内容）
