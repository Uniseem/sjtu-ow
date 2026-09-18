# 055 实现报告

## 结论

**完成。** 内战管理员组现在拿得到内战权限了。`init_site` 新增 `assign_scrim_permissions()`，删掉了「等到 M6」的过时提示。测试机上已生效。

## 问题

M6（020、021 轮）做内战时，只写了判断「能不能管理」的 `can_manage`（看 `scrims.change_scrim`），**没写给内战管理员组分配这项权限的代码**。赛事那边有 `assign_tournament_permissions()`，内战没有对应的。`init_site` 里那句「等到 M6」的提示是 005 轮写的占位，M6 做完时没人回头看它。

后果：**只有超级管理员能管内战**。设计 4.1 的角色表里，「创建内战、勾选上场、调整分队」这一项内战管理员那一格是 ✓。

为什么一直没被发现：内战的测试全都用超级管理员登录后台，**没有一条用内战管理员打开过**。

## 修法

`scrims/services.py`：

```python
SCRIM_PERMISSIONS = ("add_scrim", "change_scrim", "delete_scrim", "view_scrim")

def assign_scrim_permissions() -> list[str]:
    ...  # 和 assign_tournament_permissions 一样的写法
```

`init_site` 调用它，输出「已分配内战权限：内战管理员 可创建内战、勾选上场、调整分队」。删掉「以下内容仍等到后续里程碑写入」那一段——里面只剩这一条。

## 测试

`scrims/tests/test_manager_permissions.py`，用一个只属于「内战管理员」组、**不是超级管理员**的用户：

- 跑完 `init_site` 后有这四项权限，`can_manage` 为真
- 能打开内战后台的列表、新建、编辑页和分队页（都是 200）
- 拿不到赛事权限（角色之间不串）

变异：`init_site` 不调用这个函数时：

```
✓ 被抓到 init_site 不分配内战权限 | 2 failed, 1 passed in 0.53s ['test_init_site_grants_the_scrim_permissions', 'test_a_scrim_manager_can_open_the_scrim_admin']
已还原: True
```

## 测试机

补丁套到测试机、重建镜像后重新跑 `init_site`：

```
已确保用户组存在：内战管理员
已分配本轮权限：后台角色可进入 Wagtail；赛事管理员和内战管理员可查看联系方式。
已分配内战权限：内战管理员 可创建内战、勾选上场、调整分队
```

内战管理员组的全部权限：

```
['access_admin', 'add_scrim', 'change_scrim', 'delete_scrim', 'view_contactmethod', 'view_scrim']
```

重建后：

```
sjtu-ow-test-worker-1	Up 27 seconds
sjtu-ow-test-web-1	Up 27 seconds (healthy)
sjtu-ow-test-proxy-1	Up 8 minutes
```

提交推送后，测试机撤掉补丁、`git pull` 回到和仓库一致。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
216 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python -m pytest -q
693 passed in 47.46s
```

054 推送后的 CI：`success 054: 部署修复：重启策略、健康检查、定时任务`。

## 改动文件

```
scrims/services.py                         SCRIM_PERMISSIONS、assign_scrim_permissions
core/management/commands/init_site.py      调用它；删掉过时提示
scrims/tests/test_manager_permissions.py   新建，3 条
README.md                                  init_site 的说明
handoff/STATUS.md
handoff/rounds/055-scrim-manager-permissions/
```
