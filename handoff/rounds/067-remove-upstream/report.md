# 067 实现报告

## 结论

**完成。** 设计升到 v1.6；`integrations` 的代码、模板、测试、依赖和接线全部删除，包只剩迁移历史；`tournaments` 去掉了审核模式、上游推送来源、「待上游确认」状态和「上游」操作方，新增赛事级开关「报名自动通过」并在后台锁定；README、AGENTS.md、协议草稿、crontab、Caddyfile、REVIEW-GUIDE、STATUS 同步。本地检查全绿，7 处新守卫的变异全部被抓到，066 版旧库的升级演练通过。

## 逐条结果

| 任务 | 结果 |
|---|---|
| 1 设计 v1.6 | `docs/design.md` 108 处替换（三个脚本，每处断言原文只出现一次）。第 11 章、12.10 节整段改为删除说明，章节号保留；8.5 节重写为 6 行流转表；18 章 M5 标删除、新增 M8；附录 B/C/D 同步。全文 grep「上游」「开放 API」「Webhook」只剩第 11 章、12.10、2.3、8.5 的删除说明和附录 D 的历史行 |
| 2 删除 integrations | 删了 15 个源文件加 `templates/`、`tests/`（110 条测试）。保留 `__init__.py`、`apps.py`、`migrations/0001`、`0002`，新增 `0003` 和包内 `README.md`。接线：`INSTALLED_APPS` 去掉 DRF 三个包（`integrations` 保留，`tournaments/0004` 依赖它的 `0001`）、中间件、`REST_FRAMEWORK`、`SPECTACULAR_SETTINGS`、`API_*`、`WEBHOOK_ALLOW_INSECURE_URLS`（base 和 prod）、`/api/v1/` 路由、`core/middleware.py` 的 API 文档 CSP、`core/net.py` 的 `allow_insecure`、`cleanup_old_data` 两项、`restore.py` 两行、robots 的 `/api/`、crontab 的 webhook 行、Caddyfile 的 `/api/*`、`pyproject.toml` 三个依赖并重新锁定 |
| 3 迁移 | `makemigrations` 生成 `tournaments/0005_remove_upstream`（删约束、四个字段，加 `auto_approve`，改四处 choices）和 `integrations/0003_remove_upstream`（删五个索引、一个外键、三张表；自动生成的依赖顺序正确：先 tournaments 0005 再 integrations 0003）。手工加了两个 RunPython：`awaiting_upstream` 报名改回 `pending`；删任务表里 `task_path` 以 `integrations.` 开头的记录（依赖 `("django_tasks_database", "__latest__")`，应用标签不是包名，第一次写错了）。全新库和旧库各跑一次，见下 |
| 4 报名自动通过 | `submit()` 写完名单后若开关打开，同一事务里 `_set_status(APPROVE, SYSTEM, note="自动通过")`；`_after_status_change` 对系统操作方不发第二封邮件；同步名单和重新提交后同样自动通过。后台 `TournamentAdminForm.clean()` 用现有 `services.has_registrations()` 在有报名后拒绝改开关，通过 `Tournament.base_form_class` 接进 Wagtail 的表单 |
| 5 状态机与后台 | `approve` / `reject` 去掉 `actor_type` 参数和 `_guard_actor`；`RegistrationError` 去掉只给 API 用的 `code`；`local_actions()` 只按状态；审核详情页去掉审核模式，无操作时提示「当前状态下没有可用的审核操作」；提交成功提示按结果区分「已提交并自动通过」/「等待审核」；报名页的「再次提交」说明按开关区分 |
| 6 测试整理 | `test_state_table.py` 重写：6 行流转表 + 8 条自动通过用例（含后台锁、只发一封邮件、同步后再次通过、管理员可撤销）；其余 5 个 tournaments 测试文件删上游用例、改夹具；`test_chapter15_audit.py` 附录 B/C 的 pin 去掉 API/Webhook 项；恢复命令的测试改用 `SiteSettings.smtp_password` 造加密数据；地址清单、安全守卫、robots 测试相应修改；新增 `core/tests/test_upstream_removed.py` 5 条「已删除」断言，含「Wagtail 自己的 admin API 在去掉 `REST_FRAMEWORK` 设置后仍然可用」 |
| 7 文档 | README 删「开放 API」整节、「定时清理」说明挪到「定时维护」、升级说明加 067 一段；AGENTS.md 目录表、硬规则 6、坑（删 drf 一条，加「删应用先看迁移依赖」「Windows 跑测试设 `PYTHONUTF8=1`」）；隐私政策删「合作赛事平台」段；用户协议改审核一句；REVIEW-GUIDE 四处；STATUS 见文件 |

