# 192 正文改成 Markdown，后台换成 Markdown 编辑器（报告）

## 做了什么

1. **存储**：`ArticlePage.body`、`StandardPage.body`、`Tournament.description` 改成 `TextField`（Markdown 原文），`Scrim.description` 本来就是文本框，不动。迁移：
   - `content/0007_markdown_body`：StreamField 先改名让路，新加同名文本字段，转换后删掉旧字段。转换包括每篇的线上内容和**每条修订**（草稿、定时发布的版本从最新修订打开，不转的话编辑器里是一串 JSON）。站内页面链接按默认站点根路径换成地址，图片块换成原图地址（`default_storage.url`）
   - `tournaments/0012_markdown_description`：富文本转 Markdown
   - 两个都写了反向（每篇变成一段渲染好的 HTML）
   - 转换代码在 `content/legacy_body.py`（HTMLParser，处理 p、h2–h4、b/strong、i/em、a、ol/ul/li 含嵌套、br、hr、code、图片 embed；文字里会变成标记的字符加反斜杠，行首的 `1.`、`#`、`-` 之类也转义）
   - `content/blocks.py` 只剩迁移 0001 引用的 `VideoBlock`；三个块模板删了
2. **渲染**：`content/markdown.py`，markdown-it-py（新依赖，MIT；依赖 mdurl，MIT），`commonmark` 加表格、删除线，`html: False`、`breaks: True`。自己加的规则：
   - 标题收拢：`h1`→`h2`，`h4`–`h6`→`h3`
   - 一段里只有图片（一行一张）：每张变成 `<figure>`，方括号里的字是图注；只要有一张不是本站的就照普通段落处理
   - 图片只放本站的（以 `/` 开头的地址或 `SITE_URL` 的主机）；外站 http(s) 图片变成链接，`data:` 之类只留文字
   - 一段里只有一个 B 站链接（裸地址、`<地址>`、`[字](地址)` 都算）：播放器 `<figure class="c-prose__video"><iframe …>`。`bilibili.com` 直接按 BV 号拼地址，`b23.tv` 走 Wagtail 的 `get_embed`（第一次联网查，之后存在 Embed 表里）
   - 正文里粘贴的 `http(s)://` 地址变成链接，碰到中文标点停，末尾的英文标点不算
   - 表格外面包 `<div class="c-prose__table">`（可横向滚动）
   - 引用的最后一行以「——」开头时变成 `<footer>`，和原来的引用块一样右对齐
   - `analyse()` 顺带数图片和视频，`plain_text()` 给字数、搜索、邮件用
3. **编辑器**：EasyMDE 2.21.0 放进 `static/vendor/easymde/`（npm 包的 sha512 和登记的一致；里面打包了 CodeMirror 5.65.15、marked、codemirror-spell-checker、Typo.js，都是 MIT 或 BSD，许可证文本记进 `THIRD_PARTY_NOTICES.md`）。`content/widgets.py` 的 `MarkdownEditor` 挂在四处的 `FieldPanel` 上；`static/js/markdown-editor.js`：
   - 不下载 Font Awesome、关掉拼写检查，图标用 Wagtail 后台自带的雪碧图（`#icon-bold` 等）
   - 工具栏：加粗、斜体、删除线、二级标题、三级标题 | 引用、无序列表、有序列表 | 链接、图片（上传）、B 站视频、表格、分隔线 | 预览、并排预览（不进全屏）、全屏 | 写法说明（编辑器下面展开一张表）
   - 预览 POST 到 `/admin/markdown/preview/`，服务器用同一个 `render()`；按顺序号丢掉过时的回应
   - 图片：按钮、拖入、粘贴都 POST 到 `/admin/markdown/image/`，走 Wagtail 自己的图片表单（格式、5 MB），进「投稿图片」集合，没有往这个集合加图的权限回 403；返回 `max-1600x1600` 缩略图的地址，插在单独一行
   - 改动同步回 textarea 并发 `input`、`change` 事件，Wagtail 的未保存提醒和实时预览照常工作
   - 底部字数：汉字加英文单词，去掉链接地址
