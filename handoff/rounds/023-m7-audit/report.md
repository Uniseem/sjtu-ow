# 023 实现报告

> 本轮由实现方（Claude）自己做，用户外出。下面所有输出都是真实跑出来的；没跑的会写「未验证」。

## 结论

**完成。** 第 15 章逐条核查完毕，能测的都写成了测试（新增 22 个）。

**最重要的产出不是核查表，而是查清了一个从 013 轮就存在的「偶发测试失败」——它其实是一个真实的产品缺陷**：同一个字体切片两次会得到不同的字节，导致内容哈希去重完全失效。013 轮我把它记成「如果再次出现，必须查清楚，不要当成噪音」，这轮它出现了，查清了，修了。

## 15.1–15.5 逐条核查表

### 15.1 性能

| 要求 | 结论 | 依据 |
|---|---|---|
| 列表页避免 N+1，开发时开查询计数检查 | **原本缺失，已补** | 之前一条这样的检查都没有。新增 5 个页面的查询计数测试（见下表） |
| 首页 HTML+CSS+JS 压缩后 ≤ 300KB | **符合** | 实测 59.6KB |
| 图片按尺寸生成缩略图、WebP | 符合 | Wagtail 的 `{% image %}` 负责，006 轮验过 |
| Caddy 开 HTTP/2、HTTP/3、压缩 | **符合** | `encode gzip zstd`；HTTP/2 和 HTTP/3 是 Caddy 2 服务 HTTPS 时的默认行为 |
| 静态文件长期缓存 | **符合** | `Cache-Control: public, max-age=31536000, immutable`，并 `precompressed br gzip` |
| 各项响应时间目标 | **未验证** | 需要真实服务器和真实负载，开发机上量没有意义 |
| 分队生成 1 秒内 | **符合** | 021 实测最坏 275ms，有测试守着 |

**N+1 查询实测**（数据从 3 条加到 10 条，查询数不增长）：

| 页面 | 3 条数据 | 10 条数据 |
|---|---|---|
| `/teams/` | 3 次查询 | 3 次查询 |
| `/_fragments/lfg/` | 2 次查询 | 1 次查询 |
| `/tournaments/` | 3 次查询 | 2 次查询 |
| `/scrims/` | 3 次查询 | 2 次查询 |
| `/scrims/<id>/`（报名名单） | 5 次查询 | 4 次查询 |

数据变多查询数反而略降，是因为第二次量的时候一些缓存已经热了。关键是**不随数据量增长**。

测试断言的是「10 条的查询数 ≤ 3 条的」，不是写死一个数字——写死会因为无关改动天天红。

**首页体积明细**：

| 资源 | 压缩后 | 原始 |
|---|---|---|
| HTML | 1.9K | 6.1K |
| `css/app.css` | 16.9K | 110.7K |
| `js/state.js` | 0.7K | 1.5K |
| `vendor/htmx.min.js` | 16.2K | 50.0K |
| `vendor/alpine.csp.min.js` | 23.0K | 69.4K |
| `js/app.js` | 0.9K | 2.3K |
| **合计** | **59.6K** | 240.0K |

预算 300K，用了两成。

### 15.2 安全

