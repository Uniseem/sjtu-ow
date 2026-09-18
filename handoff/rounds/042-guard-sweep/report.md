# 042 实现报告

## 结论

**未完成，用户叫停。** 218 个守卫跑了 40 个：15 个被抓到，**25 个没被发现**。25 个都逐条看过、定了处理方式（见下），**但还没有补任何测试**。业务代码和测试都没改。

这轮交付的是：

1. 一个能复现的变异脚本 `mutate_guards.py`
2. 前 40 个守卫的实际结果 `results-partial.jsonl`，下面的表就是从它直接生成的
3. 25 个幸存者的逐条判断，下次开工照着补

## 两处更正

**039 表格最后一行是错的。** 它写「不限制每人最多当几个队长 —— 找不到对应代码，没测成」。代码在 `teams/services.py` 的 `max_captained()`，创建（第 85 行）和转让（第 281 行）都检查。当时是搜索词没对上。

**我这轮自己也差点犯同一个错。** 第一版脚本的文件清单是手写的（`services.py`、`api_views.py` 等 49 个），启动后才发现漏了各应用 `wagtail_hooks.py` 里的后台权限检查、接口文档页的超管检查、赛事详情页的「未发布返回 404」。**手写清单就是手挑，只是换了个粒度。** 停下来改成枚举 10 个应用下全部源文件，守卫从 175 个变成 218 个。

## 脚本怎么工作

用 `ast` 找出三种「条件成立就拒绝」的 `if`，把条件换成 `False`：

- 直接子语句有 `raise`
- 直接子语句有 `problems.append(...)` / `errors.append(...)`（报名校验先收集问题再统一抛）
- 直接子语句 `return` 登录跳转、`HttpResponseForbidden` 之类，或任何 `status=4xx` 的响应

每个变异先跑本应用测试（`-x`），没抓到再跑全量。输出**文件:行号、所在函数、原条件源码**，不输出任何人起的名字。

仓库用 `git archive HEAD` 导出 5 份到 scratchpad 并行跑，每份自己的测试库，**真实仓库不被改动**。

## 基线：预判的问题真的出现了

request 里写了「并行负载可能让计时测试偶发失败，把幸存误判成被抓到」。第一次运行的基线：

```
基线（并行负载下，未变异）：
  w0: exit=0 656 passed in 124.56s (0:02:04) []
  w1: exit=1 1 failed, 352 passed in 68.69s (0:01:08) ['FAILED scrims/tests/test_teaming.py::test_6v6_finishes_within_a_second']
  w2: exit=0 656 passed in 124.35s (0:02:04) []
  w3: exit=0 656 passed in 124.86s (0:02:04) []
  w4: exit=0 656 passed in 124.81s (0:02:04) []
基线不绿，变异结果没有意义。
```

5 份里 1 份的 6v6 分队超过 1 秒。**如果没有基线检查，之后所有落到这份副本、恰好在这时跑分队测试的变异，都会被记成「被抓到」。**

全仓库找了一遍墙钟断言（`perf_counter` / `monotonic` / `elapsed`），只有两条：6v6 分队 1 秒内、数据库被锁时 `/healthz` 1 秒内返回。扫描时 `--deselect` 这两条。第二次基线：

```
  w0: exit=0 654 passed, 2 deselected in 145.12s (0:02:25) []
  w1: exit=0 654 passed, 2 deselected in 145.12s (0:02:25) []
  w2: exit=0 654 passed, 2 deselected in 148.35s (0:02:28) []
  w3: exit=0 654 passed, 2 deselected in 146.41s (0:02:26) []
  w4: exit=0 654 passed, 2 deselected in 146.19s (0:02:26) []
```

**代价**：只有这两条测试能抓到的变异，扫描看不见。它们测的是性能，不是守卫，这个代价可以接受。

## 前 40 个的结果

按文件路径排序跑，所以前 40 个是 `accounts`、`content`、`core` 的前半。

