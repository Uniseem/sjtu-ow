# 147 成员展示按常用位置筛、只看还没进战队的（报告）

## 做了什么

1. `members/services.py`：`Member.number`（全站加入顺序，`showcase()` 里编号）；`looking_for(members, role, free)`
2. `members/views.members_index()`：读 `role`、`free`，筛选时传 `shown`
3. `members/index.html`：筛选时不显示分组区块；「全部成员」头部写筛出几位、筛选栏（`data-member-filter`）；编号用 `member.number`；筛不到的提示
4. 设计 v6.40（6.3），README 成员展示一节
5. `members/tests/test_member_filter.py`（3 条，测试数据里有一个可见分组，才能测到「筛选时不显示分组」）
6. `scripts/screens.py`：第二个参数 `dark` 切深色；页面列表加成员筛选页

## 截图时发现并改掉的

测试机截手机宽度时，筛不到时那句提示紧贴着筛选栏（手机上头部和内容是上下排的，筛选栏没有下边距）。筛选栏加 `mb-6`，重截确认有间距了。

## 命令输出

变异（测试机，6 处，第一次全部被抓到）：

```
baseline green, 3 tests
caught the position is ignored -> test_by_usual_position
caught people in teams stay -> test_only_people_without_a_team
caught numbers start again at 001 -> test_by_usual_position
caught groups shown while filtering -> test_by_usual_position
caught an unknown position filters everyone out -> test_no_filter_lists_everyone_and_nobody_matching_says_so
caught no word when nobody matches -> test_no_filter_lists_everyone_and_nobody_matching_says_so
restored and green; missed: none
```

整组检查（测试机，加了间距之后又跑一次）：

```
== 错误页和模板一致 (22:37:14)
== Docker 镜像 (22:37:15)
构建成功：d5a0832314c4
== 全部通过 (22:37:15)
```

演示站升级后 `/members/?role=support&free=1`：

```
筛出 <span class="font-numeric">2</span> 位
```

## 没做 / 未验证

- 没按段位筛：段位本人可以不公开（3.5.1），按段位筛会让不公开的人消失，像是被排除
