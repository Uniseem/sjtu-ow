# 197 AI 审核的设置搬进后台（报告）

## 做了什么

用户 10-05：「把 ai 的设置也放到后台去，我不想改什么 env，只想在后台改」。

1. **设计**（先改文档）：5.5.3 加「配置都在后台」一条、「没有配置密钥时不送审」改说全站设置；12 章全站设置表加五个字段；15 章「密钥」一行；16.3 环境变量表删掉两行、下面注明搬到后台；`docs/admin.md` 4.6；附录 D v7.1
2. **`SiteSettings` 五个新字段**（「AI 审核」一组）：
   - 接口密钥 `moderation_api_key`：`EncryptedTextField`，和 SMTP 密码、对象存储密钥一样加密存储；表单里不回显、空着保存表示不改，旁边写「现在：已保存 / 还没有」
   - 接口地址 `moderation_base_url`：空着用 DeepSeek
   - 附加请求参数 `moderation_extra_body`：JSON 对象，原样并进每次请求；不能带 `messages`、`tools`、`tool_choice`（`moderation.services.clean_extra_body`，新后台和 `/wagtail/` 的表单都用它）
   - 超时、最多输出 token（默认 30 秒、600）
3. **迁移 `core/0021`**：加字段；环境变量里要是设过 `MODERATION_API_KEY`、`MODERATION_BASE_URL`、`MODERATION_EXTRA_BODY`、`MODERATION_TIMEOUT`、`MODERATION_MAX_OUTPUT_TOKENS`，搬进全站设置（数据库里已有值的不覆盖）
4. **读配置的地方**：`moderation.providers.get_provider()` 每次从全站设置建（改完下一次巡查就生效，不用重启）；`OpenAICompatibleProvider` 的输出上限和附加参数改成构造参数；`moderation.services.is_configured()` 看全站设置里的密钥或地址。`settings/base.py` 删掉这五个环境变量，`.env.example` 删掉两行
5. **文字**：巡查记录页和「试一下」没配密钥时的说明、上线清单 AI 一项（现在链到全站设置）、`init_site` 结尾的「接下来」、`moderation_enabled` 的帮助文字，都改成「在全站设置里填」
6. **全站设置页右侧加「试一下 AI」**：用已保存的设置发一句测试内容，试完回到全站设置页（`moderation_try` 多认一个站内的 `next`）。「AI 审核」一组的顺序：开关、接口密钥、接口地址、模型、提醒邮箱、每日上限、连图片、附加参数、超时、最多输出
7. README「AI 内容审核」一节；AGENTS 硬规则 8 的密钥列表（AI 的密钥现在和 SMTP 密码一样加密存在全站设置里），两条过时的坑（Markdown 编辑器的样式在 `markdown-editor.css`、193 那版的侧栏标签条 196 已删）

## 测试

- 原来改 `settings.MODERATION_*` 的 12 处测试改成改全站设置（`moderation.tests.test_moderation.configure_ai`）；巡查记录页、上线清单的断言从 `MODERATION_API_KEY` 改成新的说明
- 新增 `moderation/tests/test_ai_settings.py` 11 条：服务商从全站设置建、只有密钥或只有地址都算配好、环境变量不再读、附加参数的校验、密钥存成密文不显示空着不改、附加参数在页面上被拒、`/wagtail/` 的设置页也不清掉密钥、「试一下 AI」回到设置页且不跳站外、没配密钥时让人去全站设置、迁移把旧环境变量搬进来

## 命令输出

测试机整组检查：

```
== pytest (05:20:36)
分片 1：447 passed in 55.15s
分片 2：447 passed in 55.17s
分片 3：447 passed in 58.24s
分片 4：446 passed in 56.72s
== 迁移 (05:21:39)
No changes detected
== 生产配置 (05:21:41)
System check identified no issues (0 silenced).
== 错误页和模板一致 (05:21:42)
== Docker 镜像 (05:21:43)
构建成功：199ca9fe6b12
== 全部通过 (05:21:43)
```

之后调了「AI 审核」一组字段的顺序，重跑相关的两组：

```
40 passed in 10.43s
```

