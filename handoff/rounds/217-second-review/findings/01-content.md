# 217 复核 01：内容渲染

范围：`content/markdown.py`、`content/embeds.py`、`content/legacy_body.py`（逐行）、`content/article_meta.py`、`content/blocks.py`、`content/markdown_views.py`、`content/widgets.py`，以及渲染结果落到的模板（`article_page.html`、`_toc.html`、`standard_page.html`、`article_index_page.html`、赛事/内战 `detail.html`、`core/templatetags/ow.py` 的 `markdown` 过滤器）。对照设计 5.2、细节 6.3–6.5，以及 210 review 的 D1/D10/F10（211 修过）。

**复现说明**：复现脚本 `handoff/rounds/217-second-review/findings/01-repro_test.py`，在测试机跑过一次（`bash scripts/remote-check.sh run uv run pytest -q -s -p no:cacheprovider handoff/rounds/217-second-review/findings/01-repro_test.py`，日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261007-033450-5b6d6c3.log`，基于 `e417b2e` + 工作区，结果 `2 failed, 5 passed in 14.22s`）。两条失败的意思见 01-1 和「查过没问题」的 XSS 一条：一条是我对后果的预期写错了（实际后果另一种），一条是断言写得太粗（误报），都不是脚本坏了。下面引用的输出都是这次真实打印的。

## 低（01-1：静态读时按中记，实测后降级，放在最前因为最容易碰到）

### 01-1 正文里单独一行的畸形网址让渲染抛异常：预览、发布、自动保存 500；已上线文章的定时修改会**悄悄丢掉**

- **严重度**：低（只伤到写的人自己；原来按静态推断以为会卡住全站定时发布，实测不会，见下）
- **位置**：`content/markdown.py:62`（`video_src` 里的 `urlparse(url)`）、`content/embeds.py:49-50`（`raw_page.isdigit()` 后 `int(raw_page)`）、`content/embeds.py:61-67`（`follow_b23` 只接 `URLError, OSError, ValueError`）、`content/markdown.py:73-77`（只接 `EmbedException`）；放大点在 `content/models.py:411-427`（`ArticlePage.save` 每次全量保存都渲染）、Wagtail `management/commands/publish_scheduled.py`（`for rp in revs_for_publishing: rp.publish(...)` 没有 try）
- **问题**：`_standalone` 把「整段只有一个裸网址」的段落交给 `video_src`，有三种输入会抛出不是 `EmbedException` 的异常，一直冒到 `render()` 外面：
  1. **裸网址里方括号不配对**：`https://[x`、`http://a]b`。`BARE_URL` 不排除 `[`、`]`，`fullmatch` 成立；`video_src` 第 62 行 `urlparse(url)` 在 Python 3.13 对这种网址抛 `ValueError("Invalid IPv6 URL")`。（写成 Markdown 链接的不会，因为 `normalizeLink` 把方括号编码成了 `%5B`；只有裸网址这条路传的是原文。）
  2. **B 站链接的分 P 参数是上标数字**：`https://www.bilibili.com/video/BV1xx411c7mD?p=²`（裸网址或 `[看](…?p=²)` 都一样，`parse_qs` 会把 `%C2%B2` 解回 `²`）。`"²".isdigit()` 是 True，`int("²")` 抛 `ValueError`。
  3. **b23 短链带非数字端口**：`https://b23.tv:abc/x`。`hostname` 还是 `b23.tv`，走 `get_embed` → `find_embed` → `follow_b23` → `urlopen`；`urllib` 在 `do_open` 的 try **外面**建 `HTTPSConnection`，`_get_hostport` 抛 `http.client.InvalidURL`（是 `HTTPException`，不是 `OSError`/`ValueError`），`follow_b23` 不接，`video_src` 也不接。
