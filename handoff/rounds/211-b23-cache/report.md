# 211 实现报告

## 结论

完成。D1（失效 b23 短链不缓存）和 D10（字数随请求重算）已修，顺带修了同函数的 F10；测试机整组检查 1912 条全绿。修的过程中抓到测试基建的一个旧问题：两条迁移测试回滚迁移后不回放，把分片共享的测试库留在旧表结构上（见「顺带发现」），已修并加了常驻守卫。

## 逐条结果

1. **b23 短链查询失败也缓存**：`content/embeds.py` 新增 `FAILED_LOOKUP_TTL`（1 小时）和 `remember_failed_lookup(url)`，往 Wagtail `Embed` 表写 `html=""`、`cache_until` 一小时后的行（`IntegrityError` 吞掉，已有行不覆盖）；`content/markdown.py` 的 `video_src` 在 `except EmbedException` 时调它再返回 `""`。`find_embed` 的返回字典补 `"cache_until": None`——否则失败行的旧 `cache_until` 会被 `update_or_create` 保留，后来查到的成功结果也永远显得过期。成功结果照旧永久缓存（`test_a_short_link_is_looked_up_once` 仍绿）。
2. **F10**：`extract_bvid_and_page` 对 query 里的 `bvid` 加 `BV_RE.fullmatch`，非法的当成没有（不再能往播放器地址塞 `autoplay=1` 这类参数）。
3. **存好的字段**：`ArticlePage` 加 `body_plain` / `body_words` / `body_minutes`，`Tournament`、`Scrim` 加 `description_plain`；各自的 `save()` 在 `update_fields` 为 `None` 或含源字段（`body` / `description`）时重算，并把派生字段并进 `update_fields`，否则不碰。`content/article_meta.py` 的 `body_text` 改成一次 `analyse` 同时出纯文本（`plain_html` 从 `plain_text` 拆出），新增 `stored_counts(body)`。
4. **模板改读字段**：`article_page.html`、`post_card.html` 改读 `body_minutes` / `body_words`；`ArticlePage.facts` 属性和 `context["facts"]` 删除。
5. **搜索和邮件**：`search/services.py` 文章匹配 `page.body_plain`、赛事内战匹配 `row.description_plain`，不再每次搜索逐篇渲染；`scrims/notifications.py` 的内战邮件用 `scrim.description_plain`；`core/email_samples.py` 的样张补上 `description_plain`。
6. **迁移**：`content/migrations/0012_article_body_caches.py`、`tournaments/migrations/0015_tournament_description_plain.py`、`scrims/migrations/0005_scrim_description_plain.py`，各带 `RunPython` 回填已有行；`makemigrations --check --dry-run` 干净。
7. **变异验证**（每处改坏后对应测试都变红，再改回）：失败不缓存（渲染两次联网两次）、`?bvid=` 不校验、`find_embed` 不返回 `cache_until`（成功结果被旧失败行拖住）、文章 `save()` 不重算、搜索改回现场渲染、赛事 `save()` 不重算——6 处全部被抓。注意：变异要用编辑工具改文件，heredoc 没匹配上目标字符串会造成假绿（踩到一次）。

## 测试机 4 条失败的根因与修复（顺带发现，挡住了验收，本轮一并修）

第一次整组检查 4 条失败，全部 `no such column: content_articlepage.body_plain`，都在分片 3：

```
FAILED core/tests/test_held_letters.py::test_a_member_applies_and_is_asked_before_the_captain_is_mailed
FAILED core/tests/test_held_letters.py::test_an_admin_cancels_a_scrim_and_is_asked_in_the_back_office
FAILED core/tests/test_offsite_backup.py::test_restore_pulls_from_the_bucket_and_decrypts
FAILED tournaments/tests/test_concurrency.py::test_a_team_cannot_go_over_capacity_under_a_race
```

排查过程（证据都在测试机 `/srv/sjtu-ow-check/runs/20261006-181354-fbb863e.log` 和 `shards/ids.3`）：分片是跨运行保留的 worktree，`--reuse-db` 每次只跑增量迁移，会话开始时 0012 已正常应用；4 条失败在 `ids.3` 里连续（339–346 行），排在它们**前面一位**的是 `backoffice/tests/test_backoffice.py::test_the_migration_turns_the_introduction_and_its_drafts_into_markdown`——它把 `content` 回滚到 0008 再放行到 0009 就结束了，**不回放到最新**，于是它之后的测试对着没有 `body_plain` 的旧表结构跑。再往后 `tournaments/tests/test_registration_mode.py` 的迁移测试收尾时会 `migrate(leaf_nodes)` 把全部应用放回最新，所以污染窗口在 338–346 之间，只有碰到 `ArticlePage` 新列的 4 条红了。以前没炸是因为 0010、0011 没给 `content_articlepage` 加列；本轮 0012 是第一个加列的。本地按同样顺序连跑两条即可复现。

