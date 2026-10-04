# 156 首页「我的安排」（报告）

## 做了什么

1. `core/agenda.py`（新）：`Item`、`items_for(user)`、`agenda_context()`、`my_agenda_slot()`
2. `templates/slots/agenda.html`（新）：登录的人才有面板；每条日期块、标题（链接）、「类型 · 周几 时间 · 说明」
3. `core/apps.py`：注册 `my-agenda`
4. `content/models.HomePage.get_context()`：加 `agenda_context`；首页模板在「近期」区块头下面引用
5. 设计 v6.48（5.2）
6. `core/tests/test_agenda.py`（3 条）；`scripts/screens.py` 加首页

## 截图发现并改掉的

第一版行用了 `c-row--plain`，那是给没有日期块的行用的两列布局，第二列按内容撑宽，说明一长（「赛事 · 周五 08:13 · 截图战队 · 待审核」）就压到日期块上。改用普通的 `c-row`（三列）加 `px-0`，重截正常。

## 测试修正

「队长看到自己的赛事」第一版从「我的安排」开头往后截取标题，截到了下面公开的「近期」大图卡里同名的赛事，去掉名单那一段测试照样绿（变异漏了这一处）。改成只取带 `data-agenda-item` 的行里的标题，重跑抓到。

## 命令输出

变异（测试机，10 处，修正测试后全部被抓到）：

```
baseline green, 3 tests
caught old scrims stay -> test_past_cancelled_and_strangers_see_nothing
caught cancelled scrims stay -> test_past_cancelled_and_strangers_see_nothing
caught no scrims -> test_my_signups_in_time_order
caught no rosters -> test_my_signups_in_time_order
caught cancelled tournaments stay -> test_a_cancelled_tournament_leaves_the_list
caught no pool signups -> test_my_signups_in_time_order
caught undated first -> test_my_signups_in_time_order
caught not on the homepage -> test_my_signups_in_time_order
caught no slot to fetch -> test_my_signups_in_time_order
caught strangers get the panel -> test_past_cancelled_and_strangers_see_nothing
restored and green; missed: none
```

整组检查（测试机）：

```
1588 条测试分成 4 片
分片 1：397 passed in 35.53s
分片 2：397 passed in 35.46s
分片 3：397 passed in 35.56s
分片 4：397 passed in 35.43s
== 迁移 (00:18:27)
No changes detected
== 生产配置 (00:18:28)
System check identified no issues (0 silenced).
== 错误页和模板一致 (00:18:29)
== Docker 镜像 (00:18:30)
构建成功：9286f6ba3dbe
== 全部通过 (00:18:30)
```

演示站升级后，预渲染的首页里有空的替换区块（`data-slot="my-agenda"` 出现 1 次），登录的成员会由脚本填进来。

## 没做 / 未验证

- 演示站上没登录看（没有账号）；测试机截图是开发服务器直接渲染的