- **失败场景**：
  - 任何验证过邮箱的成员（投稿者组有 `access_admin`）在编辑器里写这样一行：预览返回 500（编辑器显示「预览没有生成」），点「发布」500。只伤到自己。
  - 赛事/内战管理员在说明里写这样一行：`Tournament.save`/`Scrim.save` 里 `plain_text` 抛异常，自动保存每次 500、`autosave.js` 不停重试。
  - **定时修改悄悄丢掉**：认证作者或内容编辑（能填「定时上线」的人）给一篇**已经上线**的文章改正文加上这样一行、设定时上线后点发布。Wagtail 的 `PublishRevisionAction` 对「已上线 + 定时在将来」这一支在 `object.save()` 之前就 `return`，所以排期时不渲染、不报错，页面写「会在 MM月DD日 上线」。到点后 worker 的 `publish_due_pages` → `publish_scheduled` → `rp.publish()`：Wagtail 先 `object.revisions.update(approved_go_live_at=None)`（没有包事务），再 `object.save()` → `stored_counts` → 抛异常。结果：这一拍里排在它后面的到点修订推迟 30 秒（下一拍正常发出）；**这篇的定时修改的排期已经被清掉，再也不会上线，前台一直是旧正文，没有任何提示**，只有 worker 日志里一条 `Failed to publish scheduled pages`。（我原先按静态读以为循环会永远卡在这一条上、别人的定时文章都发不出去，实测不是。）
- **怎么验证**：`01-repro_test.py::test_crash_inputs`、`::test_scheduled_revision_with_crash_body_blocks_the_queue`（已上线文章 A 改出 `https://[x` 定时 +1h，新文章 B 定时 +2h，时钟拨到 +3h 跑两拍）。实测输出：

  ```
  [bare-bracket] RAISES builtins.ValueError: Invalid IPv6 URL
  [bare-close-bracket] RAISES builtins.ValueError: Invalid IPv6 URL
  [bili-link-superscript-page] RAISES builtins.ValueError: invalid literal for int() with base 10: '²'
  [bili-bare-superscript-page] RAISES builtins.ValueError: invalid literal for int() with base 10: '²'
  [b23-nonnumeric-port] RAISES http.client.InvalidURL: nonnumeric port: 'abc'
  [inline-bracket-not-alone] OK -> '<p>看这里 <a href="https://%5Bx">https://[x</a> 结束</p>\n'
  [plain_text bare-bracket] RAISES builtins.ValueError: Invalid IPv6 URL
  [schedule A (live page)] OK -> None
  B live before: False
  [publish_due_pages #1] RAISES builtins.ValueError: Invalid IPv6 URL
  [publish_due_pages #2] OK -> True
  B live after two beats: True | A body now: '正文'
  ```
  （脚本这一条的断言是按「卡住队列」写的，所以显示 FAILED；打印的才是实际行为：第一拍异常，第二拍 B 上线，A 的修改没上线。）
- **修法建议**：`video_src` 整段 try 住（`urlparse`、`extract_bvid_and_page`、`get_embed` 抛任何异常都当「不是视频」）；`isdigit()` 换 `isdecimal()` 或 `try: int()`；`follow_b23` 再接 `http.client.HTTPException`。定时发布失败时至少给作者/超管一封信（现在只有日志）。
- **状态**：已复现（测试机，输出见上）。

## 中

### 01-2 编辑器预览接口能让任何成员把服务器拖去逐条查 b23：每行一次联网、每行一条 `Embed`，没有上限也没有限速

- **严重度**：中
- **位置**：`content/markdown_views.py:18-20`（`preview`，`PREVIEW_LIMIT = 200_000`，没有限速）、`content/markdown.py:66-78`、`content/embeds.py:61-67`（`urlopen(timeout=10)`）、`content/embeds.py:70-90`（失败行写进 `Embed`，从不清理）；`deploy/entrypoint-web.sh`（gunicorn 同步 worker、默认 30 秒超时、`GUNICORN_WORKERS=5`）
- **问题**：211 把「查不到」也缓存了一小时，解决的是**同一个**失效短链反复联网（210 D1）。但缓存按网址算，渲染遇到**没见过的** b23 网址照样同步联网。预览接口 `placed("content", "articles")` 只要求 `access_admin`，投稿者组（所有验证过邮箱的成员）就有；一次 POST 最多 20 万字，`https://b23.tv/x1` 这样每行约 20 字，一次请求能塞约 8000 个不同短链，渲染逐个 `urlopen`（每个最多 10 秒），直到 gunicorn 30 秒超时杀掉 worker。设计 5.2 写「渲染正文本身不联网」，但实际上第一次渲染和每次过期后的渲染都在请求线程里联网。
- **失败场景**：一个普通成员开 5 个并发循环 POST `/admin/markdown/preview/`，每次换一批短链 → 5 个 gunicorn worker 一直卡在 b23 的往返上、每 30 秒被杀一次重开，全站动态页面（登录、后台、成员页）排队或 502；服务器 IP 对 b23.tv 发出大量请求，可能被 B 站限流，之后正常的短链也查不到（还会被当成「查不到」缓存一小时）；`wagtailembeds_embed` 每次多出几十到几百行，永不清理。不用恶意也会碰到：一篇赛事说明里有 3 条以上 b23 链接、b23 不通（测试机的 IPv4 走 WARP，WARP 断了就是这样）时，缓存过期后第一个打开赛事详情页的访客（`|markdown` 每次请求现渲染）要等 3×10 秒，超过 30 秒就 502。
- **怎么验证**：`01-repro_test.py::test_every_new_b23_line_is_one_lookup_and_one_row`（mock `follow_b23` 抛 `EmbedNotFoundException`），实测：

  ```
  one render of 300 distinct b23 lines: lookups=300 embed rows=300 in 0.29s
  second render lookups total: 300
  ```
  即一次渲染 300 次联网（这里被 mock 掉，真实每次最多 10 秒）、写 300 行；同一批第二次不再联网（211 的缓存是好的）。脚本里「拨过 1 小时再渲染」那一步没生效（Wagtail 的 `get_embed` 是 `from django.utils.timezone import now`，我 patch 的是模块属性），过期后重查没测到。另外同一次跑的耗时：20 万字的 `"!["` 渲染 3.9 秒、`"["` 2.2 秒、2000 行 500 列的表格 2.0 秒（2 万字时 0.36 / 0.20 / 0.08 秒，大致线性，不是 ReDoS），预览接口没有限速，也就是每个成员每次 POST 能白占一个 worker 约 4 秒 CPU，和联网叠加。线上 worker 被杀未验证。
