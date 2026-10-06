# 213 实现报告

## 结论

完成。210 复核建议顺序第 2 步的八条权限和状态守卫（S1、S7、S2、S3、T2、A8、A9、B3）全部修好；210 守卫普查的 34 个 survived 逐条判断完：7 处真缺口补了测试（补完再变异确认会被抓到）、25 处有等价的第二道兜底（其中 3 处实测复核）、1 处不可达的防御分支、1 处已由本轮 B3 覆盖。新增 22 条测试全绿；本地全量 1952 条全绿；测试机整组检查 1953 条全绿。T7（赛事取消后还能审核）是设计空白，和设计文档一起等用户拍板，不在本轮。

## 逐条结果

1. **S1（被禁言/关评论还能编辑旧评论、编辑不限流）**：`comments/services.py` 的 `edit` 开头加 `can_comment(actor, comment.page)` 检查，和发表同一套限制；`comments/views.py` 的编辑视图加 `_too_many` 限流（「编辑太频繁了，稍后再试」），编辑和发表共用 `comment:m:`/`comment:d:` 计数。设计 5.6 同步（v7.16）。
2. **S7（作者能删已被隐藏的评论）**：`comments/services.py` 的 `delete` 拦 `is_hidden`（「这条评论已经不能删除了」）。设计 5.6 同步。
3. **S2（改能打的位置不清分队）**：`scrims/services.py` 的 `sign_up` 加 `changed_roles`：roles 有变化时和换游戏 ID 一样清掉 placement、标 `_mark_teams_changed`；`was_placed` 改成 `(signup.is_selected or bool(signup.team))`，缓冲区（selected 但没分队）的人被改动也会标记。设计 9.2 同步。
4. **S3（已结束/已取消的内战还能发布、任意状态都能标记结束）**：`publish` 拦 CANCELLED/FINISHED/非 DRAFT，`finish` 要求 PUBLISHED（「只有已发布的内战可以标记为已结束。」）。查过所有现存调用点传的都是 DRAFT；`tasks.py` 的 `finish_past_scrim` 自己先过滤 PUBLISHED，不受影响。设计 9.1 同步（「状态只能往前走」）。
5. **T2（停用成员还能被转让队长）**：`teams/services.py` 的 `transfer_captain` 拦 `is_active` 为假的账号；`teams/manage.html` 的转让按钮只对启用中的成员显示。设计 7.4 同步。
6. **A8（已注销账号能被重新启用、启用后停用原因还挂着）**：`accounts/services.py` 新增 `AccountError`、`is_deleted()`、`deactivate_account()`、`reactivate_account()`——注销过的（邮箱 `@deleted.invalid` 结尾）抛错不能启用，正常启用时清掉 `deactivation_note`；`backoffice/views/members.py` 的 `user_active` 改走 service，编辑页对注销账号显示「账号已注销：数据已匿名化，不能再启用。」不显示按钮。设计 3.7 同步。
7. **A9（注销不清超管标记）**：`delete_account` 加 `user.is_superuser = False`。设计 3.8 同步。
8. **A12（连带查）**：停用时暂停招募的返回值 `paused` 传进 `_after_deactivation` 的新签名，提示语照旧。
9. **B3（投稿者能改/删别人的投稿配图）**：210 普查快照里的 `images.py:153/198` 两处，本轮以 `backoffice/tests/test_image_guards.py` 补上：投稿者 B 对 A 的图 GET/POST 编辑、POST 删除全 403 且图没动，A 自己的 200。代码本身没问题（Wagtail 集合权限拦着），缺的是钉住它的测试。
10. **测试**（新增 22 条，全绿）：`comments/tests/test_comment_extras.py` +4、`scrims/tests/test_scrims.py` +5、`teams/tests/test_teams.py` +1、`teams/tests/test_stopped_members.py` +1、`accounts/tests/test_account_deletion.py` +1、`backoffice/tests/test_backoffice.py` +2（另 +3 普查补测）、`backoffice/tests/test_image_guards.py` 新建 1 条，普查补测见下。
11. **变异验证**：`mutate.py` 14 处全部被抓到，基线前后全绿（输出见下）。

## 普查 34 个 survived 的逐条判断

210 普查（`rounds/210-full-review/results.jsonl`）的变异方式是把守卫条件换成 `False`。34 个没被抓到的，逐条读代码和测试后的结论：

**真缺口，本轮补测（7 处，补完逐一变异确认新测试会红，`verify_census.sh`）**：