4. **读正文的地方**：文章页（`render()` 后再加标题锚点）、普通页面和赛事、内战页（模板过滤器 `{{ …|markdown }}`，在 `ow` 标签库里）、`article_meta.body_text()`（字数、阅读时长）、站内搜索（文章正文和赛事、内战说明都先转纯文字再匹配）、AI 审核（送 Markdown 原文，链接地址也在里面）、上线准备检查协议里的【】、`load_legal_pages`（直接存草稿，去掉开头给社团的注释和草稿自己的 `#` 标题）、新内战邮件（说明转纯文字）
5. `init_site` 建页面时原来写 `body=[]`（StreamField 的空值），改成文本字段后存进去的是字符串 `"[]"`，`load_legal_pages` 以为已经有正文就跳过了。改成 `body=""`（全量测试里 `test_the_command_publishes_both_drafts` 红了才发现）
6. 样式：前台 `c-prose` 加行内代码、代码块、表格（`c-prose__table`）、删除线、文字里的小图、`c-prose__video`；后台 `admin.css` 加编辑器和预览的整套样式，深浅两种模式都跟着令牌走，加了 `--sj-accent`。EasyMDE 的样式表作为表单资源排在 `admin.css` 后面，同样优先级时它赢（第一次截图里编辑区的标题有 30 多像素），所以覆盖它的规则前面都加了 `.md-field`
7. **上传权限**：用户 10-04 看了上一版的说明后说「图片上传权限应该是所有人都有的啊，普通人也可以投稿的」。验证过邮箱、能投稿的成员本来就都在投稿者组（有「投稿图片」的上传权限）；`assign_content_permissions()` 再给赛事管理员、内战管理员两个组同样的权限，他们不一定在投稿者组（邮箱没验证、或者投稿功能对他关着）。认证作者、内容编辑原来就有
8. 投稿须知、样张页、README（新一节「正文的写法」、自托管脚本表）、AGENTS.md（坑）、`static/vendor/README.md`；设计 5.2、8.1、9.1、12 章三张表、13.2.6、13.16、15 章，细节 6.3、6.4，附录 D v6.70

## 验证

本机开发库迁移：21 篇文章、3 个普通页面、5 条赛事说明转换后，逐篇把旧 HTML 和新 Markdown 渲染出来的结构比了一遍（标题、列表、加粗的标签序列和文字），只有一篇因为图片和引用夹在段落中间、比较脚本拼接方式不对报了差异，人工看过转换结果是对的。

截图（无头 Edge，1440×1000）：文章编辑页浅色、并排预览浅色和深色，编辑器、工具栏图标、预览排版都正常；第一次截图发现 EasyMDE 盖掉了编辑区样式，加 `.md-field` 后重截正常。

内置浏览器（本机开发站）：

- 文章编辑页 EasyMDE 起来了，17 个按钮，底部「337 字」和服务器算的 `ArticleFacts(words=337, …)` 一致
- 点并排预览，预览区是服务器渲染的 HTML（`<h2>赛前</h2>` 等）；点写法说明，说明表展开
- 赛事编辑页编辑器正常，控制台没有新的报错（列出来的几条是开发服务器重启时上一页的心跳请求）
- 在编辑区派发一个带 PNG 的粘贴事件：上传成功，插入 `![](/media/images/browser-upload.max-1600x1600.webp)`，textarea 同步了。当时插在了光标处、紧贴正文，之后把插入格式改成前后各空一行（单独一行才是大图），这一改没有再在浏览器里点过

前台页面（开发站）：`/news/spring-cup-final-report/` 目录锚点 `h-1`…正常；`/tournaments/2/` 说明渲染成 `<h2>`、`<strong>`；搜索「龙骑」4 条结果，摘录里没有星号。