- **修法建议**：预览和所有「现渲染」路径不联网——只读缓存，查不到的交给 worker 去查（查完后让相关页面重新生成）；或至少给预览限速、限制一次渲染里新查的短链个数（比如 5 个，其余当普通链接），并定期清理过期的失败行。
- **状态**：已复现（逐行联网、逐行写行）；并发拖垮 worker 是推测（没压测）。

## 低（续）

### 01-3 目录里的标题文字被转义两次：标题里有 `&`、`<`、`>`、`"` 时目录显示 `&amp;`、`&quot;`

- **严重度**：低
- **位置**：`content/article_meta.py:70`（`strip_tags(inner)`）、`content/templates/content/_toc.html:3`（`{{ heading.text }}`）
- **问题**：`inner` 是渲染后的 HTML，`Q&A` 已经是 `Q&amp;A`。Django 的 `strip_tags` 用的 `MLStripper(convert_charrefs=False)` 会把实体原样留下（`handle_entityref` 追加 `&amp;`），模板自动转义再转一次 → 页面源码 `Q&amp;amp;A`，读者看到 `Q&amp;A`。
- **失败场景**：3 个以上小标题的文章里有一节叫「Q&A」或「他说"好"」，宽屏右栏和手机折叠目录都显示 `Q&amp;A`、`他说&quot;好&quot;`。不是 XSS（多转了一次）。
- **怎么验证**：`01-repro_test.py::test_toc_text_is_escaped_twice`，实测页面里的目录：

  ```
  <li class="c-toc__item c-toc__item--h2"><a href="#h-1">Q&amp;amp;A</a></li><li class="c-toc__item c-toc__item--h2"><a href="#h-2">他说&amp;quot;好&amp;quot;</a></li><li class="c-toc__item c-toc__item--h3"><a href="#h-3">a&amp;lt;b&amp;gt;c</a></li>
  ```
  修法：`html.unescape(strip_tags(inner))`，模板照常转义。
- **状态**：已复现。

### 01-4 裸网址结尾的 `)` 一律剥掉，带括号的网址（维基百科条目）链接错

- **严重度**：低
- **位置**：`content/markdown.py:31`（`TRAILING` 含 `)`）、`:158`（`match.group(0).rstrip(TRAILING)`）
- **问题**：不管括号是否配对都剥。`https://en.wikipedia.org/wiki/Overwatch_(video_game)` 变成指向 `…Overwatch_(video_game` 的链接，`)` 留在链接外面当文字。
- **失败场景**：攻略里直接贴维基、萌娘百科之类带括号的地址，点进去是不存在的条目。
- **怎么验证**：`render("见 https://en.wikipedia.org/wiki/Overwatch_(video_game)")`，看 `href`。修法：只在括号不配对时剥 `)`（GFM autolink 的规则）。
- **状态**：已核对代码。

### 01-5 编辑器底部字数和文章头字数不是同一个算法（细节 6.3 说用同一个）

