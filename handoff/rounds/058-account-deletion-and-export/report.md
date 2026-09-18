# 058 实现报告

## 结论

**完成。** 按设计新增的 3.8 节，个人中心「账号安全」页有了「导出我的个人信息」和「注销账号」。用户对上线前待定项的四个决定写进了设计 19.2 和 `STATUS.md`。

## 用户的决定（2026-09-18）

| 事项 | 决定 | 设计 |
|---|---|---|
| 账号注销和导出 | 按设计建议做 | 19.2 第 6 条结案，细节写成 3.8 节 |
| 后台两步验证 | 上线先不做 | 19.2 第 3 条结案 |
| 用户协议和隐私政策 | 助手起草，社团改 | 060 轮 |
| 「高风险内容暂缓公开」开关 | 上线前不做 | 19.2 第 12 条结案 |

顺带把 19.2 第 4 条（投稿初始分类）标为「已按建议实现」——043 核对过。

## 设计 3.8

19.2 原来只有一句建议，新增 3.8 节写清楚：导出包含什么、不包含什么（密码、别人的信息、后台记录）；注销改什么（邮箱、昵称、是否交大、密码、停用）、删什么（游戏 ID、联系方式、内战报名、用户组、功能规则、审核记录里的昵称快照）、留什么（赛事名单快照和日志、署名文章）；队长要先转让或解散。路由表加 `/me/export/`、`/me/delete/`。附录 D 记 v1.5.13。

## 实现

- `accounts.services.personal_data(user)`：导出的 JSON。只取这个人自己的数据
- `accounts.services.delete_account(user)`：一个事务里按 3.8 做完
- `teams.services.leave_all_teams(user)`、`scrims.services.remove_signups_of(user)`：各应用自己的那部分
- `/me/export/`：每人每小时 5 次，超了回到账号安全页提示
- `/me/delete/`：要当前密码；队长直接看到原因，没有表单；注销后登出并回到首页

**顺序有讲究**：
1. 先删内战报名，再删游戏 ID——`ScrimSignup.game_account` 是 `PROTECT`
2. 保存用户**之后**再清用户组——保存时的信号会按「是否交大」把人放回「交大用户」或「校外用户」组
3. 保存之后再删审核记录里的昵称——保存会把新昵称「已注销用户」再送检一次

改昵称会触发 057 的页面刷新，所在战队页、内战页、署名文章会重新生成。

## 测试

`accounts/tests/test_account_deletion.py`，13 条。构造一个「队员、在已提交的赛事名单里、报了内战且已勾选上场、有待审批的入队申请、在自定义用户组里、有功能规则和邮箱验证记录」的用户，注销后逐项检查；队长被拒；密码错被拒；原邮箱能重新注册；另一台设备的登录失效；导出有自己的数据、没有队长的联系方式、没有密码；导出限流。

## 变异

21 处逐个改坏，**21/21 被抓到**（`mutants.txt`）。其中两处是第一轮没抓到、补测试后才抓到的：

- **「注销后不调用 `logout`」**：账号停用本身就让登录失效，页面行为不变，第一轮没抓到。补了「会话里不再有用户 ID」的断言
- **「不删审核记录里的昵称」**：这一步是写复核时想到才加的，加的时候一起补了测试

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
228 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python -m pytest -q
FAILED scrims/tests/test_teaming.py::test_6v6_finishes_within_a_second - Asse...
1 failed, 735 passed in 214.07s (0:03:34)
```

**唯一的失败是 6v6 分队必须 1 秒内完成的计时测试**，跑的时候后台有 059 的变异扫描（5 个并行副本），机器负载：

```
load averages: 28.79 29.06 27.69
```

单独重跑这一条也是 3.67 秒失败。本轮没有改分队代码（`scrims/teaming.py` 没动）。以推送后 CI 的结果为准，记在下一轮。

## 改动文件

```
docs/design.md                                 3.8；路由表；19.2 第 3、4、6、12 条；附录 D
accounts/services.py                           personal_data、delete_account、deletion_blockers
accounts/views.py、accounts/forms.py、accounts/urls.py
teams/services.py                              leave_all_teams
scrims/services.py                             remove_signups_of
templates/me/security.html、templates/me/delete.html
accounts/tests/test_account_deletion.py        新建，13 条
README.md                                      注销与导出一节
handoff/STATUS.md
handoff/rounds/058-account-deletion-and-export/
```
