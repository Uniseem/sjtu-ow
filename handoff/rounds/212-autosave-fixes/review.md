# 212 复核结果（自查）

## 结论

自查通过。连做轮次，等独立复核后按 `REVIEW-GUIDE.md` 追加结论。

## 验证记录

- **变异验证 10 处全部被抓**（`mutate.py`，先跑基线确认绿再变异，083 的教训；恢复后清 `__pycache__`，027 的坑）：组扩展 5 条、A1 表单冲突 1 条、A1 连带 2 条、F2 两处子串各 1 条、F4 1 条、B6 两处各 1 条、D3 3 条、D2 2 条。改回后基线全绿。原始输出在 report.md「验收输出」。
- **逐行重读关键 diff**（写完报告后换角度又过了一遍）：
  - **D3 的发布路径**：`articles.py` 的 `_submit` 在 `form.is_valid()` 之后、存草稿和发布之前查 `stale_base`——stale 时不存草稿也不发布，回错误页；`pages.py` 三处整张提交同样先查 stale 再 `_save`（`_save` 里含发布）。
  - **新文章回填**：`_autosave` 里 `page is None` 跳过 stale 检查（还没有基线可比对），`start_article` 后 `values["latest_revision"]` 把新修订号写回隐藏框；模板里新文章的隐藏框 value 为空，`stale_base` 对空值不拦——两条加起来，新文章第一次创建和旧页面（没有隐藏框）都不会被误拦。
  - **D2 计数**：`category_use_counts` 里修订的取值覆盖页面行的取值（`by_page[object_id] = category_id`），每页只算一次；`Q(pk__in=Subquery(latest)) | Q(approved_go_live_at__isnull=False)` 把「最新修订」和「排了定时上线的修订」都算上。故意改坏修订那一半，两条新测试都红。
  - **JS 失败分类**：401/403/404 直接 permanent；`!response.ok || 非 JSON` 里 `permanent = response.ok`——200 非 JSON（登录页）永久、500 非 JSON 可重试；`save()` 开头 `gaveUp = false`，永久失败后用户再改仍会重新尝试（「重新登录后再改」）。
- **整组检查在测试机**：1930 条分 4 片全绿，ruff / Tailwind / 迁移 / `check --deploy` / 错误页一致性 / Docker 构建全部通过。
- **正式站升级后核过**：`migrate --check` 干净、healthz `ok`、本机访问首页 200、CSP 头照旧。

## 发现的问题

- **必须修，本轮已修**：`ContactMethod.clean` 在 type 自身有错时给 value 级联加「未知的联系方式类型」（测试机整组检查里 `test_a_whole_form_error_shows_once` 红出来抓到的，本地只跑子集时没覆盖）；`TournamentForm.autosave_together` 四条合并成一组会互相误伤（206 的旧测试 `test_a_copy_keeps_what_it_copied_when_a_field_is_wrong` 抓到的）。两处都在实现阶段修掉并进了变异清单。
- **建议修（留给后面轮次）**：F8（JS 子串测试太弱）依旧，本轮 4 条新 JS 测试沿用子串方式，只保证代码里这些分支存在，不保证浏览器行为；`stale_base` 对不带修订号的旧页面不拦（兼容选择）——升级前已经开着的编辑页仍可能互顶一次，刷新后即带号。两条都写进报告了。

## 判断里最没把握的

- `category_use_counts` 每次调用扫一遍文章修订（分类列表、编辑、删除三处各调一次）。分类管理是低频后台页、修订表目前很小，没有加缓存；文章和修订多了以后如果变慢，应先量再加。
- D3 拒绝时表单里用户刚打的字还在页面上（只是没存），提示语让他「刷新页面看一看」——刷新会丢未存的改动。这是有意的（设计 v7.15 的措辞），但没有浏览器走查验证过这段提示在真实页面的样子（JS 弱点同 F8）。

## 文档更新

- `docs/design.md`：v7.15（13.17 四条、5.3 计数定义、附录 D 一行）
- `handoff/rounds/210-full-review/review.md`：末尾追加「212 轮补充」（普查结果取回），附 `results.jsonl`、`sweep-log.txt`
- `handoff/STATUS.md`：212 段落、头部 round/next/updated、轮次表补 211 和 212 两行
- 轮次目录：request.md / report.md / review.md（本文件）/ mutate.py