- **严重度**：低
- **位置**：`static/js/markdown-editor.js:27-32`（`countWords`：在 Markdown 原文上去掉链接网址和 `https?://\S+` 再数）对比 `content/article_meta.py:23-42`（在渲染后的纯文本上数）
- **问题**：两边口径不同，至少三处结果不一样：① **裸网址**：前端去掉不算；后端渲染成链接、链接文字就是网址本身，`LATIN_WORD` 把 `https`、`www.bilibili.com`、`video`、`BV…` 都算成词（这也和细节 6.3「链接网址不算」不符）；② **有序列表的编号**：前端把行首 `1.` 的 `1` 算一个词，后端渲染后编号不在文字里；③ **外站图片没写图注**：后端渲染成文字「图片」算 2 个字，前端算 0。
- **失败场景**：一篇贴了 10 个视频/网址链接的文章，编辑器底部写 500 字，发布后文章头写 540 字。
- **怎么验证**：同一段 `1. 第一\n2. 第二\n\nhttps://www.bilibili.com/video/BV1xx411c7mD 看这个` 分别喂 `countWords` 和 `stored_counts`。修法：底部字数改用预览接口返回的数（或一个专门的计数接口），别在 JS 里另写一套。
- **状态**：已核对代码。

### 01-6 写法说明说「单独一行 `---` 是分隔线」，但紧跟在文字下一行的 `---` 会把上一行变成二级标题（还进目录）

- **严重度**：低
- **位置**：`content/templates/content/widgets/markdown_editor.html`（写法说明「分隔线：单独一行 `---`」）、`content/markdown.py:270`（CommonMark + `breaks: True`）
- **问题**：CommonMark 的 setext 标题：`一段文字\n---` 是 `<h2>一段文字</h2>`。本站又规定「单个换行就是换行」，作者习惯回车就换行，照写法说明在文字下一行写 `---` 时，上一行变成二级标题、带橙色竖条，还算进目录。工具栏按钮插入的是 `\n\n---\n\n`，没问题；手打的才会。`===` 同理。
- **失败场景**：作者写「本周赛程如下\n---\n周五…」，前台「本周赛程如下」成了一个小标题。预览里看得到，所以是易用性问题。
- **怎么验证**：`render("本周赛程如下\n---\n周五")` 得到 `<h2>`。修法：关掉 setext 标题（`md.disable("lheading")`，`#` 标题照常），或在写法说明里写清要空一行。
- **状态**：已复现（同一脚本 `setext-after-br`：`'第一行\n---'` → `<h2>第一行</h2>`，`===` 也一样）。

### 01-7 中文里加粗带引号/括号的字时 `**` 不生效、星号原样显示（旧内容迁移和新写的都会）

- **严重度**：低
- **位置**：`content/markdown.py:270`（CommonMark 的左右侧定界规则）；旧内容转换 `content/legacy_body.py:80-81,126-127`（`<b>` 直接换成 `**`）
- **问题**：CommonMark 规定 `**` 前面是字母/汉字、后面紧跟标点（`“`、`（`）时不算开始加粗。`这是**“重点”**内容`、`别忘**（注意）**了`在前台显示成带星号的原文。工具栏「加粗」包住选中文字时正好产生这种写法；v6.70 迁移把 Draftail 的 `<b>“重点”</b>` 转成同样的形状，迁移过来的旧文章里这样的加粗会变成星号。`<b> 加粗</b>`（开头有空格）同样失效。
- **失败场景**：公告里「请看**“报名须知”**」显示成星号。
- **怎么验证**：`01-repro_test.py::test_legacy_conversions`，实测：

  ```
  [cjk-bold-quotes] HTML '<p>这是<b>“重点”</b>内容，<b>（注意）</b>别忘</p>'
      MD  '这是**“重点”**内容，**（注意）**别忘'
      OUT '<p>这是**“重点”<strong>内容，</strong>（注意）**别忘</p>\n'
  [bold-leading-space] HTML '<p>前<b> 加粗</b>后</p>'
      MD  '前** 加粗**后'
      OUT '<p>前** 加粗**后</p>\n'
  ```
  不只是星号露出来，第一条还把**没加粗的「内容，」加粗了**。修法：渲染前对 CJK 邻接的 `**` 做兼容处理（社区有 `markdown-it-cjk-friendly` 这类规则，要加依赖先问用户），或者旧内容迁移时改写成 `<strong>`（但不收 HTML）——至少在写法说明里提醒。正式站已经迁移过的文章要查一遍有没有这样的残留星号：`ArticlePage.objects.filter(body__regex=r"[^\s*]\*\*[“‘（《「]")`。
