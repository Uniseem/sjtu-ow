# 057 实现报告

## 结论

**完成。** 设计 13.13.4 事件表剩下的四行都补上了，**14 行现在全部落实**。后台全站设置里 9 个「后续里程碑使用」的说明和 2 个分组标题换成了真正的说明。测试机上按升级流程（先备份、再迁移）更新，已生效。

## 补上的触发

| 事件 | 重新生成 | 实现 |
|---|---|---|
| 内战报名、修改报名、取消报名 | 活动详情 | `scrims.services._refresh_detail`，`sign_up` 和 `cancel` 调用。同一页面 30 秒内的多次请求本来就会合并，报名高峰只生成一次 |
| 用户修改昵称 | 所在的战队主页、报名的内战详情、署名的文章 | `accounts/signals.py`：`pre_save` 记下旧昵称，`post_save` 比较，**真的变了**才调 `accounts.services.refresh_nickname_pages` |
| 文章发布、修改、移动、撤回、网址改变 | 关联赛事的详情页 | `content/signals.py` 的 `refresh_related_tournament`，只对文章、只对已上架的赛事 |
| 游戏模式新建、修改、删除 | 组队大厅外壳 | 新文件 `lfg/signals.py` |

**昵称那条为什么要先比较**：登录时 Django 会更新 `last_login` 并保存用户（`update_fields=["last_login"]`），`post_save` 每次都会触发。不比较的话，每次登录都会把这个人所有的战队页、内战页、文章重新生成一遍。只更新了别的字段时连旧昵称都不查。

## 设置说明

`core/models.py` 删掉 `LATER = "后续里程碑使用"`，9 个字段各写一句说明（比如战队人数上限：「一支战队最多多少人，含队长。」），分组标题「社区参数（后续里程碑使用）」「AI 审核（后续里程碑使用）」去掉括号。迁移 `core/0010_settings_help_text` 只改说明文字，不动数据。

## 测试

`core/tests/test_regeneration_events.py`，6 条：报名和取消各刷新一次详情；改昵称刷新三类页面；登录式保存和昵称不变的保存都**不**刷新；文章发布和撤回都刷新关联赛事；游戏模式新建和删除都刷新外壳；设置里不再有「后续里程碑」。

## 变异

```
✓ 被抓到 报名不刷详情 | 1 failed, 5 passed in 0.86s ['test_signing_up_and_cancelling_refresh_the_scrim_page']
✓ 被抓到 取消报名不刷详情 | 1 failed, 5 passed in 0.92s ['test_signing_up_and_cancelling_refresh_the_scrim_page']
✓ 被抓到 改昵称不刷新 | 1 failed, 5 passed in 0.73s ['test_a_new_nickname_refreshes_every_page_that_prints_it']
✗ 没抓到 登录也算改昵称（只影响性能） | 6 passed in 0.64s []
✓ 被抓到 昵称没变也刷新 | 1 failed, 5 passed in 0.68s ['test_logging_in_does_not_refresh_anything']
✓ 被抓到 改昵称不刷战队页 | 1 failed, 5 passed in 0.62s ['test_a_new_nickname_refreshes_every_page_that_prints_it']
✓ 被抓到 改昵称不刷内战页 | 1 failed, 5 passed in 0.65s ['test_a_new_nickname_refreshes_every_page_that_prints_it']
✓ 被抓到 改昵称不刷文章 | 1 failed, 5 passed in 0.62s ['test_a_new_nickname_refreshes_every_page_that_prints_it']
✓ 被抓到 文章不刷关联赛事 | 1 failed, 5 passed in 0.65s ['test_an_article_refreshes_the_tournament_it_is_linked_to']
✓ 被抓到 新建/修改游戏模式不刷外壳 | 1 failed, 5 passed in 0.67s ['test_changing_a_game_mode_refreshes_the_lfg_shell']
✓ 被抓到 删除游戏模式不刷外壳 | 1 failed, 5 passed in 0.62s ['test_changing_a_game_mode_refreshes_the_lfg_shell']
✓ 被抓到 标题改回过时说法 | 1 failed, 5 passed in 0.61s ['test_no_setting_is_still_labelled_for_a_later_milestone']
11/12 被抓到，全部还原
```

**唯一幸存的是等价变异**：拆掉「只更新 `last_login` 就不查旧昵称」这个提前返回后，仍然会查出旧昵称、比较、发现相同、不刷新。行为一样，只是登录时多一次查询。不为它写查询次数的测试——登录的 `post_save` 上还挂着别的信号，查询数会随它们变化，测试会很脆。

## 测试机（第一次走升级流程）

设计 16.8：先备份，再迁移，再启动。

```
--- 1. 升级前备份（用旧镜像）:
已备份到 /app/backups/sjtu-ow-20260918-164525.tar.gz（0.1 MB）
异地备份没有开启。本地这份没有加密，里面有用户邮箱和联系方式，**服务器没了这份也跟着没了**。在「设置 → 全站设置 → 异地备份」里配置对象存储（设计 16.7）。
--- 3. 迁移:
  Applying core.0010_settings_help_text... OK
--- 4. 启动:
web: healthy
--- 5. 预渲染:
全量生成完成：成功 9，失败 0，删除 0；目录占用 78 KB
--- 6. 设置说明:
一支战队最多多少人，含队长。
[]
```

**这也是备份命令第一次在服务器上跑**，正常生成，异地备份的提醒也如期出现。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
221 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python -m pytest -q
718 passed in 52.32s
```

712 → 718。

## 改动文件

```
scrims/services.py                       _refresh_detail
accounts/signals.py                      记旧昵称、比较后刷新
accounts/services.py                     refresh_nickname_pages
content/signals.py                       refresh_related_tournament
lfg/signals.py                           新建
lfg/apps.py                              注册信号
core/models.py                           设置说明
core/migrations/0010_settings_help_text.py
core/tests/test_regeneration_events.py   新建，6 条
handoff/STATUS.md
handoff/rounds/057-remaining-regeneration/
```
