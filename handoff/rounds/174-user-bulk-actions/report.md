# 174 后台用户列表的批量删除、批量停用关掉（报告）

## 做了什么

1. `accounts/wagtail_hooks.py`：`USER_BULK_ACTIONS_OFF = ("delete", "set_active_state")`。Wagtail 的批量操作登记表第一次被列表页用到时才扫描各应用的钩子；包一层扫描函数，扫完从用户模型那一栏去掉这两个（每次调用都去一遍，扫描早于这段代码也不怕）。列表上不再有这两个按钮；登记表里找不到，Wagtail 的批量操作视图返回 404
2. 设计 v6.58（3.7）
3. `accounts/tests/test_user_bulk_actions.py`（2 条）

用的是 Wagtail 登记表的内部方法（没有公开的「取消登记」办法）；Wagtail 升级改了它的话，测试会红（按钮又出现、删除地址又能用）。

## 怎么发现的

173 对停用账号，看后台「用户」列表时注意到底部的批量操作。在测试机上临时写脚本试（没提交）：

```
BULK ['/admin/bulk/accounts/user/assign_role/', '/admin/bulk/accounts/user/delete/', '/admin/bulk/accounts/user/set_active_state/']
GET delete 200
POST delete 302 victim: None
```

勾一个用户批量删除，用户这一行没了。

## 命令输出

变异（测试机，3 处，全部被抓到）：

```
baseline green, 2 tests
caught bulk delete back -> test_only_assigning_roles_is_left
caught bulk delete back -> test_the_addresses_do_nothing
caught bulk switch-off back -> test_only_assigning_roles_is_left
caught the registry left alone -> test_only_assigning_roles_is_left
caught the registry left alone -> test_the_addresses_do_nothing
restored and green; missed: none
```

整组检查（测试机）：

```
1645 条测试分成 4 片
分片 1：412 passed in 35.86s
分片 2：411 passed in 37.18s
分片 3：411 passed in 42.57s
分片 4：411 passed in 39.10s
== 全部通过 (05:33:13)
```

演示站升级后，在服务器上临时建一个没有邮箱、不能登录的超级管理员账号（`bulk-probe-174@probe.invalid`），用测试客户端以它打开用户列表，看完删掉：

```
批量操作: ['assign_role']
批量删除地址: 404
检查用的账号删掉了: True
```

## 没做

- 别的列表（图片、文档、片段、页面）的批量删除是 Wagtail 正常的用法，没动