- **状态**：已复现（转换和渲染）；正式站有没有残留没查（推测有）。

### 01-8 `legacy_body` 的几处转换错（v6.70 迁移已经跑过，只影响以后从旧备份恢复再迁移）

- **严重度**：低
- **位置**：`content/legacy_body.py`
- **问题**（逐行读出的，都会让旧内容的样子和原来不一样，不丢字）：
  1. `:84-85,130-131` 行内代码：`<code>a_b</code>` 里的字先被 `_escape` 加了反斜杠，代码段里反斜杠是字面字符 → 前台显示 `a\_b`。
  2. `:19` `_BLOCK_START` 不管 setext 下划线：`<p>第一行<br/>---</p>` 转成 `第一行\n---` → 上一行变成二级标题（同 01-6）。
  3. `:57-67` 列表项里的文字不做行首转义：`<li># 不是标题</li>` → `- # 不是标题`，列表项里出现一个标题；`<li>1. x</li>` → 嵌套的有序列表。
  4. `:121-122` 嵌套列表后面还有父项的文字（`<li>a<ul><li>b</li></ul>c</li>`）：`c` 被当成没缩进的顶层段落，列表从这里断开。
  5. `:103-109,140` 链接地址原样放进 `](…)`：地址里有空格或不配对的 `)` 时整个链接变成字面文字。
  6. `:142-146` `convert_charrefs=True` 之后 `&` 不转义：原文写的是字面的 `&copy;`（库里存 `&amp;copy;`）会被渲染成 `©`。
  7. `:91-93` `<ol start="5">` 的起始编号丢了，从 1 开始。
  8. `:195-200` 引用块的每一行不做行首转义：引用里以 `- `、`# `、`1. ` 开头的句子变成列表/标题；而且最后一行是列表项时，出处「——某人」被吞进列表项的续行，不再是出处。
  9. 两个相邻的 `<ul>` 合成一个「松散」列表（每项包 `<p>`，行距变大）；`<h2>上<br/>下</h2>` 的「下」掉出标题成了段落。
- **失败场景**：正式站 183 起的数据已经是 Markdown，不受影响；从 v6.70 以前的备份恢复后跑迁移（`content/0007`、`tournaments/0012`）才会再走这里。另外两个迁移直接 import 这个文件（REVIEW-GUIDE 192 节），以后改它会改变老迁移的行为。
- **怎么验证**：`01-repro_test.py::test_legacy_conversions`，实测（节选）：

  ```
  [code-escape] MD '变量 `a\\_b\\*c`'  OUT '<p>变量 <code>a\\_b\\*c</code></p>\n'
  [entity-text] HTML '<p>&amp;copy; 写法</p>'  OUT '<p>© 写法</p>\n'
  [li-heading] OUT '<ul>\n<li>\n<h2>不是标题</h2>\n</li>\n<li>\n<ol>\n<li>不是编号</li>\n</ol>\n</li>\n</ul>\n'
  [li-after-nested] MD '- a\n  - b\n\nc\n\n- d'  OUT '…</ul>\n<p>c</p>\n<ul>\n<li>d</li>\n</ul>\n'
  [href-space] OUT '<p>[链接](<a href="https://example.com/a">https://example.com/a</a> b)</p>\n'
  [href-paren] OUT '<p><a href="https://example.com/a">链接</a>b)</p>\n'
  [ol-start] MD '1. 五\n2. 六'
  [quote] MD '> - 第一句\n> # 第二句\n> 1. 第三\n> ——某人'
      OUT '<blockquote>\n<ul>\n<li>第一句</li>\n</ul>\n<h2>第二句</h2>\n<ol>\n<li>第三<br />\n——某人</li>\n</ol>\n</blockquote>\n'
  ```
- **状态**：已复现。

### 01-9 b23 短码里碰巧有 `BV` 时不去解析，直接当成一个不存在的 BV 号