| | 位置 | 函数 | 原条件 | 被哪条测试抓到 |
|---|---|---|---|---|
| ✗ | `accounts/forms.py:134` | `GameAccountForm.clean_battletag` | `qs.exists()` |  |
| ✗ | `accounts/models.py:22` | `UserManager._create_user` | `not email` |  |
| ✗ | `accounts/models.py:43` | `UserManager.create_superuser` | `extra_fields.get("is_staff") is not True` |  |
| ✗ | `accounts/models.py:45` | `UserManager.create_superuser` | `extra_fields.get("is_superuser") is not True` |  |
| ✓ | `accounts/models.py:105` | `validate_battletag` | `tag.count("#") != 1` | test_battletag_format_rules |
| ✓ | `accounts/models.py:108` | `validate_battletag` | `" " in name or not name or "#" in name` | test_battletag_format_rules |
| ✓ | `accounts/models.py:110` | `validate_battletag` | `not (2 <= len(name) <= 12)` | test_battletag_format_rules |
| ✓ | `accounts/models.py:112` | `validate_battletag` | `not digits.isdigit() or not (4 <= len(digits) <= 6)` | test_battletag_format_rules |
| ✗ | `accounts/models.py:160` | `GameAccount.clean` | `qs.exists()` |  |
| ✓ | `accounts/models.py:200` | `validate_contact_value` | `not text.isdigit() or not (5 <= len(text) <= 11)` | test_contact_value_validators[qq-1234-False] |
| ✓ | `accounts/models.py:203` | `validate_contact_value` | `not (6 <= len(text) <= 20)` | test_contact_value_validators[wechat-short-False] |
| ✓ | `accounts/models.py:206` | `validate_contact_value` | `not (len(text) == 11 and text.startswith("1") and text.isdigit())` | test_contact_value_validators[phone-23800138000-False] |
| ✓ | `accounts/models.py:209` | `validate_contact_value` | `not text or len(text) > 64` | test_contact_value_validators[other-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-False] |
| ✗ | `accounts/permissions.py:21` | `can_use` | `feature not in Feature.values` |  |
| ✓ | `accounts/ranks.py:32` | `encode_rank` | `tier not in TIER_INDEX` | test_rank_rejects_unknown_values |
| ✓ | `accounts/ranks.py:34` | `encode_rank` | `division not in {1, 2, 3, 4, 5}` | test_rank_rejects_unknown_values |
| ✗ | `accounts/ranks.py:45` | `decode_rank` | `not isinstance(score, int) or score < 0 or score > 39` |  |
| ✗ | `accounts/ranks.py:48` | `decode_rank` | `tier_index not in INDEX_TIER` |  |
| ✓ | `accounts/services.py:105` | `add_game_account` | `user.game_accounts.count() >= max_game_accounts()` | test_game_account_max_from_site_settings |
| ✗ | `accounts/views.py:156` | `me_game_account_delete` | `request.htmx` |  |
| ✗ | `content/embeds.py:74` | `BilibiliEmbedFinder.find_embed` | `_hostname(resolved) not in BILIBILI_HOSTS \| B23_HOSTS` |  |
| ✗ | `content/embeds.py:77` | `BilibiliEmbedFinder.find_embed` | `not bvid` |  |
| ✓ | `content/models.py:96` | `ReservedSlugMixin.clean` | `slug in RESERVED_CHILD_SLUGS` | test_reserved_slug_rejected_on_homepage_children |
| ✓ | `content/models.py:142` | `HomePagePinnedArticle._enforce_pin_limit` | `qs.count() >= MAX_PINNED_ARTICLES` | test_pinned_articles_max_three |
| ✗ | `content/models.py:163` | `HomePage.clean` | `self.pinned_articles.count() > MAX_PINNED_ARTICLES` |  |
| ✗ | `content/services.py:67` | `sync_default_site_from_site_url` | `site is None` |  |
| ✗ | `core/crypto.py:15` | `_fernet` | `not raw` |  |
| ✗ | `core/fields.py:31` | `EncryptedTextField.to_python` | `looks_like_fernet(value)` |  |
| ✗ | `core/fields.py:44` | `EncryptedTextField.get_prep_value` | `looks_like_fernet(value)` |  |
| ✓ | `core/fonts/admin_views.py:41` | `superuser_required.wrapper` | `not request.user.is_superuser` | test_admin_pages_are_superuser_only |
| ✗ | `core/fonts/download.py:55` | `fetch_bytes` | `declared and int(declared) > max_bytes` |  |
| ✗ | `core/fonts/download.py:65` | `fetch_bytes` | `len(data) > max_bytes` |  |
| ✗ | `core/fonts/download.py:67` | `fetch_bytes` | `not data` |  |
| ✗ | `core/fonts/download.py:98` | `fetch_google_css` | `exc.code == 400` |  |
| ✓ | `core/fonts/download.py:130` | `parse_google_css` | `host not in GOOGLE_FONT_HOSTS` | test_google_css_rejects_foreign_hosts |
| ✗ | `core/fonts/download.py:145` | `parse_google_css` | `not faces` |  |
| ✗ | `core/fonts/forms.py:78` | `FontUploadForm.clean_file` | `uploaded.size > processing.MAX_FONT_BYTES` |  |
| ✗ | `core/fonts/forms.py:139` | `FontFaceAddForm.clean_file` | `uploaded.size > processing.MAX_FONT_BYTES` |  |
| ✗ | `core/fonts/forms.py:148` | `FontFaceAddForm.clean` | `not cleaned.get("file") and not cleaned.get("url")` |  |
| ✗ | `core/fonts/processing.py:58` | `inspect_font` | `not data` |  |

