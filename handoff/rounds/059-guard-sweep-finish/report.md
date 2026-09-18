# 059 实现报告

## 结论

**完成。** 042 剩下的 178 个守卫跑完：93 个被抓到，**85 个幸存**。85 个全部归类（表在最后）：

| 结论 | 数量 |
|---|---|
| 补测试 | 69 |
| 补测试时发现真 bug，修了 | 1 |
| 代码和设计不一致，改成设计 | 1 |
| 等价（别的检查已经拦住，或只影响提示文字） | 10 |
| 不补（只在真实 SMTP、同一秒两次备份这类情形出现） | 2 |
| 死代码，删掉 | 1 |
| 功能根本没做，另开一轮 | 1 |

加上 042 那 40 个（051 补了 15 个，其余判为等价），**218 个守卫全部跑完、全部有结论**。

## 最要紧的几类

**权限**：战队的改资料、拒绝申请、撤回别人的申请、移除成员、转让队长、超管指定队长；报名的撤回、两级审核里本站越权驳回；车帖改用别人的游戏 ID；后台的战队管理、内战管理、分队页、AI 审核、发送测试邮件——**这些拒绝都没有测试**。原来的后台测试全用超级管理员登录，而超级管理员能通过所有检查。

**安全**：防 SSRF 的三道地址检查；预渲染路径里的 `..`（路径会变成磁盘上的文件名）；预渲染的状态码和内容类型闸门（040 只补了另外两道）；队标上传的大小和类型；生产配置的启动检查；Nonce 长度。

**一处真 bug**：`approve_application` 发现申请人已经是成员时，先把申请标成「已取消」再抛错——但整个函数在事务里，抛错让标记回滚，**这条申请会永远挂在待审批里**。改成事务里标记、提交后再抛错。

**一处和设计不一致**：设计 8.3 第 5 项对停用账号和没有报名权限用同一句「某某暂时无法参加赛事报名」（全站规则：功能被限制时不说原因）。代码单独写了「某某的账号已停用」，**向队长透露了队友被停用**。删掉这个分支——`can_use()` 本来就拒绝停用账号，提示自然回到设计。

**一处功能没做**：`teams.services.disband_blockers()` 永远返回空列表，注释写着「M4 adds the real check」。设计 7.5 要求有有效报名（赛事草稿或已发布，报名待审核、待上游确认或已通过）的战队不能解散。**现在有有效报名的战队也能解散**。这不是补测试能解决的，061 做。

## 几条值得一提的构造

- **防 SSRF**：用字面量公网 IP（`93.184.216.34`），不需要 DNS。042 以为「拒绝 http 下载」那条旧测试盖住了这些检查，其实它是靠网络请求本身失败才通过的
- **开放 API 的上游审核检查**：看起来和状态机里的 `_guard_actor` 重复，但 API 在交给状态机前有「已经是目标状态就直接返回成功」的幂等短路。构造「本站审核的赛事、报名已通过、上游再发通过」，拆掉这道检查会得到 200
- **分队无解**：5 个只能打坦克和支援的人、5 个只能打输出的人，凑 5v5 角色限定。每个位置的人数都够，快速检查放行，但 5 个只能打输出的人抢 4 个输出位——排不出来。拆掉最后那道检查，`random.choice([])` 抛 `IndexError`，管理员看到 500
- **队标**：字段是 `ImageField`，Django 先用 Pillow 打开，打不开的直接拒绝，还会按真实格式重设内容类型。所以测试用真图片：超过 5MB 的真 PNG；真 GIF 起名 `.gif`，和改名成 `.png`（靠真实格式被拦）
- **生产配置**：在子进程里导入设置模块。在当前进程里 `reload` 失败会留下半执行的模块，可能影响别的测试
- **后台权限**：用「内容编辑」（能进后台、但不该碰战队和内战）或「认证作者」（没有审核权限）访问；Wagtail 把后台里的 `PermissionDenied` 变成重定向回后台首页，断言的是这个

## 脚本

`042-guard-sweep/mutate_guards.py` 加了 `--resume`：跳过结果文件里跑过的守卫，**按文件、函数和条件匹配，不按行号**（跑完之后代码会挪行）。042 那 40 个全部对得上。