- **严重度**：低
- **位置**：`content/embeds.py:15`（`BV_RE = r"(BV[0-9A-Za-z]+)"`，没有长度和边界）、`:45`、`:103-108`（`find_embed` 先 `extract_bvid_and_page(url)`，取到了就不跟 b23 跳转）
- **问题**：`https://b23.tv/xBV3kq1` 的路径里能搜到 `BV3kq1`，于是不去解析短链，直接生成 `bvid=BV3kq1` 的播放器（真实 BV 号是 `BV1` 开头共 12 位）。b23 短码 7 位、62 个字符，含 `BV` 的概率约千分之一几。
- **失败场景**：作者贴的短链碰巧含 `BV`，前台播放器显示「视频不存在」，查到的结果还被永久缓存。
- **怎么验证**：mock `follow_b23` 计数，`render("https://b23.tv/xBV3kq1")` → 调用 0 次、`<iframe src="…bvid=BV3kq1">`。修法：b23 网址一律走解析；`BV_RE` 收紧成 `BV1[0-9A-Za-z]{9}` 并要求边界。
- **状态**：已核对代码。

## 查过没问题

- 手拼的 HTML 全过 `escape`（实测 `![x" onerror="alert(1)](/media/a.png)` → `alt="x&quot; onerror=&quot;alert(1)"`，引号被转义、没有可执行属性；脚本 `test_xss_payloads` 显示 FAILED 是我断言写粗了——子串 ` onerror=` 出现在已转义的属性值里——因此它后面的 11 个载荷没跑到，那几条只是代码核对）：`_figure`（`src`、图注）、`_player`（`src` 来自 `player_src` 或缓存 iframe 的 `src`，单次转义、`&` 变 `&amp;` 正确）、`_attributions` 的出处、`_render_image` 的外站图片链接和 alt。`html: False`，原始 HTML 原样显示成文字。
- 链接、图片地址都经 markdown-it 的 `normalizeLink` + `validateLink`（拒 `javascript:`、`vbscript:`、`file:`、非 png/gif/jpeg/webp 的 `data:`，先 `strip().lower()`）；`own_image` 拒 `//host`，`/\evil` 会被编码成 `%5C`；`data:image/png` 不算本站图片、只显示 alt。
- `?bvid=` 只认 BV 形状（F10/D4 修好了）；`player_src` 只拼字母数字 BV 号和整数分 P。
- 211 的失败缓存：`remember_failed_lookup` 用的 `get_embed_hash(url)` 和 Wagtail 8.0 `get_embed` 的 key 一致（都不带宽高）；`get_embed` 用 `exclude(cache_until__lte=now())` 读，失败行一小时内命中、返回空 `html` → 不出播放器；查到后 `find_embed` 返回 `cache_until: None`，`update_or_create` 覆盖掉失败行；并发写同一行由 Django 的 `get_or_create` 重取和这里的 `IntegrityError` 兜住。
- 字数、阅读时间、纯文本 211 起存在字段里（`ArticlePage.save`、`Scrim.save`、`Tournament.save`），搜索、文章卡不再现渲染（D10 修好了）。`save_revision` 只带 `update_fields` 不含 `body`，自动保存草稿不渲染。
- AI 审核送的是 Markdown 原文（`moderation/integrations.py:page_text`），链接地址在里面，没有因为 `plain_text` 丢掉网址。
- `_site_rules` 排在 `text_join` 之后；`_link_bare_urls` 跳过链接里面的文字和行内代码；`_attributions` 对嵌套引用、引用里的列表不会误改。
- ReDoS：`BARE_URL`、`LATIN_WORD`、`CJK`、`HEADING`、`ID_ATTR`、`_BLOCK_START` 都没有嵌套量词回溯；`HEADING` 的 `.*?` 只在真正的 `<h2>/<h3>` 上起步，渲染结果里的标题总是闭合的；commonmark 预设 `maxNesting: 20`。markdown-it-py 4.2.0 已经包含 2023 年那两个 CVE 的修复。实测 13 种病态输入从 2 万到 20 万字耗时大致线性增长，最慢的是 20 万字 `"!["` 3.9 秒（数字见 01-2）。
- `content/blocks.py` 只剩迁移引用的空子类；`widgets.py` 的 data 属性都是 `reverse()` 和设置值；编辑器模板没有 `|safe`。
- 预览接口和上传接口都套了 `placed`；预览把 POST 截到 20 万字。

## 没来得及看

- XSS 载荷里除第一条以外的 11 条没在测试机上跑到（断言误报中断），修脚本断言后再跑一次。
- b23 失败缓存一小时过期后的重查（脚本 patch 的位置不对）。
- 01-4、01-5、01-9 没跑，是代码核对。
- 正式站库里有没有 01-7 那种残留星号、有没有 01-1 那几种会崩的行（`body__regex` 查一遍）。
- `content/migrations/0007`、`0009`、`tournaments/0012` 反向迁移用 `content.markdown.render` 的效果。
