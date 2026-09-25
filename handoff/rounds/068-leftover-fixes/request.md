# 068 顺带发现的修复

## 背景

067 轮三个复核代理读代码时翻出六个和上游无关的问题，加上 STATUS 里排队已久的「内容编辑改不了文章分类」。都是小改动，各配一条「拆掉它就会红」的测试，凑成一轮，不和 069 起的新功能混在一起。

## 本轮范围

做（各一条测试，能变异的做变异）：

1. **内容编辑改不了文章分类**：设计 4.1 说内容编辑能管理文章分类和成员分组；成员分组的权限 066 给了（`members.services.assign_member_permissions`），文章分类从没给过。在 `content.services.assign_content_permissions()` 里给内容编辑组加 `articlecategory` 的增删改查权限
2. **恢复命令的加密列清单漏了对象存储密钥**：`core/management/commands/restore.py` 的 `ENCRYPTED_COLUMNS` 只有 `smtp_password`；`core_sitesettings.backup_s3_secret_access_key`（core 迁移 0009）也是 Fernet 加密的，密钥不对时查不出来
3. **`/me/registrations/` 的内战占位**：模板还写着「内战报名将在后续里程碑接入」，`/me/scrims/` 020 轮就有了；`ME_NAV` 没有「我的内战」入口，`scrims/me.html` 也不在个人中心的导航里
4. **生产设置漏了一个中间件**：`sjtu_ow/settings/prod.py` 整体替换 `MIDDLEWARE`，比 base 多了 WhiteNoise，但漏了 `core.middleware.PrerenderMissMiddleware`。生产和测试机上预渲染缺页的兜底一直是关的。补上，并加一条「prod 的中间件包含 base 的全部中间件」测试
5. **内战把段位分数 0 当成「没填」**：附录 A 里青铜 5 编码为 0，`scrims/services.role_problems`、`models.rank_pairs` / `best_rating`、`teaming.players_from`、`split_admin._placements_from_post` 都用真值判断，青铜 5 的玩家报角色限定内战会被拒、分队时段位被当作缺失。改成 `is not None`；`test_teaming.py` 里 `BRONZE_5 = 1` 的标签按附录 A 改正
6. **删除用于已结束内战的游戏 ID 会 500**：`ScrimSignup.game_account` 是 PROTECT，`accounts.services.deletion_blocked_reason` 只拦草稿和已发布的内战，已结束或已取消的内战里用过的 ID 一删就 `ProtectedError`。设计 3.5.2 的意思是只有未结束的内战拦删除。先写测试复现，再把外键改成删除时置空（设计 12.9.2 补上「可空，删除时置空」），读 `game_account` 的地方处理空值
7. **`handoff/rounds/042-guard-sweep/mutate_guards.py` 的 `APPS`** 还列着 `lfg`、`integrations`，没有 `members`。加「068 轮更正」注释后改掉

明确不做：新功能（069 起）；prod 中间件之外的设置差异（dev 独有的项不管）。

## 验收标准

- 本地检查全绿（ruff、tailwind、pytest、makemigrations --check、check --deploy）
- 每条修复的测试在修复前是红的（报告里写明），修复后绿；能变异的守卫变异被抓到
- CI 绿