| 要求 | 结论 | 依据 |
|---|---|---|
| 全站 HTTPS + HSTS | 符合 | `SECURE_HSTS_SECONDS=31536000`、`INCLUDE_SUBDOMAINS`、`PRELOAD` 都开 |
| Cookie `Secure`/`HttpOnly`/`SameSite=Lax` | 符合 | 生产 `SESSION_COOKIE_SECURE`、`CSRF_COOKIE_SECURE` 为真；`SAMESITE="Lax"` |
| CSRF 保护，HTMX 带 token | 符合 | 前几轮验过，本轮未重复 |
| 模板自动转义、富文本白名单、上游 `description_html` 过滤 | 符合 | 018 的 `sanitize.py` 有测试 |
| 前台禁止内联脚本和 eval | **符合** | `script-src: ['self']`，无 `unsafe-inline`、无 `unsafe-eval`；另测了首页 HTML 里没有带内容的内联 `<script>` |
| `frame-src` 只允许 B 站 | **符合** | 外部源只有 `https://player.bilibili.com`；`frame-ancestors: none` |
| Argon2 + 密码强度校验 | 符合 | 004 轮 |
| allauth 限流（登录、注册、验证码、找回密码） | **符合** | 五个流程都配了，有测试 |
| 业务限流的四个具体数字 | **全部对得上** | 发车 10/人/小时、入队申请 20/人/天、建队 3/人/天、状态片段 120/IP/分钟 |
| 只允许 JPG/PNG/WebP，不允许 SVG | **符合** | `WAGTAILIMAGES_EXTENSIONS = ['jpg','jpeg','png','webp']`，连 GIF 都排除了；上限 5MB |
| 预渲染页面不含个人信息和 CSRF token | **符合** | 真生成一遍首页，搜不到 `csrfmiddlewaretoken`、昵称、邮箱 |
| 字体：fontTools 解析、拒绝禁止嵌入、下载只允许 HTTPS 非内网 | 符合 | 008/009，022 抽到 `core/net.py` 共用 |
| AI 审核的提示注入防护 | 符合 | 011 轮；本轮复验了「不给工具」和 `strict` 输出 |
| 开放 API 签名、Nonce、范围、限流、不返回联系方式 | 符合 | 017/018 |
| Webhook 只允许 HTTPS 非内网 | 符合 | 019，生产拒绝开发开关 |
| 密钥只在环境变量、SMTP 密码和 API 密钥加密存储 | 符合 | 004/017 |
| 备份加密后才外传 | **不符合** | **022 明确记着：没做。上线前必须补** |
| 日志不记密码、验证码、联系方式、Cookie、请求体 | **符合** | 全仓 19 处 `logger.*` 调用逐条看过，唯一涉及收件人的那条特意不写地址；`ApiRequestLog` 没有 body/headers 字段（有测试） |
| 依赖定期更新 | **不适用** | 运维习惯，不是代码 |

### 15.3 隐私

| 要求 | 结论 | 依据 |
|---|---|---|
| 最少收集 | 符合 | 只有邮箱、昵称、游戏 ID、段位、联系方式 |
| 注册记录同意时间 | 符合 | `agreed_terms_at`、`agreed_cross_border_at` |
| 联系方式只有赛事和内战管理员能看 | **符合（且更严）** | 赛事后台走 `can_see_contacts()` 判断；**内战后台目前根本不显示联系方式**，比要求更严。公开页面搜不到（有测试） |
| 不通过 API 提供给上游 | 符合 | 018 验过全部接口 |
| AI 只发公开内容，不发邮箱/联系方式/游戏 ID/用户 ID | **符合** | 本轮复验了实际构造的请求体 |
| 隐私政策正文、账号注销渠道 | **未完成** | 正文要用户写，注销方式设计第 19 章列为待定 |

### 15.4 可用性与数据安全

| 要求 | 结论 |
|---|---|
| 数据丢失上限 24 小时（每日备份） | 命令已有（022），**但异地备份没做**，服务器没了就全没了 |
| 4 小时内在新服务器恢复 | **未验证**，要真机演练 |
| 每学期一次恢复演练 | 022 在开发机上做过一次完整演练 |

### 15.5 日志保留期

| 日志 | 要求 | 结论 |
|---|---|---|
| API 调用日志 | 90 天 | **符合**（`API_LOG_DAYS = 90`） |
| Webhook 投递记录 | 180 天 | **符合**（`WEBHOOK_DAYS = 180`） |
| 任务队列记录 | 30 天 | **符合**（`TASK_DAYS = 30`） |
| AI 审核记录 | 已处理 180 天、未处理一直留着 | **部分符合**：清理任务根本不碰审核记录，所以「未处理的一直留着」成立，但「已处理的 180 天后删除」**没有实现**。加了测试固定住「不删未处理的」，180 天那半留给后续 |
| 报名状态日志、Wagtail 操作日志 | 永久 | 符合（没有任何地方删它们） |
| 访问日志、应用日志 14 天 | **不适用** | 由 Caddy 和 Docker 的日志轮转负责，不是应用代码 |

## 顺带查清的：013 轮那个「偶发失败」

`test_reprocess_clears_old_slice_files` 从 013 轮起偶尔失败，当时没查出来，我在 review 里写了「**如果再次出现，必须查清楚，不要当成噪音**」。这轮的全量回归里它又失败了，于是查了。

失败信息是关键：

```
At index 0 diff: 'fonts/9002/400-000.900391ef.woff2' != 'fonts/9002/400-000.7b888487.woff2'
```

同一个字体、同样的字符集，切两次得到**不同的内容哈希**。直接验证：

```
第 1 次前三个 slice 哈希: ['9683c8ee', 'f85cb7b5', 'eef54dcb']
第 2 次前三个 slice 哈希: ['84f5f67b', '36a1c379', 'a320fcbe']
第 3 次前三个 slice 哈希: ['653788e8', '17b9107f', 'a5ff9eb7']
三次是否完全一致: False
```

