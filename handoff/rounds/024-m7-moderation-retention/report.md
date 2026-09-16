# 024 实现报告

> 本轮由实现方（Claude）自己做，用户外出。下面所有输出都是真实跑出来的。

## 结论

**完成。** 023 核查里唯一一条「部分符合」补上了：AI 审核记录的 180 天清理。

023 当时把它列成「需要确认」，理由是不知道「已处理」指哪个字段。**读了模型之后发现不需要问**——状态枚举本身就是答案，我不该把一个看代码就能答的问题推给用户。

## 「已处理」的判定

```python
class Status(models.TextChoices):
    PENDING = "pending", "待复核"     # 没人看过 → 永久保留
    OK      = "ok",      "无问题"     # 人看过了 → 180 天
    HANDLED = "handled", "已处置"     # 人看过了 → 180 天
    IGNORED = "ignored", "忽略"       # 人看过了 → 180 天
```

180 天从 `reviewed_at`（复核时间）起算；为空时退回 `created_at`，因为早期记录或数据迁移可能没有复核时间。

## 验收输出

### 1. 检查与测试

```
$ ruff check . && ruff format --check .
All checks passed!
204 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ uv run python -m pytest -q
532 passed in 37.96s

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

本轮新增 4 个测试，并改写了 023 的一条（原来断言「清理任务完全不碰审核记录」，现在只有 `pending` 不碰）。

### 2. 真实数据演示

造 6 条覆盖四种状态和不同时间的记录：

```
  pending  待复核 · 2000 天前
  handled  已处置 · 200 天前复核
  ok       无问题 · 200 天前复核
  ignored  忽略  · 200 天前复核
  handled  已处置 · 100 天前复核
  handled  已处置 · 无复核时间，200 天前创建
```

跑清理：

```
已删除 API 调用日志（90 天前）：0
已删除 Webhook 投递记录（180 天前）：0
已删除 已完成的任务记录（30 天前）：0
已删除 已处理的 AI 审核记录（180 天前）：4
已删除 过期会话：0
```

剩下的：

```
  pending  待复核 · 2000 天前          ← 2000 天了也不删
  handled  已处置 · 100 天前复核        ← 没到 180 天
剩余 2 条
```

三种「已处理」状态都删了，`reviewed_at` 为空的那条按 `created_at` 算也删了，**`pending` 的即使 2000 天前也留着**。

### 3. 变异测试

把「排除 `pending`」这一句去掉，两条测试立刻红：

```
FAILED core/tests/test_chapter15_audit.py::test_unhandled_moderation_records_are_never_cleaned_up
FAILED core/tests/test_ops_commands.py::test_a_pending_moderation_record_is_kept_forever
```

### 4. 清理

演示数据已删，`ModerationItem` 归零。

## 设计偏差

**没有改设计文档。** 一点说明：`reviewed_at` 为空时退回 `created_at`，设计没写这一格。不退回的话，一条没有复核时间的已处置记录会永远留着，和「已处理的保留 180 天」相悖。

## 需要确认

无。023 列的那条已经自己解决了。

## 改动文件

```
core/management/commands/cleanup_old_data.py  新增 handled_moderation()、MODERATION_DAYS
core/tests/test_ops_commands.py               新增 4 个测试
core/tests/test_chapter15_audit.py            改写「清理不碰审核记录」那条
README.md                                     定时维护一节补上审核记录
```
