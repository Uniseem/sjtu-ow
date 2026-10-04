# 167 表单里的编号乱填时不再 500，把探测变成常驻测试

## 背景

继续自主推进。166 修了地址里的超长编号。接着用同样的思路探测表单：在测试机上临时写了一个脚本，遍历项目自己的全部地址，以访客和成员的身份各 POST 几组乱填的数据（该填编号的地方填字母、20 位数字、空的、超长的），1176 次请求里三处 500：

```
BAD ('member', '/teams/16/members/remove/', ['action', 'game_account', 'member'], 500)
BAD ('member', '/teams/16/members/transfer/', ['action', 'game_account', 'member'], 500)
BAD ('member', '/scrims/5/signup/', ['action', 'body', 'game_account'], 500)
```

都是把表单里的值直接拿去按主键查：「abc」让 Django 报 `ValueError`。赛事的个人报名早就先 `int()` 再查（`tournaments/registration.py` 的 `_own_account`），内战和战队没有。顺着找，后台还有几处一样的：报名审核的赛事筛选和批量通过、导出时记日志、指定队长、临时队伍解散、内战勾选上场、功能权限按人筛选。

## 本轮范围

1. `core.converters.as_id()`：从表单或查询参数里取编号，规则和 166 的 `<id:>` 一样（最多 18 位数字），不是编号就是 None；上面这些地方都改用它
2. 166、167 的探测改成常驻测试 `core/tests/test_garbage_input.py`：遍历项目自己的全部地址，访客、成员、超级管理员各用乱填的表单和查询参数访问一遍，不能有 500（`/healthz` 的 503 是「worker 没在跑」的回答，不算）

## 验证

测试：两条遍历测试和 `as_id` 的单元测试；把每处改回原样，遍历测试要红（变异脚本）。

## 验收标准

测试机上整组检查全绿；变异全部被抓到；推送 `main`，CI 绿；演示站升级。
