# 184 服务器上建的超级管理员不用收验证码就能登录（报告）

## 做了什么

0. 当场解开：正式站上只有用户刚建的一个账号（`ow4sjtu@126.com`，超级管理员），邮箱记录是登录时 allauth 建的、未验证。在服务器上把它改成已验证、主邮箱：

```
1 ow4sjtu@126.com superuser active [('ow4sjtu@126.com', False, False)]
users 1
→ [('ow4sjtu@126.com', True, True)]
```

之后用户登录成功（`last_login 2026-10-04 11:24:13`）。

1. `accounts/services.trust_email(user)`：把账号当前的邮箱记成已验证、主邮箱（没有记录就建一条，别的邮箱取消主邮箱），再同步投稿者组。不发邮件
2. `accounts/management/commands/createsuperuser.py`：继承 Django 自带的命令，建完后对**这次新建的**超级管理员调 `trust_email`，打印一句「已记为验证过的邮箱，可以直接登录后台」。`accounts` 在 `INSTALLED_APPS` 里排在 `django.contrib.auth` 前面，所以覆盖自带的
3. `accounts/management/commands/verify_email.py`：`verify_email <邮箱>`，找不到账号报错
4. 设计 3.1（v6.63）；README「生产 / 测试环境启动」；`init_site` 跑完的提示；AGENTS.md「第二台」登录后台那行
5. `accounts/tests/test_superuser_email.py`（6 条）

## 为什么 182、183 没发现

182 在测试机上演练转正式站，只检查了页面和数据，没有真的建管理员、登录；183 把 `createsuperuser` 留给用户（密码要用户自己输），也没有走到登录这一步。测试里的超级管理员都用 `create_superuser` 加 `force_login`，不经过登录表单和邮箱验证。

## 命令输出

测试机连不上（本机 IPv6 不通：`ssh: connect to host 2a0e:6a80:3:9c7:: port 22: Network is unreachable`），照 AGENTS.md 在本机跑。

变异（本机）。第一次漏了一处：测试里的账号没有自己邮箱的记录，走的是新建那条路，「已有未验证的记录」这条路（正是用户遇到的情况）没测到。测试改成先放一条 allauth 留下的未验证记录，再跑：

```
baseline green, 5 tests
caught created superuser not trusted -> test_the_command_records_the_email_as_verified
caught created superuser not trusted -> test_that_superuser_signs_in_without_a_code
caught every superuser trusted -> test_superusers_already_there_are_left_alone
caught address left unverified -> test_the_command_records_the_email_as_verified
caught address left unverified -> test_that_superuser_signs_in_without_a_code
caught existing address not verified -> test_verify_email_lets_a_stuck_account_in
caught old primary kept -> test_verify_email_lets_a_stuck_account_in
caught unknown address passes -> test_verify_email_names_an_unknown_address
restored and green; missed: none
```

整组检查（本机，和 CI 同一组命令；`docker build` 本机没跑，未验证，看 CI）：

```
All checks passed!
353 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
1705 passed, 1 skipped in 294.30s (0:04:54)
No changes detected
System check identified no issues (0 silenced).
```

正式站升级（`deploy_ship.sh 184`，全量生成成功 9、失败 0）后：

```
createsuperuser from accounts accounts.management.commands.createsuperuser
verify_email from accounts
ow4sjtu@126.com True [(True, True)] last_login 2026-10-04 11:24:13.441522+00:00
CommandError: 没有用 nobody@example.invalid 注册的账号。
```

健康检查仍然是磁盘那一项不过（183 报告），其余正常。

## 没做

- 后台没有「把某人的邮箱标成已验证」的按钮，只有服务器上的命令。管理员能在后台改别人的邮箱，再给一个「不用验证」的按钮等于绕过邮箱验证，先不加
