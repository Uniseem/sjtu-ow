# 178 战队主页和管理页标出账号已停用的成员（报告）

## 做了什么

1. `teams/templates/teams/detail.html`：队头「队长 X（账号已停用）」；成员卡片上停用的人加「账号已停用」标签，不显示宣言和位置段位（`data-account-stopped`）
2. `teams/templates/teams/manage.html`：成员表里标「账号已停用」，小字「这个账号被管理员停用了，可以移出、空出名额」
3. `teams/services.can_apply`：队长停用了的战队返回 `CAPTAIN_STOPPED`「这支战队的队长账号已停用，等管理员指定新队长后再申请。」
4. 设计 v6.61（3.7）；细节 5.3、5.5
5. `teams/tests/test_stopped_members.py`（4 条）

## 编号

本来是 179，排在「守卫普查」后面。普查在测试机上跑得比预计慢（同时在跑别的检查，25 分钟 23 个守卫，254 个要三四个小时），为了不卡住提交，这一轮先用 178；普查跑完后用当时的编号。这一轮是在本机单独的 git 工作树里做的，和普查的文件分开。

## 命令输出

变异（测试机，5 处，全部被抓到）：

```
baseline green, 4 tests
caught no tag on the card -> test_the_team_page_marks_the_stopped_member
caught no tag on the card -> test_a_stopped_captain_is_said_so_up_top
caught the motto still shown -> test_the_team_page_marks_the_stopped_member
caught nothing said up top -> test_a_stopped_captain_is_said_so_up_top
caught the captain's page silent -> test_the_captain_sees_whom_to_remove
caught applications still open -> test_nobody_applies_to_a_team_whose_captain_is_stopped
restored and green; missed: none
```

整组检查（测试机，普查同时在跑，所以每片慢了一倍）：

```
1656 条测试分成 4 片
分片 1：414 passed in 79.82s (0:01:19)
分片 2：414 passed in 75.61s (0:01:15)
分片 3：414 passed in 87.44s (0:01:27)
分片 4：414 passed in 78.59s (0:01:18)
== 全部通过 (06:17:40)
```

演示站升级后，在服务器上把一个战队成员临时改成停用（`update`，不经过网站、不触发重新生成），用测试客户端看战队主页，再改回来：

```
战队: 零号机 停用标签: 1 成员还在: True
恢复后停用标签: 0
```

## 没做

- 队长停用了的战队在战队列表里仍显示「招募中」，点进去申请时才看到原因；列表上没单独标