## 验收输出

```
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
215 files left unchanged

$ uv run python manage.py tailwind build --force
UnicodeDecodeError: 'gbk' codec can't decode byte 0x88 in position 15: illegal multibyte sequence
Built production stylesheet 'C:\Users\fyc12\Desktop\Claudee\sjtu-ow\static\css\app.css'.

$ PYTHONUTF8=1 uv run pytest -q
717 passed in 135.16s (0:02:15)

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

`tailwind build` 的那行 `UnicodeDecodeError` 是 Windows 控制台 GBK 编码的问题，CSS 照样生成；不设 `PYTHONUTF8=1` 时有三条用 `read_text()` 读中文文件的测试也会因 GBK 解码失败（`test_home_sections`、`test_legal_pages`、`test_chapter15_audit` 各一条），设了以后全绿。CI 是 Linux，不受影响。已写进 AGENTS.md 的坑。

**变异（新守卫逐个拆掉，跑对应测试）**

```
✓ 被抓到 auto_approve 分支被拆掉 | 3 failed, 2 passed, 22 deselected in 8.36s
✓ 被抓到 系统通过不再跳过状态变化邮件 | 1 failed, 26 deselected in 7.42s
✓ 被抓到 后台表单不再检查是否已有报名 | 1 failed, 26 deselected in 6.88s
✓ 被抓到 base_form_class 没接上 | 2 failed, 25 deselected in 6.63s
✓ 被抓到 approve 不再检查当前状态 | 3 failed, 24 deselected in 7.28s
✓ 被抓到 撤销通过按钮对任何状态都显示 | 1 failed, 9 deselected in 7.93s
✓ 被抓到 rejected 状态的名单不再释放名额（原有守卫，回归） | 2 failed, 25 deselected in 6.70s
---
7/7 mutations caught
```

脚本：`mutate_067.py`（本轮目录）。每次改坏后清 `tournaments/__pycache__`，跑完按原字节恢复。

**066 旧库升级演练**

用 `git worktree add ../sjtu-ow-066 f08bcfe` 拉出 066 提交，单独 `uv sync`，`DATABASE_PATH` 指向临时文件：

```
[066] migrate ... OK
[066] seed:  registration status = awaiting_upstream | integrations tasks = 1 | other tasks = 3 | api clients = 1
[066] showmigrations: integrations 0001、0002 [X]；tournaments 0001–0004 [X]

[067] migrate（同一个库）
  Applying tournaments.0005_remove_upstream... OK
  Applying integrations.0003_remove_upstream... OK