## 命令输出

变异（本机，38 处，全部被抓到）：

```
baseline green, 29 tests
caught HTML let through -> test_html_is_shown_as_text_and_bad_links_are_not_links
caught newlines run together -> test_one_newline_is_a_line_break
caught a first-level heading in the body -> test_headings_are_second_and_third_level_only
caught any image shown -> test_only_this_sites_images_are_shown
caught images alone stay inline -> test_an_image_alone_is_a_figure_with_its_caption
caught no player -> test_a_bilibili_link_alone_is_the_player
caught any site's video a player -> test_a_bilibili_link_alone_is_the_player
caught pasted addresses stay text -> test_pasted_addresses_become_links_without_the_full_stop
caught the full stop joins the link -> test_pasted_addresses_become_links_without_the_full_stop
caught tables do not scroll -> test_tables_scroll_and_quotes_keep_their_source
caught quotes lose their source -> test_tables_scroll_and_quotes_keep_their_source
caught quotes lose their source -> test_a_quote_names_its_source
caught plain text keeps entities -> test_plain_text_is_what_a_reader_sees
caught words counted in the raw text -> test_word_counts_leave_out_markup_and_addresses
caught search reads the markup -> test_search_matches_the_words_not_the_markup
caught review misses the body -> test_review_gets_the_body_as_written
caught article body unrendered -> test_the_article_page_shows_the_markdown
caught tournament description unrendered -> test_event_pages_show_their_descriptions_as_markdown
caught scrim description unrendered -> test_event_pages_show_their_descriptions_as_markdown
caught page body unrendered -> test_the_command_publishes_both_drafts
caught letter carries markup -> test_the_new_scrim_letter_carries_plain_words
caught article without the editor -> test_every_body_and_description_gets_the_editor
caught page without the editor -> test_every_body_and_description_gets_the_editor
caught tournament without the editor -> test_every_body_and_description_gets_the_editor
caught scrim without the editor -> test_every_body_and_description_gets_the_editor
caught Font Awesome fetched -> test_the_editor_script_loads_nothing_from_elsewhere
caught preview by GET -> test_the_preview_is_the_public_rendering
caught anyone uploads -> test_uploads_need_the_right_to_add_images
caught the original inserted -> test_an_upload_lands_in_the_submission_collection
caught no file, no answer -> test_a_file_that_is_not_an_image_is_refused
caught the note to the club published -> test_the_draft_goes_in_as_markdown_without_the_note_and_title
caught new pages start as a list -> test_the_command_publishes_both_drafts
caught old quotes lose the dash -> test_old_blocks_turn_into_markdown
caught old text turns into lists -> test_old_rich_text_turns_into_the_same_markdown_page
caught drafts left as JSON -> test_bodies_drafts_and_descriptions_survive_the_switch
caught descriptions left as HTML -> test_bodies_drafts_and_descriptions_survive_the_switch
caught managers cannot add pictures -> test_managers_upload_even_outside_the_submitters
caught the renderer's classes unstyled -> test_what_the_renderer_emits_has_its_styles
restored and green; missed: none
```

整组检查（本机；测试机仍连不上，`ssh: connect to host 2a0e:6a80:3:9c7:: port 22: Network is unreachable`）。第一次全量红了一条：

```
FAILED core/tests/test_flat_muted.py::test_nothing_is_outlined_only_toned_apart
1 failed, 1752 passed, 1 skipped in 357.46s (0:05:57)
```

表格和视频框改成浅底后重跑：

```
1753 passed, 1 skipped in 261.25s (0:04:21)
```

加上管理员上传权限以后最后一次：

```
1754 passed, 1 skipped in 365.94s (0:06:05)
```

```
All checks passed!
363 files already formatted
No changes detected
System check identified no issues (0 silenced).
```

