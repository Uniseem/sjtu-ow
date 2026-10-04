# 181 守卫普查补上「软拒绝」（报告）

## 做了什么

1. `mutate_guards.py` 从 179 复制到本轮目录，多认一种「软拒绝」：`if` 的直接内容里有 `messages.error` / `messages.warning`，或者调了 `add_error`。不要求后面紧跟 `return`：很多视图写的是 `if 超限: messages.error(...)`，真正的动作在后面的 `elif form.is_valid()` 里。`--soft` 只跑这一种（042、179 认得的那种不重跑）
2. 用 `remote-check.sh run` 在测试机上跑（3 个并行，副本放在 `/srv/sjtu-ow-check/soft-copies`，跑完删了）。结果原样存在 `results.jsonl`，过程在 `sweep-log.txt`
3. 列出 26 处：15 处被抓到，11 处没有。9 处补了测试（其中一条是把原来测错了的改准），2 处有另一层兜着
4. 补的 9 处写进 `mutate.py`，在测试机上逐个改坏，全部被抓到
5. STATUS 里那条「042 脚本认不出 `messages.error` + `redirect` 式的拒绝，要手动补验」改成指向本轮；AGENTS.md 硬规则 7 指向本轮的脚本

只加测试，网站代码没改。

## 补了测试的 9 处

| 守卫 | 改坏的后果 | 测试 |
|---|---|---|
| `moderation/admin_views.py:172` 不认识的处理方式 | 提交一个不在列表里的 `action` 是 500（`ACTIONS[action]` 的 KeyError） | `core/tests/test_soft_guards.py::test_an_unknown_handling_is_refused_not_a_crash`（内容编辑） |
| `core/fonts/admin_views.py:318` 字重没有可下载的文件 | 下载到一个空的 zip | `…::test_a_weight_with_nothing_to_download` |
| `teams/views.py:106` 每天最多建 3 支战队 | 不限次数。原来的 `test_create_is_rate_limited` 第 4 次是被「最多当 3 支队的队长」挡下的，每日限制本身从没碰到过；改成先把队长上限调到 5 再测 | `teams/tests/test_teams.py::test_create_is_rate_limited` |
| `teams/views.py:160` 每天最多 20 次入队申请 | 不限次数 | `…::test_applications_are_rate_limited` |
| `teams/views.py:146` 重名的提示放在「队名」一栏 | 变成表单顶上的一句，队名框不标红 | `…::test_a_taken_name_is_marked_on_the_name_field` |
| `moderation/admin_views.py:212` AI 审核关闭时不发起全量扫描 | 关着也排上一个扫描任务 | `core/tests/test_soft_guards.py::test_no_full_scan_while_moderation_is_off`（内容编辑） |
| `core/prerender_admin.py:65` 预渲染关闭时说明 | 关着也提示「已排入队列」 | `…::test_rebuilding_says_so_while_prerendering_is_off` |
| `accounts/views.py:181` 游戏 ID 满了不给「添加」表单 | 打开 `?new=1` 照样给表单，填完提交才被拒 | `…::test_the_add_form_is_not_offered_at_the_limit` |
| `tournaments/wagtail_hooks.py:149` 保存后提醒「下限大于战队人数上限」 | 表单只在改了下限或报名方式时检查；之后站长调低了战队人数上限，再编辑赛事（比如只改标题）时这条提醒没了 | `…::test_editing_a_tournament_the_teams_outgrew_warns`（赛事管理员，不是超级管理员） |

## 有另一层兜着的 2 处

| 守卫 | 理由 |
|---|---|
| `accounts/views.py:159` 提交时游戏 ID 已满 | `accounts/services.add_game_account`（126 行）查同一件事、同样的话，视图把 `ValidationError` 放回表单 |
| `teams/views.py:158` 提交申请时 `can_apply` 不通过 | `teams/services.apply_to_team` 先调 `can_apply`，不通过抛 `TeamError`，视图同样用 `messages.error` 显示原因 |

## 命令输出

普查（测试机，`sweep-log.txt` 开头）：

```
基线（并行负载下，未变异）：
  w0: exit=0 1690 passed, 2 deselected in 178.53s (0:02:58) []
  w1: exit=0 1690 passed, 2 deselected in 175.83s (0:02:55) []
  w2: exit=0 1690 passed, 2 deselected in 179.39s (0:02:59) []
[1/26] ✓ accounts/admin_users.py:41 SiteUserEditForm.clean  if stopping and not (cleaned.get("deactivation_note") or "").st
[2/26] ✓ accounts/admin_users.py:72 UserEditView.save_instance  if teams
```

26 处里本应用的测试抓到 7 处、全量测试抓到 8 处、没抓到 11 处；每处的耗时加起来 50.4 分钟。

变异（测试机，9 处，全部被抓到）：

```
baseline green, 9 tests
caught add form offered at the limit -> test_the_add_form_is_not_offered_at_the_limit
caught empty zip downloaded -> test_a_weight_with_nothing_to_download
caught rebuild queued while off -> test_rebuilding_says_so_while_prerendering_is_off
caught unknown handling accepted -> test_an_unknown_handling_is_refused_not_a_crash
caught scan while moderation off -> test_no_full_scan_while_moderation_is_off
caught teams created without limit -> test_create_is_rate_limited
caught taken name as a toast -> test_a_taken_name_is_marked_on_the_name_field
caught applications without limit -> test_applications_are_rate_limited
caught outgrown tournament saved quietly -> test_editing_a_tournament_the_teams_outgrew_warns
restored and green; missed: none
```

整组检查（测试机）：

```
== pytest (08:20:14)
1700 条测试分成 4 片
分片 1：425 passed in 48.12s
分片 2：425 passed in 41.97s
分片 3：425 passed in 43.32s
分片 4：425 passed in 38.04s
== 迁移 (08:21:06)
No changes detected
== 生产配置 (08:21:07)
System check identified no issues (0 silenced).
== 错误页和模板一致 (08:21:08)
== Docker 镜像 (08:21:09)
构建成功：a99be2ddeac5
== 全部通过 (08:21:09)
```

## 没做

- 软拒绝只认 `messages.error` / `warning` 和 `add_error`。返回一个带错误提示的 HTMX 片段（200）、或者模板里按条件不显示按钮的，还是认不出
- 模板里的条件和查询里的过滤仍然不在普查里（179 报告也写了），靠每轮自己的变异
