# 051 实现报告

## 结论

**完成。** 042 判为真空白的 14 处，加上 042 悬而未决的 `processing.py:60`，一共 15 处各补了一条测试。逐个拆掉这 15 道检查，**全部被抓到**，而且每处都是被专门为它写的那条测试抓到的。业务代码没改。

## 042 的一个判断，这轮落了地

042 把 `core/fonts/forms.py:78`、`:139`（上传时检查不超过 30MB）判为「等价」，理由是后面 `inspect_font` 里还有同样的检查（`processing.py:60`）。**但那一道当时没跑到。** 这轮先单独拆它：

```
core/fonts/processing.py 60 inspect_font if len(data) > MAX_FONT_BYTES
变异 processing.py:60 → 36 passed in 2.04s
已还原: True
```

没被发现。也就是说，**三道「不超过 30MB」的检查一道都没有测试**，042 的「等价」判断依据不成立。补上 `processing.py:60` 的测试之后，另外两道才真正是等价的：拆掉它们，文件照样会在 `inspect_font` 被拒绝，只是多读一次内存。

## 每条测试怎么构造的

难点是**只让要测的那道闸起作用**。如果别的检查也能拦住同一个输入，拆掉这道闸后测试照样绿，等于没测。

| 位置 | 测试 | 为什么这样构造 |
|---|---|---|
| `core/crypto.py:15` 空钥匙 | 钥匙设为空，加密应该报配置错误 | 拆掉后钥匙变成 `sha256("")`，人人都能算出来 |
| `core/fields.py:31` 读 | 用钥匙 A 存，换成钥匙 B 再读，应该报错 | 拆掉后会把密文本身当密码返回 |
| `core/fields.py:44` 存 | 用钥匙 A 加密一段，换成钥匙 B 再存这段密文，应该报错 | 拆掉后会再加密一层，原密码永久丢失 |
| `accounts/permissions.py:21` | `can_use(user, "tournament_regsiter")`（故意拼错）应该报错 | 拆掉后拼错的功能名默认放行 |
| `content/embeds.py:74` | 短链跳到 `evil.example.com/video/BV1xx411c7mD` | 目标地址里**特意放了 BV 号**：不放的话，第 77 行「没有 BV 号」也会拦住，测不出第 74 行 |
| `content/embeds.py:77` | `https://www.bilibili.com/video/` | 拆掉后生成 `bvid=None` 的播放器 |
| `core/fonts/download.py:55` | 声明 11 字节、实际 10 字节、上限 10 | **实际内容没超**，只有看声明长度的那道能拦 |
| `core/fonts/download.py:65` | 不声明长度、实际 11 字节、上限 10 | 没有声明长度，第 55 行不起作用 |
| `core/fonts/download.py:67` | 下载到空文件 | |
| `core/fonts/download.py:98` | Google 返回 400，提示里要有字体名 | 拆掉后照样报错，只是提示变成笼统的「HTTP 400」，所以断言提示内容 |
| `core/fonts/download.py:145` | 样式表里只有 ttf，没有 woff2 | |
| `core/fonts/forms.py:148` | 添加字重时文件和地址都不填 | |
| `core/fonts/processing.py:58` | 空文件，提示要说「空的」 | 拆掉后解析也会失败，但提示变成「无法解析」，所以断言提示内容 |
| `core/fonts/processing.py:60` | 把上限临时改成 10 字节，传 11 字节 | 同上，拆掉后提示变成「无法解析」 |
| `content/models.py:163` | 4 篇置顶**都还没存进数据库**时调页面的 `clean()` | 编辑在后台一次提交全部置顶；已有的测试只测了「第 4 篇单独保存」那条路 |

字体下载的 4 条测试用假的网络响应（`fake_download` 夹具），不连网。

## 变异结果

用 042 的脚本在导出的副本里跑，真实仓库不被改动。原始结果在 `mutants.jsonl`：