[067] check
integrations tables left: []
integrations indexes left: []
old tournament columns left: []
auto_approve present: True
actor_client_id left: False
registration statuses: ['pending']
auto_approve values: [False, False]
integrations tasks left: 0 | other tasks kept: 3
integrations migration rows: ['0001_initial', '0002_webhookdelivery', '0003_remove_upstream']
tournaments migration rows: ['0001_initial', ..., '0004_remove_tournament_tournament_external_id_unique_and_more', '0005_remove_upstream']
```

接着在同一个库上跑升级说明里的那步：

```
$ python manage.py shell -c "...ContentType.objects.filter(app_label='integrations')..."
['apiclient', 'apirequestlog', 'webhookdelivery']
$ python manage.py remove_stale_contenttypes --include-stale-apps --noinput
$ （再查一次）
[]
```

造的旧数据：一个两级审核赛事（带上游推送来源和 `external_id`）、一个本站审核赛事、一条被改成「待上游确认」的报名、一个 API 客户端、一条排队的 `deliver_due_webhooks` 任务、三条无关的邮件任务。脚本 `drill_seed_066.py`、`drill_check_067.py` 在本轮目录。

## 设计偏差

无。设计先改（v1.6），代码照设计做。

## 未完成

无。测试机没动（用户指示 VPS 先不管，且 SSH 主机密钥已变化）。部署时按 README「从有开放 API 的旧版本升级」：迁移后 `remove_stale_contenttypes --include-stale-apps --noinput`，删 `/etc/cron.d/sjtu-ow-test` 里的 webhook 行。

## 顺带发现（留给 068）

1. `sjtu_ow/settings/prod.py` 整体替换 `MIDDLEWARE`，漏掉 `core.middleware.PrerenderMissMiddleware`，生产环境预渲染缺页兜底一直是关的（代理复核发现，没有测试覆盖 prod 的中间件列表）
2. `core/management/commands/restore.py` 的加密列清单漏了 `core_sitesettings.backup_s3_secret_access_key`（core 迁移 0009 加的）
3. `templates/me/registrations.html` 还写着「内战报名将在后续里程碑接入」，`/me/scrims/` 早就有了；`ME_NAV` 缺入口
4. 内容编辑改不了文章分类：设计 4.1 说能，`init_site` 从没给过权限（STATUS 里排队已久）
5. 内战把段位分数 0（青铜 5）当成「没填」：`scrims/services.role_problems`、`models.rank_pairs/best_rating`、`teaming.players_from`、`split_admin._placements_from_post` 都用真值判断；`test_teaming.py` 的 `BRONZE_5 = 1` 标错
6. `ScrimSignup.game_account` 是 PROTECT，但 `accounts.services.deletion_blocked_reason` 只拦草稿和已发布的内战，删一个用于已结束内战的游戏 ID 大概率 500（读代码得出，未复现）
7. `handoff/rounds/042-guard-sweep/mutate_guards.py` 的 `APPS` 列表还写着 `lfg`、`integrations`
8. `content/models.py` 的 `RESERVED_CHILD_SLUGS` 还保留着 `api`，无害，留着

## 需要确认

1. **`pyyaml` 改成了显式的开发依赖**（`[dependency-groups] dev`）。它原来由 drf-spectacular 间接带入，`core/tests/test_healthcheck_script.py` 用它解析 `docker-compose.yml`；删掉 drf-spectacular 后 9 条测试 `No module named 'yaml'`。MIT 许可证，只在测试用。硬规则 5 说加依赖要先问，这次算把已在用的依赖写明，不是新引入；你不认可就改成不用 yaml 的解析
2. **状态日志的历史行没有改写**：`awaiting_upstream` 只在 `Registration.status` 上映射回 `pending`；日志表里 `from_status` / `to_status` / `actor_type` 的旧值（`awaiting_upstream`、`upstream`）原样保留，因为设计 12.8.4 说日志只增不改。后台看这类旧行会显示原始值。测试机上大概率一条都没有
3. **`integrations` 用「墓碑」而不是压缩迁移**：`tournaments/0004` 引用 `integrations.apiclient`，整个删应用会让迁移图断掉。压缩（squash）要等所有库都迁到 0005 之后才能删旧文件，而测试机现在动不了。墓碑是三个空文件，以后想清理再压缩

## 改动文件

- 设计与记录：`docs/design.md`、`handoff/STATUS.md`、`handoff/REVIEW-GUIDE.md`、`handoff/rounds/067-remove-upstream/`
- 文档：`README.md`、`AGENTS.md`、`content/legal/privacy.md`、`content/legal/terms.md`
- `integrations/`：删 `api.py`、`api_views.py`、`middleware.py`、`models.py`、`notifications.py`、`pagination.py`、`sanitize.py`、`schema.py`、`serializers.py`、`services.py`、`signing.py`、`tasks.py`、`urls.py`、`views.py`、`wagtail_hooks.py`、`webhooks.py`、`templates/`、`tests/`；改 `apps.py`；新增 `README.md`、`migrations/0003_remove_upstream.py`
- `tournaments/`：`models.py`、`registration.py`、`review_admin.py`、`wagtail_hooks.py`、`registration_views.py`、`services.py`、`templates/tournaments/admin/review_detail.html`、`templates/tournaments/register.html`、新增 `migrations/0005_remove_upstream.py`；测试 `test_state_table.py`（重写）、`test_registration.py`、`test_tournaments.py`、`test_review_admin.py`、`test_guards.py`、`test_disband_blockers.py`
- `teams/services.py`（文档字符串）
- `core/`：`middleware.py`、`net.py`、`management/commands/cleanup_old_data.py`、`management/commands/restore.py`；测试 `test_chapter15_audit.py`、`test_ops_commands.py`、`test_documented_urls.py`、`test_security_guards.py`、新增 `test_upstream_removed.py`
- `content/views.py`、`content/tests/test_content.py`
- `sjtu_ow/settings/base.py`、`sjtu_ow/settings/prod.py`、`sjtu_ow/urls.py`
- `deploy/crontab.example`、`deploy/Caddyfile`
- `pyproject.toml`、`uv.lock`
