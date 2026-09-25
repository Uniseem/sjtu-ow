# 068 实现报告

## 结论

**完成。** 七项全部修好，每项配了测试；把修复逐个还原，9/9 处对应测试变红。设计升到 v1.6.1（只有 12.9.2 节一处字段变化）。

## 逐条结果

| 任务 | 结果 |
|---|---|
| 1 内容编辑管文章分类 | `content.services.assign_content_permissions()` 给内容编辑组加 `articlecategory` 的增删改查（`CATEGORY_PERMISSIONS`）。测试：内容编辑打开分类列表和新建页 200，赛事管理员被送回后台首页 |
| 2 恢复命令的加密列 | `restore.py` 的 `ENCRYPTED_COLUMNS` 加 `core_sitesettings.backup_s3_secret_access_key`。测试：只设 R2 密钥不设 SMTP 密码，换一把 `FIELD_ENCRYPTION_KEY` 恢复必须报错——修复前这条测试静默通过恢复，也就是密钥不匹配查不出来 |
| 3 我的内战 | `ME_NAV` 加「我的内战」；`/me/registrations/` 的占位文案换成链接；`scrims/me.html` 改为继承 `me/base.html`，`me_scrims` 视图用 `accounts.views.me_context` 提供导航。测试三条 |
| 4 prod 中间件 | `prod.py` 补 `core.middleware.PrerenderMissMiddleware`。测试：子进程里分别导入 base 和 prod，断言 base 的每个中间件 prod 都有。`_import_prod` 拆成 `_run_in_prod_env(code)` 复用 |
| 5 段位 0 | `role_problems`、`rank_pairs`、`best_rating`、`teaming.players_from`、`_placements_from_post` 五处改成 `is None` 判断。测试文件 `scrims/tests/test_bronze_five.py` 五条，青铜 5 报角色限定内战不再被拒、分队和分队页都保留 0 分。`test_teaming.py` 三个标错的常量改名（`BRONZE_5`→`BRONZE_4`、`PLATINUM_1`→`PLATINUM_2`、`MASTER_5`→`MASTER_4`），值不动，测试数据不变 |
| 6 已结束内战的游戏 ID | `ScrimSignup.game_account` 改为 `null=True, on_delete=SET_NULL`（迁移 `scrims/0002`），设计 12.9.2 同步；新增 `ScrimSignup.battletag` 属性，删了之后显示「（游戏 ID 已删除）」，模板、复制文本、个人信息导出改用它。测试：已结束内战里的 ID 通过页面删除成功、报名记录保留、段位显示未填；未结束的仍被拦（HTMX 返回 400） |
| 7 `mutate_guards.py` | `APPS` 去掉 `lfg`、`integrations`，加 `members`，加「068 轮更正」注释 |

## 验收输出

```
$ uv run ruff format . && uv run ruff check .
1 file reformatted, 217 files left unchanged
All checks passed!

$ PYTHONUTF8=1 uv run pytest -q
731 passed in 137.84s (0:02:17)

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

**修复逐个还原（脚本 `mutate_068.py`，本轮目录）**

```
✓ 被抓到 1 内容编辑的文章分类权限没给 | 1 failed, 1 passed in 2.79s
✓ 被抓到 2 恢复命令不再检查对象存储密钥 | 1 failed, 25 deselected in 1.52s
✓ 被抓到 3 导航里没有「我的内战」 | 1 failed, 2 passed in 1.87s
✓ 被抓到 4 prod 又漏掉 PrerenderMissMiddleware | 1 failed, 12 deselected in 0.64s
✓ 被抓到 5a 角色限定内战又把 0 当没填 | 4 failed, 1 passed in 1.95s
✓ 被抓到 5b best_rating 又丢掉 0 | 1 failed, 4 passed in 1.76s
✓ 被抓到 5c 分队页又把 0 换成最高段位 | 1 failed, 4 passed in 1.69s
✓ 被抓到 5d 算法又丢掉 0 | 1 failed, 4 passed in 1.64s
✓ 被抓到 6 删掉的游戏 ID 不再显示占位 | 1 failed, 45 deselected in 1.46s
---
9/9 mutations caught
```

第 6 项的外键改动本身没法不带迁移地还原，所以变异拆的是「已删除」占位；修复前的行为（`ProtectedError`）是读代码得出的，没有在 067 版代码上跑过这条测试。

## 设计偏差

无。12.9.2 先改（v1.6.1）再改代码。

## 未完成 / 顺带发现

- 第 4 项的效果要在测试机部署后验证：故意删一个预渲染文件，访问该页应由 Django 实时渲染并重新排队生成。写进 STATUS
- 内战分队页的成员表和卡片对已删除的游戏 ID 显示「（游戏 ID 已删除）」，但没有针对这个页面的渲染测试（只测了模型属性）

## 需要确认

无。

## 改动文件

`docs/design.md`、`README.md`、`handoff/STATUS.md`、`handoff/rounds/068-leftover-fixes/`、`handoff/rounds/042-guard-sweep/mutate_guards.py`；`content/services.py`、`content/tests/test_category_permissions.py`（新）；`core/management/commands/restore.py`、`core/tests/test_ops_commands.py`、`core/tests/test_security_guards.py`；`accounts/views.py`、`accounts/services.py`、`accounts/tests/test_me_nav.py`（新）、`templates/me/registrations.html`；`sjtu_ow/settings/prod.py`；`scrims/models.py`、`scrims/services.py`、`scrims/teaming.py`、`scrims/split_admin.py`、`scrims/views.py`、`scrims/migrations/0002_game_account_set_null.py`（新）、`scrims/templates/scrims/me.html`、`scrims/templates/scrims/admin/split.html`、`scrims/templates/scrims/admin/_card.html`、`scrims/templates/scrims/slots/actions.html`、`scrims/tests/test_teaming.py`、`scrims/tests/test_scrims.py`、`scrims/tests/test_bronze_five.py`（新）
