# 212 实现报告

## 结论

完成。210 复核（`rounds/210-full-review/review.md`）建议顺序第 1 步的八条自动保存收尾（T1、A1、A3、F2、F4、B6、D3、D2）全部修好；复核要求连带查的 `ScrimForm` 查过，没有同类问题。新增 18 条测试全绿；10 处变异全部被抓到（改回后基线全绿）；测试机整组检查 1930 条全绿。210 的尾巴一并收了：守卫普查完整结果取回（299 个守卫，265 被抓到、34 survived），写进 210 review.md 末尾的「212 轮补充」，逐条判断排进 213。正式站已升级（上次升级是 209，这次把 211、212 一起带上，升级前备份）。

## 逐条结果

1. **T1、A3 的根因（跨字段规则落错字段时照样落库）**：`core/autosave.py` 的 `valid_changes` 重写。原来只在 `NON_FIELD_ERRORS` 时才看 `autosave_together`，而 v7.10 起跨字段规则落在单个字段上——那段是死代码。现在 `autosave_together` 按**分组**解释（`_together_groups`：裸字符串是一字段组，元组是多字段组）：表单级错误又没登记组时什么都不存（原行为）；组内任一字段有错误时整组这次不存，无论规则报在表单上还是组里某个字段上。`TournamentForm.autosave_together` 照两条独立规则拆成两组（报名开始/截止一组、人数上下限一组）——合并成一组会互相误伤，206 的旧测试 `test_a_copy_keeps_what_it_copied_when_a_field_is_wrong` 在合并写法下红了，照它拆的。
2. **连带查 `ScrimForm`**（复核 T1 的要求）：`Scrim` 模型无跨字段约束、表单无 `clean`，没有同类问题。
3. **A1（联系方式改类型 500）**：`ContactMethodForm.clean()` 查同用户同类型冲突（`(user, type)` 唯一约束里的 `user` 不在表单上，`is_valid()` 查不到它），错误落在 `type` 上，自动保存和整张提交都不再 500；`save` 里的 `full_clean()` 留作兜底。`autosave_together` 改为一组 `("type", "value")`（A3：只改类型、内容不匹配新类型时整组不存，库里不会再出现「微信 12345」）。连带修：`ContactMethod.clean` 开头 `if self.type not in ContactType.values: return`——type 自身有错被踢出 cleaned_data 时，不再给 value 级联加「未知的联系方式类型」（这是测试机上 `core/tests/test_client_ip.py::test_a_whole_form_error_shows_once` 红出来才抓到的，本地子集没覆盖到）。
4. **F2（失败后每 5 秒无限重试）**：`static/js/autosave.js`：401/403/404 和「200 但不是 JSON」（被跳去登录页）算**永久失败**——不重试，状态栏写「保存失败：登录状态已失效或没有权限，重新登录后再改」，且不算 pending、不拦 `beforeunload`；网络错误、5xx、429 退避重试，5 秒起步逐次翻倍、封顶 60 秒（`RETRY_MAX`），存好归零；表单里有已选文件（`fileChosen()`，队标）不自动重试，写「保存失败，再改一次会重新尝试」。另：`apply()` 里 saved 为空且有错误时状态文案改「没有保存：」（原来一律写「其余已保存」，在 D3 整次拒绝的场景自相矛盾）。
5. **F4（密钥明文留在框里、每次保存重发）**：`backoffice/views/settings.py` 的自动保存响应把存过的密钥字段（`core/forms.py` 的 `SECRET_FIELDS`）放进 `values[name] = ""`，客户端保存后清空框里的明文。
6. **B6（新建第一次改动有错就不建行）**：`backoffice/views/categories.py`、`backoffice/views/members.py` 的新建分支改用 `autosave.new_from_valid_fields`：有错的那几项不存、其余照存、行照样建起来、`location` 照回编辑地址（分组的成员块照旧随 `replace` 带上）。
7. **D3（两人同时改同一篇互相顶掉）**：`content/drafts.py` 新增 `STALE_MESSAGE`（「另一个人在你打开以后改过这篇，你的改动没有存；刷新页面看一看现在的内容，再重新改。」）和 `stale_base(page, request)`：POST 带 `latest_revision` 且和 `page.latest_revision_id` 不一致就拒绝；没带不拦（旧页面、还没建行的文章兼容）；非数字当拒绝。文章（`articles.py` 的 `_autosave` 和 `_submit`——发布路径 stale 时不存草稿也不发布）、网站页面、首页置顶、栏目介绍（`pages.py` 三处，自动保存和整张提交都算）都接上；存好后回 `values["latest_revision"]`，页面不刷新接着改；新文章第一次创建后由 values 回填隐藏框。三个模板（article_edit、page_edit、draft_form）加隐藏框，新文章时 value 为空。
8. **D2（删分类不数草稿修订）**：`content/services.py` 新增 `category_use_counts()` / `category_in_use()`——页面行 ∪ 最新修订 ∪ 排了定时上线的修订（`Revision.content` 是 JSONField，`content__category=pk` 查；修订里的分类覆盖页面行的取值，每页只算一次）。分类列表（替换原来的 `Count("articles")` 注解）、编辑页、删除三处都改用它；删除提示语改成「还有 N 篇文章（含草稿）在……」。
9. **测试**（新增 18 条，全绿）：`core/tests/test_autosave.py` +6（组规则单测、A1 撞类型不 500、A3 类型不单存、F4 密钥清空、B6 分类、B6 分组）、`core/tests/test_autosave_events.py` +3（改开始时间越过截止整组不存、复制路径不再 500、人数下限超上限整组不存）、`core/tests/test_autosave_js.py` 新建 4 条（F2 子串守卫，弱点见「顺带发现」）、`content/tests/test_drafts.py` +3（两人交替编辑拒绝、整张提交拒绝 + 非数字修订号拒绝、网站页面和置顶拒绝）、`content/tests/test_category_delete.py` +2（仅草稿引用的分类删不掉、定时上线修订也算在用）。另改 `test_drafts.py` 里 `test_the_address_follows_the_title_until_published` 的 values 精确断言（values 现在多带 latest_revision）。
10. **变异验证**：`mutate.py` 10 处全部被抓到（输出见下）。脚本先跑基线红了就停（083 的教训）；恢复后清 `__pycache__`（027 的坑）。