## 25 个幸存者的判断

### 要补测试（14 个）

**字段加密（3 个）——最该先补**

| 位置 | 拆掉之后 |
|---|---|
| `core/crypto.py:15` 钥匙为空 | 钥匙变成 `sha256("")`，**一把谁都能算出来的固定钥匙**。SMTP 密码等于明文存储，而且不报错。生产环境 `env(required=True)` 挡在前面，但这是最后一道 |
| `core/fields.py:31` 读出的密文解不开 | 换了钥匙之后，**把密文本身当密码返回**，发邮件时静默用错密码 |
| `core/fields.py:44` 保存解不开的密文 | 把旧密文**再加密一层**存进去，原密码永久丢失 |

后两条防的是同一件事：钥匙变了，数据要大声坏，不能静默坏。

**功能开关（1 个）**

| `accounts/permissions.py:21` 功能名不存在 | 拼错的功能名**默认放行**，那个功能的开关形同虚设 |
|---|---|

**B 站嵌入（2 个）**

| 位置 | 拆掉之后 |
|---|---|
| `content/embeds.py:74` 短链跳到非 B 站域名 | 从别的网站的地址里抠 BV 号。播放器域名是写死的，危害小，但违背设计 5.2「只支持 B 站」 |
| `content/embeds.py:77` 没有 BV 号 | 生成 `bvid=None` 的播放器 |

**字体下载与上传（7 个）**

| 位置 | 拆掉之后 |
|---|---|
| `core/fonts/download.py:55` 声明长度超限 | 不提前拒绝，先下载 30MB 再被第 65 行拒绝 |
| `core/fonts/download.py:65` 实际长度超限 | 没有 Content-Length 时，**超大文件被截断成 30MB 当字体用** |
| `core/fonts/download.py:67` 空文件 | 空字节进入字体解析，报错信息变成解析失败 |
| `core/fonts/download.py:98` Google 返回 400 | 提示从「没有这个字体或字重」变成笼统的 HTTP 400 |
| `core/fonts/download.py:145` 样式表里没有 woff2 | 返回空列表，后面静默生成一个没有分片的字体 |
| `core/fonts/forms.py:148` 既没文件也没地址 | 表单通过，后面的视图拿不到任何字体 |
| `core/fonts/processing.py:58` 空文件 | 同 67，但在上传路径 |

55 / 65 / 67 / 98 可以共用一个假的 `_opener`，传小的 `max_bytes`。

**首页置顶（1 个）**

| `content/models.py:163` 页面 `clean` 检查置顶超过 3 篇 | 后台表单 `max_num` 和子项保存时各还有一道，渲染时也截断。**基本等价**，但直接给页面塞 4 个未保存的子项调 `clean()` 就能测，成本很低 |
|---|---|

