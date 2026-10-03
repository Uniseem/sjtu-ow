# 122 站长上线清单（报告）

## 怎么查的

本机用新的空库（`DATABASE_PATH` 指到临时目录）照 README 走一遍：`migrate`、`createcachetable`、`init_site`，再用测试客户端打开各公开页面和后台首页（`scratchpad/walk_owner.py`）。看到的：首页、资讯、战队、赛事、内战、成员、搜索都有合适的空状态；**用户协议、隐私政策、关于我们只有标题和日期**；后台首页只有「待办：暂时没有待办」。

## 做了什么

1. **「上线清单」**（`core/admin_setup.py`、`core/templates/core/admin/setup_panel.html`，后台首页插在「待办」后面，只给超级管理员）：每项 `Check(label, done, detail, url, required)`
   - 必做：邮件（SMTP 服务器和发件地址都填了）；用户协议、隐私政策（有正文且没有「【」，写出还剩几处）
   - 建议：AI 审核（没设密钥 / 开关关着 / 在运行，三种说法）、异地备份（`BACKUP_ENCRYPTION_KEY` 和对象存储开关都要有）、内容编辑组里有在用的账号、关于我们有正文、站点简介 / QQ 群 / 成立日期 / 首屏图、默认封面和默认头像图库有图、测试环境横幅关着
   - 做完的收在「已完成 N 项」里
2. **`init_site`**：建好页面树后调 `load_legal_pages`（空页填草稿、有正文的跳过）；最后打印「接下来」三步（建管理员、按上线清单配置、AI 密钥）
3. **AI 审核**：`moderation.services.disabled_reason()`（没设密钥 / 开关关着）显示在「内容审核」页顶；`try_connection()` 和「试一下」按钮：发一句固定测试内容，成功写模型、判断、token 数，失败写原因，401/403 提示密钥、404 提示模型或地址；开关关着也能试，算一次调用（`note_usage`），不建记录；没设密钥时不显示按钮
4. **文档**：设计 v6.18（14.1 后台首页、16.4 首次部署第 6–8 步、5.5.4「试一下」）；README（init_site 之后看上线清单、AI 的「试一下」）

改了两条原有测试：`test_legal_pages` 里「不带 --force 不覆盖」那条，因为 `init_site` 现在已经填了草稿，第一次写入改成带 `--force`；`test_prerender` 里「静态页不含登录区」原来查「退出」二字，隐私政策草稿里有「退出所有战队」，改成查退出登录的链接 `href="/accounts/logout/"`（这条改动没有单独做变异）。

## 命令输出

变异（`mutate.py`，14 处）。第一次漏了一处：备份「开了对象存储但没设加密密钥」没被当成未完成的情况，测试没覆盖，补了断言后整组重跑：

```
baseline green, 9 tests
caught mail counts as done without SMTP -> test_mail_is_a_must_until_smtp_is_set
caught blanks in the agreement pass -> test_the_agreements_need_their_blanks_filled
caught the AI check blames the switch for a missing key -> test_ai_says_whether_the_key_or_the_switch_is_missing
caught backup without the key counts as done -> test_suggestions_turn_done
caught nobody in 内容编辑 counts as done -> test_suggestions_turn_done
caught the test banner never shows up -> test_suggestions_turn_done
caught no checklist on the dashboard -> test_mail_is_a_must_until_smtp_is_set
caught everyone sees the checklist -> test_only_superusers_see_the_checklist
caught init_site leaves the agreements empty -> test_init_site_fills_the_agreements_and_says_what_is_next
caught init_site says nothing about what is next -> test_init_site_fills_the_agreements_and_says_what_is_next
caught trying the AI is not counted -> test_trying_the_ai_reports_success_and_counts_the_call
caught a bad key gets no hint -> test_a_bad_key_says_so
caught the page hides why AI is off -> test_without_a_key_the_page_says_why_and_offers_no_try
caught the try button shows without a key -> test_without_a_key_the_page_says_why_and_offers_no_try
restored and green; missed: none
```

整组检查：

```
All checks passed!
297 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
1448 passed in 182.91s (0:03:02)
```

演示站（镜像时间 `2026-10-03 19:21:23 +0200`，全量生成「成功 46，失败 0」）上清单算出来的结果：

```
必做 邮件（SMTP）：还没配置。……
必做 用户协议：正文里还有 4 处【】要社团填写（运营方、联系方式、生效日期等）。
必做 隐私政策：正文里还有 8 处【】要社团填写（运营方、联系方式、生效日期等）。
建议 AI 内容审核：服务器没有设置环境变量 MODERATION_API_KEY（或自建服务的 MODERATION_BASE_URL），……
建议 异地备份：加密密钥已设置，全站设置里「备份上传到对象存储」还没开。
OK 内容编辑：已有人负责。
建议 关于我们：还是空的。……
建议 首页和分享信息：还没填：站点简介、QQ 群链接、首屏图片。……
OK 默认封面和默认头像：图库里有图。
建议 测试环境标记：页面顶部有「测试环境」横幅、禁止搜索引擎收录。……
```

## 没做 / 未验证

- 「试一下」没有接真的 DeepSeek（本机和演示站都没有密钥），成功和 401 两种情况用替身测的
- 「关于我们」没有给草稿：内容是社团自己的介绍，清单只提醒