逐字节 diff 定位到 `head` 表：

```
不同字节数: 89，首个位置 23，共 344 字节
  表 head 不同（54 vs 54 字节）
  head.modified: 3872414530 3872414531   ← 差一秒
  head.created : 3872414530 3872414530
```

**fontTools 在 `save()` 时默认把 `head.modified` 重写成当前时间**（`recalcTimestamp` 默认为真）。

**这不是测试的问题，是产品缺陷。** 分片文件按内容哈希命名（009 轮的去重机制），所以：

- 每次重新处理字体都会生成**一整套全新的分片文件**
- 旧的全部进入「一天后删除」队列
- 字体 CSS 重新生成，**所有访客重新下载整套字体**
- 一个中文字体动辄几 MB，而服务器在海外——正是设计 15.1 最在意的那种浪费
- 009 轮辛苦做的内容哈希去重，**在重新处理这条路径上从来没生效过**

修法：`TTFont(..., recalcTimestamp=False)`，保留源字体自己的时间戳。修完三次切片完全一致。

加了 `test_slicing_the_same_font_twice_gives_identical_bytes`，中间睡 1.1 秒跨过秒级时间戳。把 `recalcTimestamp` 改回 `True` 做变异测试，这条立刻红。

## 验收输出

### 1. 检查与测试

```
$ ruff check .
All checks passed!

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ uv run python -m pytest -q   （连跑 5 次）
第 1 次：531 passed in 37.76s
第 2 次：531 passed in 38.42s
第 3 次：531 passed in 39.40s
第 4 次：531 passed in 39.73s
第 5 次：531 passed in 40.76s

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

### 2. N+1 测试真的能抓到 N+1

把 `scrims/views.py` 里报名名单的 `select_related("user")` 去掉：

```
AssertionError: /scrims/39/：3 条数据用了 8 次查询，10 条用了 14 次——查询数随数据量增长，说明有 N+1。
```

### 3. 首页体积测试原本是假的

第一版是「用 HTTP 抓每个静态资源，抓不到就 `continue`」。开发环境下静态文件走 404，于是**它只量了 HTML，1.9KB 就通过了**。改成用 staticfiles finders 从磁盘读，抓不到直接断言失败，并断言至少引用了 3 个资源。

### 4. 容器

```
$ docker build -t sjtu-ow:023 .
sha256:2e4bc43d12919cf604f91561c1a5d217b87e3f69ce2c6eb9072dcee8c71df008

$ docker run --rm -v ./deploy:/etc/caddy:ro caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile
Valid configuration
```

修完之后连跑 5 次全量回归，531 个测试全绿，**那个从 013 轮起偶发的失败没有再出现**。

### 5. 清理

本轮没有造持久化的验证数据（测试都用 `tmp_path` 和事务回滚）。全库计数与 022 结束时一致。

## 设计偏差

**没有改设计文档。** 两点说明：

1. **AI 审核记录「已处理 180 天后删除」没有实现**（15.5）。清理任务不碰审核记录。我没有顺手加，因为「已处理」的判定口径（`checked_at`？`handled_at`？人工处理完的标记是哪个字段）需要对着 5.5 节再确认一遍，而这轮是审计不是开发。**记在这里，建议下一轮补。**
2. **响应时间目标没有验证**。开发机上的数字对海外服务器 + 国内访问没有参考价值，只能真机量。

## 未完成 / 不同意

1. **备份加密与异地同步**（022 就记着的缺口，上线阻塞项）。
2. **AI 审核记录 180 天清理**（见上）。
3. 响应时间、国内网络访问、真机恢复演练——都要真实服务器。
4. 隐私政策正文和账号注销渠道——要用户定。

## 需要确认

1. **AI 审核记录的「已处理」以哪个字段为准？** 定了我就能把 180 天清理接进 `cleanup_old_data`。
2. 前面几轮的五个问题仍未定。

## 改动文件

```
core/fonts/processing.py           recalcTimestamp=False —— 修掉切片不可复现的缺陷
core/tests/test_fonts.py           新增切片可复现测试；给老测试加前置断言
core/tests/test_chapter15_audit.py 新增 22 个测试：N+1、首页体积、安全头、限流数字、
                                   上传限制、预渲染无个人信息、联系方式可见范围、
                                   AI 送出内容、日志保留期
core/tests/test_ops_commands.py    022 的写入线程加 daemon 和存活断言，避免泄漏到别的测试
pyproject.toml                     ruff 排除 handoff/（轮次报告里引用的是当时的代码，
                                   包括故意写错的，不该被格式化改写）和 backups/
```
