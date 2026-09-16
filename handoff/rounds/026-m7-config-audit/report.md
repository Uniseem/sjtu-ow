# 026 实现报告

> 本轮由实现方（Claude）自己做，用户外出。下面所有输出都是真实跑出来的。

## 结论

**完成。** 附录 C 的 60 多行参数表逐条对过：**代码常量和 `settings` 全部对得上**，`SiteSettings` 的默认值也对得上。

**只有一处不符，而且是我自己在 019 和 020 轮写坏的**：邮件主题硬编码了前缀，导致实际发出去的主题是 `[SJTU OW] [交大守望先锋] ...`，双前缀，而且无视管理员在后台配的前缀。已修。

## 唯一的不符：邮件主题双前缀

### 现象

附录 C：`邮件主题前缀 | [SJTU OW] | 后台`。

`core/mail.py` 在发信时统一加前缀：

```python
def apply_subject_prefix(subject, prefix=None):
    prefix = (prefix if prefix is not None else get_subject_prefix()).strip()
    if subject.startswith(prefix):
        return subject
    return f"{prefix} {subject}".strip()
```

所以别的应用都写裸主题：

```python
subject="赛事已取消"            # tournaments
subject="报名状态有更新"         # tournaments
```

但我在 019 和 020 轮写的三处自带了前缀：

```python
f"[交大守望先锋] 内战提醒：{scrim.title}"
f"[交大守望先锋] 内战已取消：{scrim.title}"
f"[交大守望先锋] Webhook 投递失败：{client.name}"
```

实际效果：

```
别的应用（写裸主题）:
    [SJTU OW] 内战提醒：周五内战

我在 019/020 写的（自带前缀）:
    [SJTU OW] [交大守望先锋] 内战提醒：周五内战
```

`startswith` 那个判断挡不住，因为硬编码的前缀和配置的前缀不是同一个字符串。

### 影响

1. 主题里有两个前缀，难看。
2. **管理员在后台改了前缀，这三封信不跟着变**——后台设置对它们无效。
3. 它们说的是「交大守望先锋」而不是站点配置的名字，两套叫法并存。

### 修法

三处都改成裸主题，并在两个模块的 docstring 里写明「不要自己加前缀，`core.mail` 会加」。

### 为什么测试没发现

020 的测试写的是：

```python
assert scrim.title in mail.outbox[0].subject
```

加不加前缀它都通过。**又是「断言的对象不是真正要保证的那件事」**——这已经是第四次了（019 文档页 200 但空白、021 穷举只用一个种子、023 首页体积只量了 HTML）。

补了三条测试：
- 扫描所有 `notifications*.py`，**主题字面量里不许以 `[...]` 开头**
- 前缀只加一次，重复调用不叠加
- 真发一遍内战提醒和取消，检查最终主题

把硬编码前缀改回去做变异测试，第一条立刻红。

## 逐条比对结果

### `settings` 常量

| 参数 | 设置项 | 实际 | 文档 |
|---|---|---|---|
| API 时间戳允许偏差 | `API_TIMESTAMP_TOLERANCE` | 300 | 300（5 分钟）✓ |
| API Nonce 有效期 | `API_NONCE_TTL` | 600 | 600（10 分钟）✓ |
| 会话有效期 | `SESSION_COOKIE_AGE` | 1209600 | 1209600（14 天）✓ |
| 图片上传上限 | `WAGTAILIMAGES_MAX_UPLOAD_SIZE` | 5242880 | 5MB ✓ |
| 本地备份保留 | `BACKUP_KEEP_DAYS` | 14 | 14 ✓ |
| 旧静态资源保留 | `STATIC_KEEP_DAYS` | 30 | 30 ✓ |

### 代码常量

| 参数 | 实际 | 文档 |
|---|---|---|
| 批量审核每次上限 | 100 | 100 ✓ |
| API 列表每页默认 / 最多 | 50 / 200 | 50 / 200 ✓ |
| Webhook 超时 | 10 | 10 秒 ✓ |
| Webhook 共尝试次数 | 8 | 8 ✓ |
| Webhook 重试间隔 | `[60, 300, 1800, 7200, 21600, 43200, 86400]` | 1 分、5 分、30 分、2 时、6 时、12 时、24 时 ✓ |
| 单个字体文件上限 | 31457280 | 30MB ✓ |
| 常用汉字每片字数 | 200 | 200 ✓ |
| 其余字符每片字数 | 600 | 600 ✓ |
| 处理中超时判定 | 1800 秒 | 30 分钟 ✓ |
| 旧字体样式表保留 | 1 天 | 1 天 ✓ |
| API 调用日志保留 | 90 | 90 天 ✓ |
| Webhook 记录保留 | 180 | 180 天 ✓ |
| 任务记录保留 | 30 | 30 天 ✓ |
| AI 审核记录保留 | 180 | 180 天 ✓ |
| 内战列表已结束范围 | 30 | 30 天 ✓ |
| 状态片段限流 | 120 | 120 次/IP/分钟 ✓ |

### `SiteSettings`（后台可改的）默认值

| 参数 | 实际 | 文档 |
|---|---|---|
| 邮件主题前缀 | `[SJTU OW]` | `[SJTU OW]` ✓ |
| 每人最多游戏 ID | 5 | 5 ✓ |
| 战队人数上限 | 10 | 10 ✓ |
| 每人最多担任队长 | 3 | 3 ✓ |
| 每人最多未过期车帖 | 3 | 3 ✓ |
| 车帖过期时间 | 2 小时 | 2 小时 ✓ |
| 内战提醒时间 | 2 小时 | 开始前 2 小时 ✓ |
| AI 审核每日上限 | 2000 | 2000 ✓ |

**除了邮件前缀那一处，全部对得上。**

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
204 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ uv run python -m pytest -q
542 passed in 40.20s

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

本轮新增 6 个测试。

## 顺带做的

025 的 review 里建议「给开发库也来一份备份」，这轮做了：

```
$ uv run python manage.py backup --output backups/dev
已备份到 backups/dev/sjtu-ow-20260916-230903.tar.gz（0.1 MB）
```

`backups/` 已经在 `.gitignore` 里（022 加的），不会进仓库。

## 未完成 / 不适用

附录 C 里这些没法用测试固定，原因写在这里：

- **服务器地区、API 旧版本保留、典型文章页字体下载量**——不是代码里的值。
- **allauth 的验证码有效期、尝试次数、发送频率**——文档写的是「使用 allauth 默认值」，我们没有覆盖，跟着上游走就是符合。
- **Caddy 的两条缓存策略**——在 `Caddyfile` 里，023 核查过（`max-age=31536000, immutable` 和 `max-age=300, must-revalidate`）。
- **cron 相关的三条**——在 `deploy/crontab.example` 里，022 核查过。

## 需要确认

无新增。前面几轮的五个问题仍未定。

## 改动文件

```
scrims/notifications.py             去掉硬编码前缀，docstring 说明原因
integrations/notifications.py       同上
core/tests/test_chapter15_audit.py  新增 6 个测试：前缀不许硬编码、前缀只加一次、
                                    settings / 代码常量 / SiteSettings 三组默认值
```