| 位置 | 判断 |
|---|---|
| `backoffice/views/articles.py:260` | 没投稿权限的职员（未验证邮箱的赛事管理员：能进后台但没有资讯栏目的 add_page）POST 写文章会被拦——拆掉就直接 `add_child` 建站，是真守卫。补 `test_a_manager_without_submission_cannot_write_articles` |
| `backoffice/views/articles.py:258` | 资讯栏目被删后写文章给 404，拆掉变 500。补 `test_article_new_without_an_index_is_404` |
| `backoffice/views/images.py:250` | 选择器传坏文件回 400 JSON，拆掉变 500。补 `test_the_chooser_reports_a_bad_file_instead_of_crashing` |
| `core/held_views.py:111` | 未登录看信件预览是 404，拆掉后 `actor=AnonymousUser` 查询抛 TypeError 变 500。补 `test_the_preview_is_404_for_anonymous` |
| `core/announce_admin.py:23` | 没注册的通知类型是 404，拆掉变 AttributeError 500。补 `test_an_unknown_kind_is_404` |
| `backoffice/nav.py:235` | 写错大类名的程序员错误立即报 ValueError。补 `test_a_section_that_does_not_exist_is_caught_when_the_page_is_placed` |
| `tournaments/services.py:232` | 没填好的草稿取消会公开露出空白字段，服务层拦（「还没填好的草稿不用取消，直接删除。」）——没有第二道。补 `test_a_half_filled_draft_is_deleted_not_cancelled` |

**有等价的第二道兜底，行为不变（25 处），注明不补**：

- `accounts/forms.py:189`、`accounts/models.py:255`（游戏 ID 撞车）：数据库有大小写不敏感唯一约束且 `violation_error_message` 就是同一句文案，`full_clean` 的 `validate_unique` 会抛同样的 ValidationError；表单视图又 catch ValidationError 回填表单。本轮实测：两处分别变异后跑测试照常绿、手动复现撞车仍抛同文案。本轮另补了一条端到端行为测试 `test_a_taken_battletag_is_a_form_error_not_a_crash`（钉住「撞车是页面上的一句文案」这个结果，不管哪一层拦的）。
- `backoffice/nav.py:245`（wrapper 里的 `can_enter`）：所有页签的 `allowed` 都含 `can_enter`（`writes_articles` 就是它本身，其余是 `can_enter and …`），拆掉后页签门口照拦；`test_door.py` 用四个非超管角色扫全部后台地址钉着门口。
- 各应用的权限装饰器（`moderation/admin_views.py:53`、`scrims/admin_views.py:28`、`scrims/split_admin.py:187/239`、`teams/admin_views.py:25`、`tournaments/admin_views.py:28`、`tournaments/review_admin.py:35`、`core/fonts/admin_views.py:42`、`core/activity.py:254`、`core/admin_manual.py:229`、`core/views.py:107/124`）：所有视图经 `_at` = `placed(...)` 注册，页签进门函数就是同一个检查（`reviews_content = can_enter and can_review` 等），装饰器是纵深防御的第二层，拆掉不可观测。
- `backoffice/views/articles.py:292`（编辑页按发布无权限）：`_submit` 里还有一道——不发布、只警告「草稿已保存；你不能发布这篇文章。」，安全结果一样。
- `backoffice/views/articles.py:311/322`（撤下/删除）：Wagtail 的 `UnpublishPageAction`/`DeletePageAction` 内部再查权限（源码确认 `check()` 抛 PermissionDenied），同样 403。
- `backoffice/views/pages.py:92`（`page_edit` 的 `can_edit`）：页签进门 `edits_site_pages` = 内容编辑/超管，而内容编辑对首页子树有 change_page——进门集合 ≡ 可编辑集合，实际不可达，防御性保留。
- `backoffice/views/images.py:117`（没有可上传集合）：拆掉后表单必填校验兜底（POST 无效、GET 渲染空下拉），无洞。
- `backoffice/views/images.py:247`（选择器没选文件）：`_upload_one` 对空文件返回错误，由 `:250` 接住，同样 400。
- `teams/forms.py:101`（申请至少选一个位置）：service 层 `apply_to_team` 用同一句文案再拦。本轮实测：变异后 `test_the_apply_page_says_it_once` 照常绿。
- `teams/services.py:137/172`（队名查重）：数据库有条件唯一约束 `unique_active_team_name`，service 把 IntegrityError 转成 TeamError（`test_duplicate_name_race_is_reported_not_crashed` 已钉住）。

