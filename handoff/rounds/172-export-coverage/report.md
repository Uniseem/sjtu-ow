# 172 导出个人信息补齐，以后新加的表也漏不了（报告）

## 做了什么

1. `accounts/services.personal_data()` 加三节：`comments`、`comment_likes`、`feature_rules`
2. `accounts/services.py`：`EXPORTED`（14 个字段 → 导出到哪一节）、`NOT_EXPORTED`（21 个字段 → 为什么不导出：管理员和队长的操作人记录、Wagtail 页面的所有者和锁定人、别人回复本人的评论、AI 审核的内部记录）
3. `accounts/tests/test_export_coverage.py`（2 条）：数一遍项目里所有指向用户的字段，必须正好是两份清单的并集、两份不重叠，导出里要有 `EXPORTED` 写的每一节；三节的内容
4. 设计 v6.56（3.8）；README「注销账号与导出个人信息」

## 怎么查的

在测试机上临时列出项目各应用里所有指向用户的外键（35 个，见请求），逐个对导出的 12 节。导出漏掉的、确实属于本人的：评论正文、点过的赞、对本人单独设置的功能权限（含原因）。

**AI 审核记录没放进导出**：它是内部复核用的（设计 5.5），送审的内容本身（昵称、宣言、文章、评论）都已经导出；这是我的判断，写在 `NOT_EXPORTED` 和复核里。

## 命令输出

变异（测试机，6 处，全部被抓到）：

```
baseline green, 2 tests
caught comments forgotten again -> test_every_column_pointing_at_a_person_is_accounted_for
caught listed but not exported -> test_every_column_pointing_at_a_person_is_accounted_for
caught listed but not exported -> test_comments_likes_and_rules_go_out
caught listed twice -> test_every_column_pointing_at_a_person_is_accounted_for
caught others' comments too -> test_comments_likes_and_rules_go_out
caught hidden shown as public -> test_comments_likes_and_rules_go_out
caught reason left out -> test_comments_likes_and_rules_go_out
restored and green; missed: none
```

整组检查（测试机）：

```
1638 条测试分成 4 片
分片 1：410 passed in 47.12s
分片 2：410 passed in 38.10s
分片 3：409 passed in 36.91s
分片 4：409 passed in 38.75s
== 全部通过 (05:13:32)
```

演示站升级后，在服务器上给评论最多的演示用户生成一份导出：

```
导出的节: 15 评论: 6 点赞: 6 功能权限: 0
第一条评论: {'article': '新手入门：第一次打守望先锋该知道的几件事', 'state': '公开'}
```

## 没做

- 隐私政策草稿（`content/legal/privacy.md`）只写了「包含本站保存的你的全部个人信息」，没有逐项列，不用改
