# 185 页头账号菜单里加「管理后台」（报告）

## 做了什么

1. `core/templatetags/ow.runs_admin`：登录了、能进后台（`wagtailadmin.access_admin`），而且不是只投稿的人（`content.permissions.is_submitter_only` 为假）
2. `templates/components/account_area.html`：这样的人菜单最上面「管理后台」（链到后台首页），下面一条分隔线
3. `templates/slots/footer_account.html`：页脚「账号」一栏最前面同样一项
4. 设计 13.2.6、13.3、13.13.3（v6.64）
5. `core/tests/test_admin_link.py`（3 条）

第一版按「能进后台」判断，普通成员的测试就红了：验证过邮箱的成员会被自动放进投稿者组，投稿者能进后台写稿，于是人人都有这一项。改成排除只投稿的人（他们有页脚的「我要投稿」）。

## 命令输出

测试机仍然连不上（本机 IPv6 不通），在本机跑。

变异（本机，5 处，全部被抓到）：

```
caught no link in the menu -> test_the_site_owner_is_shown_the_way_in
caught no link in the menu -> test_so_is_a_content_editor
caught no link in the footer -> test_the_site_owner_is_shown_the_way_in
caught no link in the footer -> test_so_is_a_content_editor
caught submitters get it too -> test_members_and_visitors_are_not
caught everyone signed in gets it -> test_members_and_visitors_are_not
caught nobody gets it -> test_the_site_owner_is_shown_the_way_in
caught nobody gets it -> test_so_is_a_content_editor
restored and green; missed: none
```

整组检查（本机）：

```
All checks passed!
354 files already formatted
Built production stylesheet 'D:\\claude\\sjtu-ow\\static\\css\\app.css'.
FAILED scrims/tests/test_teaming.py::test_6v6_finishes_within_a_second - Asse...
1 failed, 1707 passed, 1 skipped in 271.07s (0:04:31)
No changes detected
System check identified no issues (0 silenced).
```

红的那条是 AGENTS.md 记着的计时测试（6v6 分队 1 秒内，机器忙时偶发）。单独重跑：

```
1 passed in 0.80s
```

`docker build` 本机没跑，看 CI。

正式站升级（`deploy_ship.sh 185`，全量生成成功 9、失败 0）后，在服务器上用 `RequestFactory` 拿超级管理员渲染这两块（不建会话）：

```
components/account_area.html [('/admin/', '管理后台'), ('/me/', '个人中心'), ('/me/registrations/', '我的报名'), ('/me/teams/', '我的战队'), ('/accounts/logout/', '退出')]
slots/footer_account.html [('/admin/', '管理后台'), ('/me/', '个人中心'), ('/me/registrations/', '我的报名'), ('/me/teams/', '我的战队')]
```

## 没做

- 后台角色登录后仍然先回到前台（和成员一样），不自动进后台：内容编辑、赛事管理员平时也在前台看评论、报名
- 手机上的导航抽屉没有账号菜单以外的入口，「管理后台」只在账号菜单和页脚