这轮补测试后的验证用 `mutate_fixed.py`：在工作区里逐个改坏、只跑对应的测试文件、改回。没用 042 的副本方式，因为这轮改了两处业务代码还没提交，副本是从已提交的版本导出的。

## 补完后逐个变异

71 处，**第一轮 69/71**。两处没抓到：

- **建赛时开始或截止时间为空**：我的测试是不传这个字段，但更前面的「必填字段缺失」先拦住了。这道检查真正管的是「传了但不是合法时间」。改成传「下周一」，拆掉后 `None >= 时间` 抛 `TypeError`，返回 500
- **审核时缺名单版本**：拆掉后 `int(None)` 抛 `TypeError`，被捕获后照样是 422，只是提示从「缺少 roster_version」变成「必须是整数」。改成同时断言提示文字——对接上游的开发者看的就是它

改完重跑这两处都被抓到，**71/71**。完整输出在 `mutants-fixed.txt`：

```
✓ 被抓到 teams/services.py:107 update_team  if not is_captain(team, user) and not user.is_superuser  ← ['test_a_member_cannot_edit_the_team']
✓ 被抓到 teams/services.py:211 approve_application  if already_member  ← ['test_approving_someone_already_in_the_team_is_refused']
...
✓ 被抓到 integrations/api_views.py:304 perform_review  if not registration_service.upstream_review_allowed(registration.tournament)  ← ['test_upstream_cannot_review_a_local_tournament_even_idempotently']
...
✓ 被抓到 scrims/teaming.py:295 generate  if not tied  ← ['test_counts_add_up_but_the_roles_do_not_fit']
69/71 被抓到，全部还原
# 补测试后重跑没抓到的两处：
✓ 被抓到 integrations/api_views.py:160 TournamentUpsertView.put  if opens_at is None or closes_at is None  ← ['ERROR    integrations.api:api.py:91 API 内部错误']
✓ 被抓到 integrations/api_views.py:292 perform_review  if roster_version is None  ← ['test_review_needs_the_roster_version']
```

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
233 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python -m pytest -q
813 passed in 53.37s
```

736 → 813，新增 77 条。这次跑的时候后台没有扫描，负载正常，6v6 计时测试也过了。058 那次本地的失败确实是负载造成的，058 推送后 CI 也是绿的。

## 改动文件

```
teams/services.py                      approve_application 的事务；删掉 clean_name
tournaments/registration.py            停用账号的提示回到设计
teams/tests/test_teams.py              权限、重复处理、队长上限、队标上传
tournaments/tests/test_guards.py       新建：撤回、驳回、发布、草稿报名页
integrations/tests/test_api_guards.py  新建：上游审核、参数、404、分页、Nonce
integrations/tests/conftest.py         新建：共享 API 夹具
core/tests/test_security_guards.py     新建：SSRF、预渲染、生产配置
core/tests/test_admin_gates.py         新建：后台入口
lfg/tests/test_lfg.py                  车帖的权限和状态
scrims/tests/test_scrims.py            取消两次、未登录
scrims/tests/test_teaming.py           无解、段位被清空
core/tests/test_fonts.py               点阵字体、空字体
handoff/rounds/042-guard-sweep/mutate_guards.py   --resume
handoff/STATUS.md
handoff/rounds/059-guard-sweep-finish/
```

## 全部 85 个

| 位置 | 函数 | 条件 | 结论 | 说明 |
|---|---|---|---|---|
| `core/fonts/processing.py:79` | `inspect_font` | `fs_type & FSTYPE_BITMAP_ONLY` | 补 | 只允许点阵嵌入的字体 |
| `core/fonts/processing.py:93` | `inspect_font` | `not codepoints` | 补 | 一个字符都没有的字体 |
| `core/health.py:76` | `check_database` | `not HealthProbe.objects.filter(token="__healthz__").exists()` | 等价 | 刚写入就读不到，只有数据库坏了才会发生，而那样前面的写入已经报错 |
| `core/mail.py:240` | `send_test_email` | `not sent` | 不补 | 测试邮件被 SMTP 拒收时的提示；真 SMTP 服务器才会出现，测试里模拟不了有意义的情形 |
| `core/management/commands/backup.py:75` | `Command.handle` | `archive.exists()` | 不补 | 同一秒里备份两次、文件名撞了才会触发 |
| `core/management/commands/restore.py:146` | `Command.handle` | `not snapshot.exists()` | 等价 | 备份包里没有数据库文件：后面复制时照样失败，只是提示不同 |
| `core/net.py:41` | `assert_public_https_url` | `parts.scheme != "https" and not allow_insecure` | 补 | **防 SSRF**。042 以为「拒绝 http 下载」那条测试盖住了它，其实那条测试是靠网络请求失败才通过的 |
| `core/net.py:43` | `assert_public_https_url` | `parts.scheme not in ("https", "http")` | 补 | **防 SSRF**：ftp 等协议 |
| `core/net.py:46` | `assert_public_https_url` | `not host` | 补 | **防 SSRF**：没有主机名的地址 |
| `core/offsite.py:132` | `upload` | `not config.enabled` | 等价 | 调用方 `backup` 命令先判断了开关 |
| `core/offsite.py:154` | `listing` | `config.missing` | 等价 | 缺配置时 boto3 自己报错，只是提示不同 |
| `core/offsite.py:170` | `download` | `config.missing` | 等价 | 同上 |
| `core/prerender.py:54` | `normalize_path` | `not path.startswith("/")` | 补 | **路径安全**：路径会变成 `PRERENDER_ROOT` 下的文件名 |
| `core/prerender.py:56` | `normalize_path` | `"?" in path or "#" in path` | 补 | **路径安全** |
| `core/prerender.py:58` | `normalize_path` | `".." in path or "//" in path` | 补 | **路径安全**：`..` 会跳出预渲染目录 |
| `core/prerender.py:132` | `render_html` | `response.status_code != 200` | 补 | **预渲染闸门**：040 只补了 Cookie 和敏感标记，状态码和内容类型这两道没测 |
| `core/prerender.py:135` | `render_html` | `"text/html" not in content_type` | 补 | **预渲染闸门** |
| `core/views.py:109` | `send_site_test_email` | `not request.user.has_perm("core.change_sitesettings")` | 补 | **权限**：能进后台的人都能用站点 SMTP 发信 |
| `integrations/api.py:168` | `authenticate` | `not (16 <= len(nonce) <= 64)` | 补 | **签名安全**：设计 11.2.3 要求 Nonce 16–64 位，短了重放更容易猜 |
| `integrations/api_views.py:145` | `TournamentUpsertView.put` | `review_mode not in ReviewMode.values` | 补 | 上游推赛事的参数校验 |
| `integrations/api_views.py:160` | `TournamentUpsertView.put` | `opens_at is None or closes_at is None` | 补 | 同上 |
| `integrations/api_views.py:162` | `TournamentUpsertView.put` | `opens_at >= closes_at` | 补 | 同上 |
| `integrations/api_views.py:169` | `TournamentUpsertView.put` | `not (1 <= roster_min <= roster_max <= 20)` | 补 | 同上 |
| `integrations/api_views.py:175` | `TournamentUpsertView.put` | `status_value not in TournamentStatus.values` | 补 | 同上 |
| `integrations/api_views.py:254` | `RegistrationDetailView.get` | `registration is None` | 补 | 不存在或看不到的对象：拆掉后是 500 而不是 404 |
| `integrations/api_views.py:269` | `RegistrationLogsView.get` | `registration is None` | 补 | 不存在或看不到的对象：拆掉后是 500 而不是 404 |
| `integrations/api_views.py:292` | `perform_review` | `roster_version is None` | 补 | 审核必须带名单版本 |
| `integrations/api_views.py:304` | `perform_review` | `not registration_service.upstream_review_allowed(registration.tourname` | 补 | **权限**：看起来和状态机里的检查重复，但 API 有幂等短路，拆掉后上游对本站审核的赛事能拿到 200 |
| `integrations/api_views.py:363` | `RegistrationReviewView.post` | `registration is None` | 补 | 不存在或看不到的对象：拆掉后是 500 而不是 404 |
| `integrations/api_views.py:388` | `RegistrationReviewBatchView.post` | `not isinstance(items, list)` | 补 | 批量审核的参数校验 |
| `integrations/api_views.py:460` | `TournamentRosterView.get` | `tournament is None` | 补 | 同上 |
| `integrations/api_views.py:502` | `TournamentRosterCsvView.get` | `tournament is None` | 补 | 同上 |
| `integrations/api_views.py:563` | `TournamentStatsView.get` | `tournament is None` | 补 | 同上 |
| `integrations/pagination.py:32` | `decode_cursor` | `moment is None` | 补 | 游标、增量同步的时间格式 |
| `integrations/pagination.py:45` | `read_limit` | `limit < 1` | 补 | 分页参数 |
| `integrations/pagination.py:55` | `apply_updated_since` | `moment is None` | 补 | 游标、增量同步的时间格式 |
| `lfg/forms.py:44` | `LfgPostForm.clean` | `not any( cleaned.get(name) for name in ("role_tank", "role_damage", "r` | 等价 | 服务层 `create_post`、`update_post` 也检查，这轮补了服务层的测试 |
| `lfg/services.py:99` | `create_post` | `not allowed` | 补 | **权限**：被禁止发车帖的人。原测试只测了 `can_post()` 的返回值，没测 `create_post` 用了它 |
| `lfg/services.py:103` | `create_post` | `not mode.is_active` | 补 | 停用的游戏模式 |
| `lfg/services.py:127` | `update_post` | `post.status == LfgStatus.CLOSED` | 补 | 已关闭的车帖不能改 |
| `lfg/services.py:129` | `update_post` | `game_account.user_id != user.pk` | 补 | **权限**：改车帖时借用别人的游戏 ID |
| `lfg/services.py:131` | `update_post` | `not any(roles.values())` | 补 | 至少一个位置 |
| `lfg/services.py:156` | `set_status` | `status not in LfgStatus.values` | 补 | 未知状态 |
| `moderation/admin_views.py:39` | `reviewer_required.wrapper` | `not can_review(request.user)` | 补 | **权限**：AI 审核后台 |
| `scrims/services.py:282` | `cancel_scrim` | `scrim.status == ScrimStatus.CANCELLED` | 补 | 取消两次会给报名者再发一次取消邮件 |
| `scrims/split_admin.py:118` | `split_view` | `not services.can_manage(request.user)` | 补 | **权限**：分队页 |
| `scrims/split_admin.py:160` | `copy_view` | `not services.can_manage(request.user)` | 补 | **权限**：分队结果复制页 |
| `scrims/teaming.py:108` | `check_feasible` | `stuck` | 补 | 报名后把段位清空的人 |
| `scrims/teaming.py:295` | `generate` | `not tied` | 补 | 设计 17.4 的「无解」：人数和位置数都够但排不出来。拆掉后 `random.choice([])` 抛 `IndexError`，管理员看到 500 |
| `scrims/views.py:53` | `scrim_signup` | `not request.user.is_authenticated` | 补 | 未登录访问报名、取消报名、我的内战 |
| `scrims/views.py:73` | `scrim_cancel_signup` | `not request.user.is_authenticated` | 补 | 未登录访问报名、取消报名、我的内战 |
| `scrims/views.py:107` | `me_scrims` | `not request.user.is_authenticated` | 补 | 未登录访问报名、取消报名、我的内战 |
| `scrims/wagtail_hooks.py:138` | `manager_required.wrapper` | `not services.can_manage(request.user)` | 补 | **权限**：内战后台的发布、取消 |
| `sjtu_ow/settings/env.py:10` | `env` | `required and default is None` | 补 | 必填环境变量 |
| `sjtu_ow/settings/prod.py:10` | `<module>` | `not ALLOWED_HOSTS` | 补 | **生产配置**：启动检查 |
| `sjtu_ow/settings/prod.py:16` | `<module>` | `not CSRF_TRUSTED_ORIGINS` | 补 | **生产配置** |
| `sjtu_ow/settings/prod.py:23` | `<module>` | `env_bool("WEBHOOK_ALLOW_INSECURE_URLS", False)` | 补 | **生产配置**：生产环境不许放开 Webhook 地址检查 |
| `teams/forms.py:46` | `TeamForm.clean_logo_file` | `uploaded.size > LOGO_MAX_BYTES` | 补 | **上传**：队标大小 |
| `teams/forms.py:50` | `TeamForm.clean_logo_file` | `not name.endswith(LOGO_EXTENSIONS) or ( content_type and content_type ` | 补 | **上传**：队标类型。SVG 这类会先被 `ImageField` 拒掉，这道检查管的是 GIF 等 Pillow 能打开但不允许的格式 |
| `teams/forms.py:71` | `ApplicationForm.clean` | `not any( cleaned.get(name) for name in ("role_tank", "role_damage", "r` | 等价 | 服务层 `apply_to_team` 也检查，已有测试 |
| `teams/services.py:87` | `create_team` | `name_taken(name)` | 等价 | 数据库有部分唯一约束，插入冲突时给出同样的提示 |
| `teams/services.py:107` | `update_team` | `not is_captain(team, user) and not user.is_superuser` | 补 | **权限**：只有队长能改资料 |
| `teams/services.py:111` | `update_team` | `name_taken(name, exclude_pk=team.pk)` | 等价 | 同上 |
| `teams/services.py:187` | `approve_application` | `application.status != ApplicationStatus.PENDING` | 补 | 重复审批 |
| `teams/services.py:191` | `approve_application` | `is_member(team, application.applicant)` | 补+修 | **补测试时发现真 bug**：标记「已取消」后抛错，事务回滚，标记从没生效 |
| `teams/services.py:220` | `reject_application` | `not is_captain(application.team, actor) and not actor.is_superuser` | 补 | **权限**：只有队长能拒绝 |
| `teams/services.py:222` | `reject_application` | `application.status != ApplicationStatus.PENDING` | 补 | 重复处理 |
| `teams/services.py:236` | `cancel_application` | `application.applicant_id != actor.pk` | 补 | **权限**：只能撤回自己的申请 |
| `teams/services.py:238` | `cancel_application` | `application.status != ApplicationStatus.PENDING` | 补 | 重复处理 |
| `teams/services.py:248` | `leave_team` | `membership is None` | 补 | 不是成员 |
| `teams/services.py:257` | `remove_member` | `not is_captain(team, actor) and not actor.is_superuser` | 补 | **权限**：只有队长能移除成员 |
| `teams/services.py:262` | `remove_member` | `membership is None` | 补 | 不是成员 |
| `teams/services.py:274` | `transfer_captain` | `not is_captain(team, actor) and not actor.is_superuser` | 补 | **权限**：只有队长能转让 |
| `teams/services.py:279` | `transfer_captain` | `target.is_captain` | 补 | 转给自己 |
| `teams/services.py:281` | `transfer_captain` | `captained_count(new_captain) >= max_captained()` | 补 | 接手的人已到队长上限（039 以为「找不到代码」的那条，其实在这里没测） |
| `teams/services.py:301` | `assign_captain` | `not actor.is_superuser` | 补 | **权限**：只有超管能指定队长 |
| `teams/services.py:325` | `disband_team` | `blockers` | 见 061 | **功能没做**：`disband_blockers()` 永远返回空列表，注释写着「M4 adds the real check」。设计 7.5 要求有有效报名的战队不能解散 |
| `teams/services.py:440` | `clean_name` | `len(name) < 2 or len(name) > 16` | 删 | 死代码：没有任何地方调用，表单自己有长度校验 |
| `teams/wagtail_hooks.py:102` | `superuser_required.wrapper` | `not request.user.is_superuser` | 补 | **权限**：战队后台的指定队长、解散 |
| `tournaments/registration.py:55` | `member_problems` | `not user.is_active` | 改 | **和设计不一致**：设计 8.3 第 5 项对停用和无权限用同一句「暂时无法参加赛事报名」，代码却单独写「账号已停用」，向队长透露了队友被停用。删掉这个分支，`can_use` 本来就拒绝停用账号 |
| `tournaments/registration.py:134` | `_resolve_accounts` | `account is None` | 等价 | 队员一个游戏 ID 都没有：「资料不完整：缺少游戏 ID」先拦住了 |
| `tournaments/registration.py:362` | `withdraw` | `not is_team_captain(registration.team, actor)` | 补 | **权限**：只有队长能撤回 |
| `tournaments/registration.py:448` | `reject` | `registration.status == RegistrationStatus.AWAITING_UPSTREAM and actor_` | 补 | **权限**：两级审核里等上游确认的，本站管理员不能驳回（设计 8.5） |
| `tournaments/registration_views.py:33` | `register` | `not tournament.is_public` | 补 | 草稿赛事的报名页是 404 |
| `tournaments/services.py:142` | `publish` | `tournament.status == TournamentStatus.CANCELLED` | 补 | 已取消的赛事不能再发布 |