```
✓ 被抓到  core/crypto.py:15 _fernet  if not raw  ← core/tests/test_crypto.py::test_an_empty_key_is_refused_rather_than_hashed
✓ 被抓到  core/fields.py:31 EncryptedTextField.to_python  if looks_like_fernet(value)  ← core/tests/test_crypto.py::test_reading_ciphertext_from_another_key_fails_loudly
✓ 被抓到  core/fields.py:44 EncryptedTextField.get_prep_value  if looks_like_fernet(value)  ← core/tests/test_crypto.py::test_saving_ciphertext_from_another_key_is_not_encrypted_again
✓ 被抓到  accounts/permissions.py:21 can_use  if feature not in Feature.values  ← accounts/tests/test_profile.py::test_can_use_rejects_an_unknown_feature_name
✓ 被抓到  content/embeds.py:74 BilibiliEmbedFinder.find_embed  if _hostname(resolved) not in BILIBILI_HOSTS | B23_  ← content/tests/test_submissions.py::test_bilibili_finder_refuses_a_short_link_that_leaves_bilibili
✓ 被抓到  content/embeds.py:77 BilibiliEmbedFinder.find_embed  if not bvid  ← content/tests/test_submissions.py::test_bilibili_finder_refuses_a_page_without_a_video_id
✓ 被抓到  core/fonts/download.py:55 fetch_bytes  if declared and int(declared) > max_bytes  ← core/tests/test_fonts.py::test_download_refuses_a_declared_size_over_the_limit
✓ 被抓到  core/fonts/download.py:65 fetch_bytes  if len(data) > max_bytes  ← core/tests/test_fonts.py::test_download_refuses_a_body_over_the_limit_without_a_declared_size
✓ 被抓到  core/fonts/download.py:67 fetch_bytes  if not data  ← core/tests/test_fonts.py::test_download_refuses_an_empty_file
✓ 被抓到  core/fonts/download.py:98 fetch_google_css  if exc.code == 400  ← core/tests/test_fonts.py::test_google_fonts_400_names_the_missing_family
✓ 被抓到  core/fonts/download.py:145 parse_google_css  if not faces  ← core/tests/test_fonts.py::test_google_css_without_woff2_slices_is_refused
✓ 被抓到  core/fonts/forms.py:148 FontFaceAddForm.clean  if not cleaned.get("file") and not cleaned.get("url  ← core/tests/test_fonts.py::test_adding_a_weight_needs_a_file_or_a_url
✓ 被抓到  core/fonts/processing.py:58 inspect_font  if not data  ← core/tests/test_fonts.py::test_an_empty_font_file_is_reported_as_empty
✓ 被抓到  core/fonts/processing.py:60 inspect_font  if len(data) > MAX_FONT_BYTES  ← core/tests/test_fonts.py::test_an_oversized_font_file_is_refused_before_parsing
✓ 被抓到  content/models.py:163 HomePage.clean  if self.pinned_articles.count() > MAX_PINNED_ARTICL  ← content/tests/test_content.py::test_homepage_clean_refuses_a_fourth_pin_before_any_are_saved
15 / 15 被抓到
```

## 验收输出

```
$ git status --short
 M accounts/tests/test_profile.py
 M content/tests/test_content.py
 M content/tests/test_submissions.py
 M core/tests/test_crypto.py
 M core/tests/test_fonts.py
?? handoff/rounds/051-guard-gaps/

$ ruff check . && ruff format --check .
All checks passed!
213 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python -m pytest -q
675 passed in 51.43s
```

660 → 675，新增 15 条。推送后的 CI 结果记在下一轮。

## 改动文件

```
core/tests/test_crypto.py          3 条
accounts/tests/test_profile.py     1 条
content/tests/test_submissions.py  2 条
content/tests/test_content.py      1 条
core/tests/test_fonts.py           8 条，加一个假网络响应的夹具
handoff/rounds/042-guard-sweep/report.md   加更正说明
handoff/STATUS.md
handoff/rounds/051-guard-gaps/
```
