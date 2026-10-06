# 211 复核结果（自查）

## 结论

自查通过。连做轮次，等独立复核后按 `REVIEW-GUIDE.md` 追加结论。

## 验证记录

- **根因不靠猜**：测试机 4 条 `no such column` 失败，先在本地按分片顺序连跑「backoffice 迁移测试 + held_letters 测试」复现出同一报错，再动手修；修完同一组合转绿。
- **变异验证 7 处全部被抓**：失败不缓存、`?bvid=` 不校验、`find_embed` 丢 `cache_until`、文章 save 不重算、搜索改回现场渲染、赛事 save 不重算、迁移测试不留最新（守卫抓到，报错列出 content.0010–0012 三个待回放迁移）。
- **逐行重读关键 diff**（写报告后换角度又过了一遍）：
  - `remember_failed_lookup` 用 `update_or_create` + `get_embed_hash`，和 Wagtail `get_embed` 读写同一行；`find_embed` 补 `"cache_until": None`，否则失败行的旧 `cache_until` 会让后来的成功结果永远显得过期——这条是新测试 `test_a_failed_lookup_is_retried_once_the_hour_passes` 盯着的。
  - `search/services.py` 原来 `plain(plain_text(body))` 里的 `plain()` 是折叠空白；新代码直接用 `body_plain`（带换行）。核对过：搜索词按空白切开、每个词本身不含空白（`_terms` 用 `split()`），逐词子串匹配不受换行影响；摘要处的 `excerpt()` 自己还会折叠一遍。匹配行为不变。
  - 三个模型的 `save()`：`update_fields=None` 或含源字段时重算并把派生字段并入 `update_fields`，其它 `update_fields` 不动派生字段；去重保持顺序。
- **整组检查在测试机**：1912 条分 4 片全绿，ruff / Tailwind / makemigrations --check / check --deploy / 错误页一致性 / Docker 构建全部通过（原始输出在 report.md「验收输出」）。

## 发现的问题

- **迁移测试不留最新表结构**（必须修，本轮已修）：`test_the_migration_turns_the_introduction_and_its_drafts_into_markdown` 把 content 停在 0009、`test_the_migration_carries_the_old_environment_in` 把 core 停在 0021。129 起三条同类测试都有 `finally` 回放，这两条漏了；以前没炸是因为 0010/0011 没加列，本轮 0012 第一个加。已补回放并在 conftest 加常驻守卫（`transaction=True` 测试结束时断言没有待应用的迁移）。教训一条：守卫里用的 `MigrationExecutor` 要在 conftest 导入时就绑定真类——有测试会把这个类打桩，夹具拆除顺序不保证桩先撤。
- **建议修（留给后面轮次）**：变异时用 heredoc 改文件没匹配上目标字符串造成一次假绿，以后变异一律用编辑工具；这条写进报告了，不用再开工。

## 判断里最没把握的

- 守卫给每个 `transaction=True` 测试加了一次迁移计划计算。整组时长没涨（分片 1 分 57 秒–2 分 13 秒，和上轮相当），但普查在测试机上同时跑，等普查结束后再看一次时长确认没有变慢。
- `body_plain` 等三个字段在 Wagtail 修订（revision）里的快照是保存时的值，恢复旧修订再发布会重新算，行为正确；但没有专门测「恢复旧修订」这条路——现有发布路径测试（`test_the_counts_are_stored_at_publish_and_recounted_at_republish`）覆盖了同一入口 `save()`。

## 文档更新

- `docs/design.md`：v7.14（头部版本、5.2 视频行、13.16 末条、12.5.1/12.8.1/12.9.1 字段表、附录 D 一行）
- `docs/design-details.md`：6.3 末条改写、版本行提 211
- `handoff/STATUS.md`：211 段落、next 改写
- 轮次目录：request.md / report.md / review.md（本文件）