（最后一行是 `check --deploy`，用 AGENTS.md 里那组环境变量跑的。）

### 正式站

升级前先备份：`已备份到 /app/backups/sjtu-ow-20261004-232907.tar.gz（210.1 MB）`。升级前库里要转换的只有：0 篇文章，`terms`、`privacy` 各一个段落块，`about` 为空，一条赛事说明（用户写的「段位要求 / 人员数目」）。这条说明先在本机转了一遍：`'## 段位要求\n\n至少白金\n\n## 人员数目\n\n总计 10 人，需要筛选'`。

`deploy_ship.sh 192` 的输出：

```
 Image sjtu-ow-worker Built 
 Image sjtu-ow-web Built 
sjtu-ow-web 2026-10-04 17:35:40 +0200 CEST
  Applying tournaments.0012_markdown_description... OK
 Container sjtu-ow-worker-1 Starting 
 Container sjtu-ow-worker-1 Started 
全量生成完成：成功 11，失败 0，删除 0；目录占用 249 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

然后在服务器上跑了一段核对脚本（`assign_content_permissions()` 也在里面跑的：部署脚本不跑 `init_site`）。脚本用测试客户端给超级管理员建了一个临时会话看编辑页，最后 `logout()` 删掉了：

```
0007 True 0012 True
tournament: '## 段位要求\n\n至少白金\n\n## 人员数目\n\n总计 10 人，需要筛选'
terms 1387 '生效日期：【YYYY 年 M 月 D 日】\n\n欢迎使用上海交通大学守望先锋社区网站（以下称「本站」）。本站由【运营方名称' revision body is str: True True
privacy 2420 '生效日期：【YYYY 年 M 月 D 日】\n\n本网站（以下称「本站」）由【运营方名称，比如：上海交通大学守望先锋社团】运' revision body is str: True True
about 0 '' revision body is str: True True
赛事管理员 [('投稿图片', 'add_image'), ('投稿图片', 'choose_image')]
内战管理员 [('投稿图片', 'add_image'), ('投稿图片', 'choose_image')]
editor on terms: True False
editor on tournament: True
preview: 200 <h2>测</h2>
<p><strong>粗</strong></p>
```

「editor on terms」第二项是 False，是因为脚本找的是字面的 `easymde.min.js`，生产环境的静态文件名带哈希；容器里收集到的是 `easymde.min.6032a851ed03.js` 等。前台：`/terms/` 的正文是 `<p>`、`<strong>`，`/tournaments/1/` 是 `<h2>段位要求</h2> <p>至少白金</p> …`。

## 没做 / 顺带发现

- 从图片库里挑已有的图插进正文（只做了上传），留给以后
- 赛事、内战管理员的**封面**选择器：他们现在有「投稿图片」的选图权限，但默认封面在别的集合里，他们能不能选到那些图本轮没核实
- `b23.tv` 短链第一次渲染时要联网查一次（预渲染或预览时），查不到就当普通链接
- `journey.py pages` 没跑（测试机连不上，本机没有 Chromium）
- 栏目介绍（`ArticleIndexPage.intro`）还是 Draftail 富文本，不在本轮范围

## 推送后补的（同一轮，用户 10-04：「先把文档什么更新一下然后 push 吧」）

- `handoff/REVIEW-GUIDE.md` 加「192 正文改成 Markdown」一节：手写 HTML 块的转义、预览进 innerHTML、上传接口、迁移依赖应用代码、正文里写死的图片地址、编辑页没在 `journey.py pages` 里跑过
- `AGENTS.md` 目录表的 `content/` 一行写上 Markdown 相关的几个文件
- 后台手册（`core/admin_manual.py`）：赛事管理员、内战管理员、内容编辑、认证作者各一句「用 Markdown 写、点「?」看写法、图片拖进来或粘贴」。只改了文字，`core/tests/test_admin_manual.py` 等 27 条通过，提交前又跑了全量
