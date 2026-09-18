# 056 实现报告

## 结论

**完成。** 首页的「正在报名的赛事」「近期内战」接上了真实数据，战队主页有了参赛记录，设计 13.13.4 事件表里和它们相关的重新生成全部补上。做的过程中又发现**内战后台的三个状态按钮都不刷新页面**，一并修了。测试机上已生效。

## 发现了什么

| 位置 | 原来 |
|---|---|
| `HomePage.get_context` | `context["open_tournaments"] = None`、`context["upcoming_scrims"] = None`，注释「M4 / M6 data hooks: leave keys in context so templates stay put」 |
| `home_page.html` | `{# M4: iterate open_tournaments here. Layout stays. #}`；空状态「即将开放——赛事报名将在后续里程碑接入」；页首「赛事与内战功能正在建设中」 |
| `teams/detail.html` | 参赛记录：「即将开放——赛事报名将在后续里程碑接入」 |
| 赛事变化 | 刷新详情和列表，**不刷新首页** |
| 报名审核通过、撤销 | **什么都不刷新**（设计要求刷新赛事详情和战队主页） |
| 内战变化 | 刷新详情和列表，**不刷新首页** |
| 内战的「发布」「标记结束」「取消」按钮 | **什么都不刷新**。只有编辑表单保存才调用 `after_change`；赛事那边三个按钮都调用了 |

M2 做首页时给 M4、M6 留了接口和注释，M4、M6 做完时没人回来接。一路下来每轮的测试都是绿的，因为首页的测试**断言的就是「即将开放」这四个字**（`test_home_uses_pinned_articles_when_present`）——占位状态被写成了预期。

## 改动

**首页**（设计 5.1、附录 C）：
- `tournaments.services.open_tournaments()`：已发布、当前在报名期内，截止早的在前
- `scrims.services.upcoming_scrims()`：已发布、未来 7 天内开始，早的在前。7 天写成 `HOME_SCRIM_DAYS`
- 每项有标题链接和时间；空的时候写「现在没有正在报名的赛事」「未来 7 天没有内战」；底下有「全部赛事」「全部内战」链接
- 删掉「赛事与内战功能正在建设中」

**战队主页参赛记录**（设计 7.2）：`tournaments.services.team_entries(team)`，这支队状态为「已通过」的报名，不含草稿赛事；已结束、已取消的赛事带标签。

**重新生成**（设计 13.13.4）：

| 事件 | 补上的 |
|---|---|
| 赛事创建、修改、发布、取消、结束 | 首页 |
| 报名开始、截止的时间点 | 首页（原来只排了详情和列表） |
| 报名变为已通过，或从已通过变走（审核、撤销、同步名单） | 赛事详情、战队主页 |
| 内战创建、修改、发布、取消 | 首页 |
| 内战进入 7 天范围、开始的时间点 | 首页 |
| 内战后台的发布、结束、取消按钮 | 详情、列表、首页 |

报名那条放在 `_set_status` 和 `submit` 里（事务内），只有「已通过」出现在变化前后之一时才刷新。

## 测试

`tournaments/tests/test_public_pages.py`（11 条）、`scrims/tests/test_home_listing.py`（8 条）：

- 首页：报名中的出现；未开始、已截止、草稿、已取消的不出现；排序；空状态
- 首页内战：2 天后、6.9 天后的出现；7.1 天后、已开始、草稿、已取消的不出现；排序；空状态
- 参赛记录：只有已通过的；草稿赛事不出现
- 每个触发各一条；另有一条确认「不涉及已通过」的状态变化**不**刷新战队页

`test_state_table.py` 里构造报名的夹具通过 `tournaments/tests/conftest.py` 共享。

旧测试 `test_home_uses_pinned_articles_when_present` 原来断言「即将开放」，改成断言新的空状态。

## 变异

25 处逐个改坏，**25/25 被抓到**（原始输出在 `mutants.txt`）：

```
✓ 被抓到 首页不取赛事 | 1 failed, 18 passed in 6.08s ['test_the_homepage_lists_tournaments_open_for_registration']
✓ 被抓到 首页不取内战 | 1 failed, 18 passed in 6.09s ['test_the_homepage_lists_the_next_seven_days']
...
✓ 被抓到 报名刷新不看是否涉及已通过 | 1 failed, 18 passed in 6.10s ['test_changes_that_never_touch_approval_refresh_nothing']
...
✓ 被抓到 取消按钮不刷新 | 1 failed, 18 passed in 6.02s ['test_the_admin_buttons_refresh_the_static_pages[cancel_scrim-published]']
25/25 被抓到，全部还原
```

## 测试机

补丁套上、重建、全量预渲染：

```
全量生成完成：成功 9，失败 0，删除 0；目录占用 78 KB
```

首页里搜这几个词：

```
   1 未来 7 天没有内战
   1 现在没有正在报名的赛事
```

「后续里程碑」「即将开放」「功能正在建设中」都没有了。测试机上还没有赛事和内战，所以看到的是空状态；有数据时的样子由本地测试覆盖。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
219 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python -m pytest -q
712 passed in 50.79s
```

693 → 712。055 推送后的 CI：`success 055: 给内战管理员组分配内战权限`。

## 改动文件

```
content/models.py                          首页取赛事和内战
content/templates/content/home_page.html   两块的列表、空状态、链接；删「正在建设中」
tournaments/services.py                    open_tournaments、team_entries；首页刷新
tournaments/registration.py                _refresh_public_pages
scrims/services.py                         upcoming_scrims、schedule_home_refresh、_status_changed
teams/views.py、teams/templates/teams/detail.html   参赛记录
tournaments/tests/test_public_pages.py     新建
tournaments/tests/conftest.py              新建，共享 make 夹具
scrims/tests/test_home_listing.py          新建
content/tests/test_content.py              旧断言「即将开放」改掉
handoff/STATUS.md
handoff/rounds/056-home-and-team-records/
```