变异（测试机，`handoff/rounds/197-ai-settings/mutate.py`，18 处、20 次检查，全部被抓到）：

```
mutations: 18 not applying: none
baseline green, 11 tests
caught a self-hosted address alone is not enough -> test_a_key_or_an_address_is_enough_and_nothing_else_is_read
caught the provider without the saved key -> test_the_provider_comes_from_the_settings_row
caught the extra body not sent -> test_the_provider_comes_from_the_settings_row
caught the output limit ignored -> test_the_provider_comes_from_the_settings_row
caught the timeout ignored -> test_the_provider_comes_from_the_settings_row
caught forbidden keys allowed -> test_the_extra_body_is_an_object_without_the_request_s_own_keys
caught forbidden keys allowed -> test_a_bad_extra_body_is_refused_on_the_field
caught a list taken as the extra body -> test_the_extra_body_is_an_object_without_the_request_s_own_keys
caught a list taken as the extra body -> test_a_bad_extra_body_is_refused_on_the_field
caught a blank key box clears the key -> test_the_key_is_saved_encrypted_never_shown_and_kept_when_blank
caught the secrets drawn as plain fields -> test_the_key_is_saved_encrypted_never_shown_and_kept_when_blank
caught the extra body unchecked on the page -> test_a_bad_extra_body_is_refused_on_the_field
caught wagtail's form clears the key -> test_wagtails_own_settings_page_keeps_the_key_too
caught the old variable read again -> test_the_environment_variables_are_gone
caught the migration forgets the key -> test_the_migration_carries_the_old_environment_in
caught the migration forgets the numbers -> test_the_migration_carries_the_old_environment_in
caught trying the AI never comes back -> test_the_ai_is_tried_from_the_settings_page_and_comes_back
caught trying the AI goes anywhere -> test_the_ai_is_tried_from_the_settings_page_and_comes_back
caught the owner told to edit .env -> test_without_a_key_the_owner_is_sent_to_the_settings
caught the checklist points at the review list -> test_ai_says_whether_the_key_or_the_switch_is_missing
restored and green; missed: none
```

浏览器（测试机）：

```
看了 163 个地址，0 处有问题
```

截了全站设置页（1280 宽），「AI 审核」一组的新字段、帮助文字和「现在：还没有。」显示正常。

## 部署（正式站）

正式站 `.env` 里的两行是空的（只看了有没有值，没打印内容）：

```
0
MODERATION_API_KEY=
MODERATION_BASE_URL=
```

先备份：

```
已备份到 /app/backups/sjtu-ow-20261005-133609.tar.gz（210.8 MB）
```

`deploy_ship.sh 197`（这轮没有删文件）：

```
 Image sjtu-ow-web Built 
 Image sjtu-ow-worker Built 
sjtu-ow-web 2026-10-05 07:36:57 +0200 CEST
  Applying core.0021_ai_settings_in_admin... OK
 Container sjtu-ow-worker-1 Starting 
 Container sjtu-ow-worker-1 Started 
全量生成完成：成功 12，失败 0，删除 0；目录占用 280 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

正式站真实数据上只读检查（`/root/smoke197.py`，请求工厂调视图；每行是状态码、地址、页面里有没有「接口密钥」「试一下 AI」「MODERATION_API_KEY」）：

```
200 /admin/settings/site/ True True False
200 /admin/moderation/ True False False
200 /admin/ True True False
configured: False key saved: False
timeout/tokens: 30 600
reason: 还没有填接口密钥（自建服务可以只填接口地址），AI 审核不会运行。在「设置 → 全站设置 → AI 审核」里填好、保存，下一次巡查就会用上。
```

## 没做 / 没验证

- 没有真的接 DeepSeek 试（正式站还没有密钥；测试里服务商都是假的）。用户在全站设置里填好密钥后点「试一下 AI」就知道
- 正式站 `.env` 里那两行空的 `MODERATION_*` 没删（不再读，留着无害；不动生产配置）
- 已保存的密钥只能换、不能在页面上清空（和 SMTP 密码一样）；要停用 AI 关掉「启用 AI 内容审核」就行