## 验收输出

本地五个相关测试文件：`58 passed in 6.82s`。`uv run ruff check . && uv run ruff format --check .`：All checks passed，404 files already formatted。

变异验证（`uv run python handoff/rounds/212-autosave-fixes/mutate.py`，2026-10-06 本机）：

```
基线全绿，开始变异。
ok T1/A3: autosave_together 组扩展：改坏后红了（5 条）
ok A1: ContactMethodForm 的同类型冲突检查：改坏后红了（1 条）
ok A1 连带：类型自身有错时不再给内容加「未知类型」：改坏后红了（2 条）
ok F2: 退避封顶（子串守卫）：改坏后红了（1 条）
ok F2: 永久失败不再拦住离开（子串守卫）：改坏后红了（1 条）
ok F4: 保存后清空密钥框：改坏后红了（1 条）
ok B6: 新建分类有错也建行：改坏后红了（1 条）
ok B6: 新建成员分组有错也建行：改坏后红了（1 条）
ok D3: 修订号不一致就不存：改坏后红了（3 条）
ok D2: 删分类计数算上修订：改坏后红了（2 条）
改回后基线全绿。
```

测试机整组检查（`bash scripts/remote-check.sh`，服务器时间 2026-10-06 20:13–20:14，日志 `/srv/sjtu-ow-check/runs/20261006-201308-afc9ee9.log`）：