同类问题还有一处：`moderation/tests/test_ai_settings.py::test_the_migration_carries_the_old_environment_in` 把 `core` 停在 0021（最新是 0024），这次恰好窗口里没有碰 `core_heldletter` 的测试，是潜伏的。

修复（对照 129 起 `test_registration_mode.py`、`test_markdown_migration.py`、`test_trust_migrations.py` 已有的「finally 里回放到最新」惯例）：

- 上面两条测试补上 `finally: call_command("migrate", verbosity=0)`；
- `conftest.py` 加常驻守卫 `_migration_tests_leave_the_schema_at_latest`：每个 `transaction=True` 测试结束后检查没有待应用的迁移，有就直接报出是哪个测试留下的、缺哪几个。executor 类在 conftest 导入时绑定（`test_restore_warns_when_the_code_is_newer_than_the_backup` 会把 `MigrationExecutor` 打桩成假的，夹具拆除顺序不保证桩已撤掉，踩到一次误报）。

守卫的变异验证：临时把 backoffice 那条测试的 `finally` 摘掉，该测试自己立刻变红，报错原文：`这个测试把数据库留在了旧迁移上，后面的测试会对着旧表结构跑：content.0010_unnamed_while_new, content.0011_article_category_while_draft, content.0012_article_body_caches`。改回后转绿。

## 验收输出

本地复现（修复前）：

```
FAILED core/tests/test_held_letters.py::test_a_member_applies_and_is_asked_before_the_captain_is_mailed
1 failed, 1 passed in 3.28s        ← backoffice 迁移测试先跑，held_letters 跟着红
```

修复后同一组合：`3 passed in 6.51s`。受影响的九个测试文件：`125 passed in 48.57s`。`ruff check` / `ruff format --check` 干净。

测试机整组检查（`bash scripts/remote-check.sh`，2026-10-06 18:42–18:45 服务器时间）：

```
== pytest (10:42:57)
1912 条测试分成 4 片
分片 1：478 passed in 127.73s (0:02:07)
分片 2：478 passed in 131.62s (0:02:11)
分片 3：478 passed in 133.48s (0:02:13)
分片 4：478 passed in 117.77s (0:01:57)
== 迁移 (10:45:18)
No changes detected
== 生产配置 (10:45:19)
System check identified no issues (0 silenced).
== 错误页和模板一致 (10:45:20)
== Docker 镜像 (10:45:22)
构建成功：da908447a130
== 全部通过 (10:45:22)
```

（ruff、Tailwind 编译也在同一日志里通过；用户可见行为没变，模板只换了字段名，没加新的工具类，不需要 `--force`。）

## 设计偏差

无。文档先改（design.md v7.14：5.2、12.5.1、12.8.1、12.9.1、13.16、附录 D；design-details.md 6.3），实现照文档。

## 未完成 / 顺带发现 / 需要确认

- 测试机上 210 留下的守卫普查还在后台跑（中途结果 59/299 已取回放在 `rounds/210-full-review/`，会被完整结果覆盖，**没有进本轮提交**）；跑完取回、逐个判断「全量测试也没抓到」的守卫、清理 sweep worktree，都是 210 的尾巴，不占本轮。
- 测试机负载高（普查在跑），计时类测试偶发失败属已知现象，这次没出现。
- 210 复核的其余条目按顺序在 212 及以后：212 自动保存收尾（T1、A1、A3、F2、F4、B6、D3、D2），213 守卫（S1、S7、S2、S3、T2、A8、A9、B3），214 worker（C1–C3），215 Caddy 和预渲染（C4、C5、C6、C9、F1）。A2、A12、T7、B11 等用户拍板。

## 改动文件

代码：`content/embeds.py`、`content/markdown.py`、`content/article_meta.py`、`content/models.py`、`tournaments/models.py`、`scrims/models.py`、`scrims/notifications.py`、`search/services.py`、`core/email_samples.py`、`content/templates/content/article_page.html`、`templates/components/post_card.html`

迁移：`content/migrations/0012_article_body_caches.py`、`tournaments/migrations/0015_tournament_description_plain.py`、`scrims/migrations/0005_scrim_description_plain.py`（新）

测试：`content/tests/test_markdown.py`、`content/tests/test_article_head.py`、`search/tests/test_search.py`、`backoffice/tests/test_backoffice.py`、`moderation/tests/test_ai_settings.py`、`conftest.py`

文档：`docs/design.md`（v7.14）、`docs/design-details.md`；轮次目录 `handoff/rounds/211-b23-cache/`