**不可达的防御分支（1 处）**：

- `accounts/ranks.py:48`：前面已拦 `score < 0 or score > 39`，`divmod(score, 5)` 的 `tier_index` 恒在 0–7，必在 `INDEX_TIER` 里。防御性保留。

**本轮已修（1 处）**：`backoffice/views/images.py:153/198` 即 B3。

## 验收输出

本地：`uv run ruff check . && uv run ruff format --check .` 全过；`uv run pytest -q` 全量 `1952 passed, 1 skipped in 141.77s`。

变异验证（`uv run python handoff/rounds/213-permission-state-guards/mutate.py`，2026-10-06 本机）：

```
基线全绿，开始变异。
ok S1: edit 不查 can_comment：改坏后红了（2 条）
ok S1: edit 视图不限流：改坏后红了（1 条）
ok S7: 作者能删被隐藏的评论：改坏后红了（1 条）
ok S2: 改位置不清分队、不标记：改坏后红了（1 条）
ok S2: 缓冲区的人被清掉不标记：改坏后红了（1 条）
ok S3: publish 不拦已结束/已发布：改坏后红了（1 条）
ok S3: finish 不看状态：改坏后红了（1 条）
ok T2: 转让队长不拦停用账号：改坏后红了（1 条）
ok T2: 管理页对停用成员仍显示「转让队长」：改坏后红了（1 条）
ok A8: 启用不看清没注销：改坏后红了（1 条）
ok A8: 启用不清停用原因：改坏后红了（1 条）
ok A9: 注销不清 is_superuser：改坏后红了（1 条）
ok B3: 图片按张改守卫：改坏后红了（1 条）
ok B3: 图片按张删守卫：改坏后红了（1 条）
改回后基线全绿。
```

普查补测的变异验证（`bash handoff/rounds/213-permission-state-guards/verify_census.sh`，逐处改坏跑对应新测试）：

```
ok 抓到 backoffice/views/articles.py（can_add_subpage）
ok 抓到 backoffice/views/articles.py（parent is None）
ok 抓到 backoffice/views/images.py（error）
ok 抓到 core/held_views.py（未登录）
ok 抓到 core/announce_admin.py（entry is None）
ok 抓到 backoffice/nav.py（section）
ok 抓到 tournaments/services.py（没填好的草稿）
```

（`accounts/forms.py:189` 一处变异后测试仍绿，追查确认是等价兜底，见上表；补的测试钉的是端到端行为。）

测试机整组检查（`bash scripts/remote-check.sh`，服务器时间 2026-10-06 21:10–21:11）：

```
== ruff (13:10:28)
All checks passed!
405 files already formatted
== Tailwind (13:10:28)
Built production stylesheet '/srv/sjtu-ow-check/repo/static/css/app.css'.
== pytest (13:10:30)
1953 条测试分成 4 片
分片 1：489 passed in 70.53s (0:01:10)
分片 2：488 passed in 64.06s (0:01:04)
分片 3：488 passed in 65.15s (0:01:05)
分片 4：488 passed in 58.39s
== 迁移 (13:11:46)
No changes detected
== 生产配置 (13:11:48)
System check identified no issues (0 silenced).
== 错误页和模板一致 (13:11:49)
== Docker 镜像 (13:11:50)
构建成功：24e6655b9337
== 全部通过 (13:11:50)
```

正式站升级：见提交后的 STATUS 更新（本节在部署后补记）。

## 设计偏差

无。文档先改（design.md v7.16：5.6 评论编辑同发表限、隐藏的不能删；9.1 内战状态只能往前走；9.2 改位置清分队；3.7 启用清原因、注销不能启用；3.8 注销清超管；7.4 不能转给停用成员；附录 D 记版本），实现照文档。

## 顺带发现（留给后面轮次）

- **赛事的 `publish` 有和 S3 同形的洞（一半）**：`tournaments/services.py` 的 `publish` 只拦 CANCELLED，已结束的赛事还能被重新发布回 PUBLISHED；`finish` 是好的（已经要求 PUBLISHED）。213 只照复核清单修了内战；赛事那边建议下一轮照抄（连同「状态只能往前走」写进设计 8 章）。
- **普查的等价兜底集中在两类**：唯一约束 + `violation_error_message`（游戏 ID、队名）和 `placed` 页签门口（各权限装饰器）。以后删「冗余」检查前先想这两类。
- 本轮没有 JS 改动，无新增弱测试。