```
== ruff (12:13:27)
All checks passed!
404 files already formatted
== Tailwind (12:13:27)
Built production stylesheet '/srv/sjtu-ow-check/repo/static/css/app.css'.
== pytest (12:13:29)
1930 条测试分成 4 片
分片 1：483 passed in 55.59s
分片 2：483 passed in 54.02s
分片 3：482 passed in 58.17s
分片 4：482 passed in 60.16s (0:01:00)
== 迁移 (12:14:34)
No changes detected
== 生产配置 (12:14:35)
System check identified no issues (0 silenced).
== 错误页和模板一致 (12:14:36)
== Docker 镜像 (12:14:37)
构建成功：cc358e499863
== 全部通过 (12:14:37)
```

正式站升级（2026-10-06 22:23 北京时间）：先 `backup`（`sjtu-ow-20261006-202314.tar.gz`，210.8 MB；异地备份未开启，命令照常提醒），ship212（40 个文件，含 211 的改动，209 以来没升过）上传后 `deploy_ship.sh 212`：镜像重建、迁移应用（0012、0015、0005）、`prerender` 全量生成成功 12 失败 0、healthz `ok`；`migrate --check` 干净；本机访问首页 HTTP 200、CSP 头照旧。

## 设计偏差

无。文档先改（design.md v7.15：13.17 的失败重试政策、跨字段分组、草稿修订号、新建有错也建行、密钥存后清空，5.3 的「草稿按草稿修订算」计数定义，附录 D 记版本），实现照文档。

## 未完成 / 顺带发现 / 需要确认

- **210 报告 T9 说的「删掉 `autosave_together` 四行不红」现在红了**：变异 1 拆的就是这段逻辑，5 条测试跟着红。
- **JS 子串测试的弱点（F8）依旧**：`test_autosave_js.py` 的 4 条断言的是源码子串，不能证明浏览器里的真实行为；F8 本身不在本轮范围，本轮按 request 沿用子串方式。
- **210 守卫普查结果已取回**：299 个守卫，265 被抓到、34 survived，逐条在 `rounds/210-full-review/results.jsonl`、日志 `sweep-log.txt`，review.md 末尾加了「212 轮补充」。survived 的大多是权限门和逐对象权限（`placed`、`manager_required`、`superuser_required`、文章/页面/图片的 `can_*`——即 B3 说的那类），逐条判断排进 213（正好是权限和状态守卫轮）。普查跑的是 210 的代码快照（1902 passed, 2 deselected）。
- **STATUS.md 轮次记录表缺 211 一行**（211 提交时漏加），本轮补上。
- 210 复核的其余条目照旧排队：213 权限和状态守卫（S1、S7、S2、S3、T2、T7、A8、A9、B3 + 普查 34 条），214 worker 和日志（C1–C3），215 Caddy 和预渲染（C4、C5、C6、C9、F1）；A2、A12、T7、B11 等用户拍板。

## 改动文件

代码：`core/autosave.py`、`accounts/forms.py`、`accounts/models.py`、`backoffice/forms.py`、`backoffice/views/articles.py`、`backoffice/views/pages.py`、`backoffice/views/categories.py`、`backoffice/views/members.py`、`backoffice/views/settings.py`、`content/drafts.py`、`content/services.py`、`static/js/autosave.js`

模板：`backoffice/templates/backoffice/content/article_edit.html`、`page_edit.html`、`draft_form.html`

测试：`core/tests/test_autosave.py`、`core/tests/test_autosave_events.py`、`core/tests/test_autosave_js.py`（新）、`content/tests/test_drafts.py`、`content/tests/test_category_delete.py`

文档：`docs/design.md`（v7.15）；`handoff/rounds/210-full-review/review.md` 末尾追加普查结果补充（附 `results.jsonl`、`sweep-log.txt`）；`handoff/STATUS.md`；轮次目录 `handoff/rounds/212-autosave-fixes/`
