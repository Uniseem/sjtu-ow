# 055 内战管理员拿不到内战权限

## 背景

053 部署时 `init_site` 输出：

```
以下内容仍等到后续里程碑写入（命令可重复执行）：
  - 内战管理员的内战管理权限（M6）
```

M6 早就完成了。054 查下来**不是提示过时，是真的漏了**：

- 赛事有 `tournaments.services.assign_tournament_permissions()`，给赛事管理员组加上赛事的增删改查权限，`init_site` 会调用
- 内战**没有对应的函数**。内战后台判断「能不能管理」看的是 `scrims.change_scrim`（`scrims.services.can_manage`），后台的内战列表、新建、编辑用的是 Wagtail 按模型权限判断的那一套
- 结果：**只有超级管理员能管内战**。设计 4.1 的角色表里「创建内战、勾选上场、调整分队」这一项，内战管理员那一格是 ✓

现有测试里没有一条用非超级管理员打开过内战后台，所以一直没被发现。

## 任务

1. `scrims/services.py` 加 `assign_scrim_permissions()`，照赛事的写法，给「内战管理员」组 `scrims` 的 `add_scrim`、`change_scrim`、`delete_scrim`、`view_scrim`
2. `init_site` 调用它，删掉「等到后续里程碑」那段提示
3. 测试：跑完 `init_site` 后，内战管理员组的成员能打开内战后台列表、新建页和分队页；拿不到赛事权限（角色之间不串）
4. 变异确认：不调用这个函数时测试会红
5. 测试机上重新跑一次 `init_site`，确认输出里有内战权限那一行

## 验收标准

本地四项检查干净，推送后 CI 绿；测试机上 `init_site` 输出正确。