### 等价或低价值，不补（11 个）

| 位置 | 理由 |
|---|---|
| `accounts/forms.py:134`、`accounts/models.py:160` 游戏 ID 查重 | **三层**：表单、模型 `clean`、带同样提示文字的数据库约束 `accounts_gameaccount_battletag_ci_unique`。拆任意一层，另外两层给出一样的结果 |
| `accounts/ranks.py:45`、`:48` 段位解码 | 互为兜底。0–39 的整数 `divmod` 后分档一定在表里，**第 48 行实际到不了**；超范围的整数被任意一道拦住。只有传浮点数时有差别，而数据库字段和表单都只产生整数 |
| `accounts/models.py:22`、`:43`、`:45` 用户管理器 | Django 标准模板代码（没邮箱、超管必须是 staff），只在命令行建号时走到 |
| `accounts/views.py:156` 删除游戏 ID 被拦时 `if request.htmx` | 这是在选「返回 400」还是「提示 + 跳转」，**两条路都没删掉**。它不是守卫，是被算子误收的 |
| `content/services.py:67` 没有默认站点 | 拆掉也报错，只是异常类型从 `DoesNotExist` 变成 `AttributeError` |
| `core/fonts/forms.py:78`、`:139` 上传大小 | 读入内存前的提前拒绝，后面 `inspect_font` 有同样的长度检查（`processing.py:60`，还没跑到，**如果它也幸存，这两条要改判**） |

> **051 轮更正**：`processing.py:60` 单独变异后确实幸存（字体测试 36 条全过），所以当时三道 30MB 检查一道都没有测试，上面的「等价」没有依据。051 给 `processing.py:60` 补了测试，之后这两条才真正等价。

## 发现的算子盲区

`accounts/views.py:156` 暴露的：它外面那层 `if blocked:` 才是真正的守卫（有进行中的报名时不许删游戏 ID），但它的拒绝方式是 `messages.error(...)` 加 `return redirect(...)`。**脚本不认识这种形式**——成功路径也是 `redirect`，没法只凭语法区分。

这类守卫要么手动补验，要么扩展算子（比如「body 里先 `messages.error` 再 `return`」）。**还没做。**

## 还没做的

1. **剩下 178 个守卫没跑**：`core` 后半、`integrations`、`lfg`、`moderation`、`scrims`、`sjtu_ow`、`teams`、`tournaments`。脚本目前不支持续跑，重跑会从头开始。时间参考：日志 22:45 开始、23:07 最后一次写入，含约 2.5 分钟基线；幸存者单个约 160 秒（负载下的全量回归），被抓到的多数十几秒。剩下的应用测试密度更高，预计幸存比例会低
2. 上面 14 个要补的测试
3. 补完后逐个变异确认咬得住
4. 「提示 + 跳转」式守卫的手动补验

## 验收输出

这轮没有改业务代码和测试，只新增了脚本和文档。

```
$ ruff check . && ruff format --check .
All checks passed!
209 files already formatted

# handoff/ 在 ruff 的 extend-exclude 里，脚本要单独指定路径检查
$ ruff check handoff/rounds/042-guard-sweep/mutate_guards.py && ruff format --check handoff/rounds/042-guard-sweep/mutate_guards.py
All checks passed!
1 file already formatted

$ python mutate_guards.py --list | tail -1
共 218 个守卫

$ git status --short   # 扫描停止后
?? handoff/rounds/042-guard-sweep/
```

pytest 没有重跑：没有改业务代码和测试。上面第二次基线是在导出的副本里跑的（654 passed, 2 deselected），不是本仓库的验收。

## 改动文件

```
handoff/rounds/042-guard-sweep/request.md
handoff/rounds/042-guard-sweep/mutate_guards.py        新增，变异脚本
handoff/rounds/042-guard-sweep/results-partial.jsonl   新增，前 40 个的原始结果
handoff/rounds/042-guard-sweep/report.md
handoff/rounds/042-guard-sweep/review.md
handoff/rounds/039-mutation-sweep/report.md            加更正说明
handoff/STATUS.md
```
