# 130 投稿者的编辑页去掉「推荐」标签页（报告）

## 做了什么

1. `content/forms.py`：
   - `EDITOR_ONLY_FIELDS`（slug、seo_title、search_description、show_in_menus、go_live_at、expire_at）。`submits_for_review(user)` 的人，表单里去掉这些字段；没有字段的面板不显示，「推荐」标签页就没了
   - `clean()`：表单里没有 slug、实例也还没有 slug（新稿）时，由 `_free_slug()` 按标题选一个：`slugify(allow_unicode=True)`，保留词加 `-article`，`Page._slug_is_available` 不通过就加 `-2`、`-3`
2. `content/tests/test_submitter_editor.py`（3 条）：表单拿网页上渲染出来的数据提交（`wagtail.test.utils.form_data.querydict_from_html`，正文是脚本画的，`body-count` 手动补 0），走真实的新建、编辑视图
3. 设计 v6.25（14.3），文档头部版本号从 v6.23 改到 v6.25
4. 127 的更正：README 改成「内容编辑（和超级管理员）能发」；127 的 request、report、review 和 STATUS 里的 127 段落加了更正说明，原文不删

## 命令输出

变异（测试机，6 处，第一次全部被抓到）：

```
baseline green, 3 tests
caught submitters keep the promote fields -> test_only_editors_and_authors_get_the_promote_fields
caught the schedule stays -> test_only_editors_and_authors_get_the_promote_fields
caught Wagtail picks the address -> test_reserved_and_taken_addresses_step_aside
caught the address is picked again on every save -> test_the_address_comes_from_the_title_and_survives_the_writer
caught reserved words are not stepped round -> test_reserved_and_taken_addresses_step_aside
caught taken addresses are not stepped round -> test_reserved_and_taken_addresses_step_aside
restored and green; missed: none
```

整组检查（测试机）：

```
1499 条测试分成 4 片
分片 1：375 passed in 33.74s
分片 2：375 passed in 37.81s
分片 3：375 passed in 36.26s
分片 4：374 passed in 34.50s
== 迁移 (20:02:25)
No changes detected
== 生产配置 (20:02:26)
System check identified no issues (0 silenced).
== 错误页和模板一致 (20:02:27)
== Docker 镜像 (20:02:28)
构建成功：d412829ddfb0
== 全部通过 (20:02:28)
```

演示站升级：

```
  No migrations to apply.
全量生成完成：成功 46，失败 0，删除 0；目录占用 1606 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

## 没做 / 未验证

- 赛事管理员、内战管理员（他们的文章也要过审）同样看不到这一页，按「要过审」划线，没有单独区分
- 没在浏览器里看投稿者的编辑页（演示站上没有投稿者账号可用，测试里断言了页面上没有这些输入框）
- 「推荐」这个标签名（Wagtail 中文翻译，原文 Promote）对编辑来说也不直观，没改
