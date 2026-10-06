# 217 复核 03：评论

范围：`comments/` 全部（模型、services、视图、网址、模板、`rendering.py` 的状态片段），以及它碰到的 `content/models.py` 文章页上下文、`backoffice/views/comments.py` 与其模板、`core/ratelimit.py`、`deploy/Caddyfile` 带查询参数的分流。设计依据 5.6、4.4 表第 490–493 行、13.13.3。210 已修、213 落地的 S1（编辑和发表同样受限）、S7（被隐藏的评论作者不能删）没有重复报。

本轮只读代码，**没有在测试机或本机跑任何测试**。前一位复核者留下的 `03-repro_comments.py` 我读过（它疑心的是：未上线 / 私密文章经点赞、编辑接口泄露整块、CRLF 字数、登录读者的 N+1），但没有运行；这份文件早先草稿里贴的「5 passed」输出不是我跑的，下面不作为依据，各条状态按我自己核对的程度写。

---

## 03-1 中　点赞、编辑、删除、置顶、隐藏接口不查文章是否上线、是否公开：任何登录用户能读出撤下或私密文章第一页的整块评论，还能改赞数、改正文

- **位置**：`comments/views.py:136-144`（`_act`）、`:112-120`（`_moderate`）、`:148-153`（`like` 超限分支）、`:158-162`（`edit` 超限分支）；`comments/views.py:39-52`（带 HTMX 头时渲染整块）；`comments/services.py:213-229`（`toggle_like`）、`:280-301`（`edit`）、`:49-60`（`can_comment` 不查 `live`）
- **问题**：`create`、`reply`、`more` 和状态片段 `article_comments_slot` 都先过 `commentable_page`（`.live().public()`），但 `like`、`edit`、`delete`、`pin`、`unpin`、`hide`、`unhide` 只做 `get_object_or_404(Comment, pk=pk)`，然后拿 `comment.page` 调 `_section_response`。请求带 `HX-Request: true` 时，响应是 `section_context(..., interactive=True)` 渲染的整块评论区：第 1 页 20 条顶层评论和全部可见回复，含昵称、头像、正文。两个超限分支同样先取评论再渲染整块，不查文章，所以每分钟 60 次的点赞限额也挡不住读。service 层的 `toggle_like`、`edit` 也不查文章状态（`can_comment` 只看功能权限和 `comments_enabled`）。
- **失败场景**：
  1. 内容编辑把一篇有问题的文章撤下（后台 `article_unpublish`）。评论编号是连续的，任何登录成员带 HTMX 头 POST `/comments/<n>/like/` 逐个试，就能读到撤下文章下的评论（可能正引用着出问题的内容）；再点一次取消赞，不留痕迹。即使点赞超限，超限分支照样回整块。
  2. 超管在 `/wagtail/` 给文章加了密码或「仅限某些组」的查看限制。文章页对普通成员不可见，但经点赞接口照样读到评论。
  3. 作者在文章撤下期间还能编辑自己的评论（编辑照常送审），文章重新上线后显示的是撤下期间改的内容；赞数在撤下期间也能被改。
  4. 不带 HTMX 头时只是 302 回文章地址（文章 404），不泄露；但脚本加一个请求头即可。
- **怎么验证**：建文章和一条评论，`article.unpublish()`；对照 `GET /comments/<文章>/more/` 应 404；用另一个成员 `POST /comments/<评论>/like/`，带 `HTTP_HX_REQUEST="true"`，断言 200、响应含评论正文、`like_count` 变 1。私密：给文章建 `PageViewRestriction(PASSWORD)`，同样请求。编辑：作者 POST `/comments/<评论>/edit/`，断言正文被改。前一位复核者的 `03-repro_comments.py` 前三条就是这个写法，可直接拿去跑。
- **修法提示（不在本轮做）**：`_act`、两个超限分支统一 `_page_or_404(comment.page_id)`；`_moderate` 是否放行未上线文章另定（只对内容编辑开放，风险小）；`toggle_like`、`edit`、`delete` 在 service 里也查一次 `commentable_page`。
- **状态**：已核对代码（未运行）

## 03-2 低　被拒的回复和编辑会丢掉刚打的字

- **位置**：`comments/views.py:68`（`draft` 只留给顶层评论）、`:151-153`、`:160-162`、`:143`（编辑被拒时不传草稿）；`comments/templates/comments/_own.html:7`（编辑框回填的是库里的旧正文）、`_composer.html:9`（回复框不回填）
- **问题**：所有提交都是 HTMX 整块替换。顶层评论被拒时 `draft_body` 回填进发表框；但回复被拒（太频繁、超长、对方刚被隐藏）、编辑被拒（太频繁、超长、刚被禁言）时，整块重新渲染，回复框是空的、编辑框是旧正文，用户打的字直接没了，而且回复框、编辑框所在的 `<details>` 也被折叠回去，只在顶部提示条里看到原因。
- **失败场景**：一分钟内连发了 3 条，第 4 条写的是一段长回复，提交后回「评论太频繁了，稍后再试」，回复内容消失。
- **附带：换行字数**。服务端对正文直接 `len()`，不把 `\r\n` 换成 `\n`（`services.py:70`、`:293`）。浏览器原生提交表单时换行会被规范成 CRLF，输入框按 1 个字算、服务端按 2 个字算。但本站提交走 htmx 2.0.10，它从 `FormData` 取值后自己 URL 编码，按现行 HTML 规范 `FormData` 里的 textarea 值是 LF，所以正常路径应当不触发；只有 htmx 没加载、退回原生表单提交时才会。这一半是**推测**，没在浏览器里核对。
- **怎么验证**：先用 `cache` 把 `comment:m:<用户>` 的计数打满，再 HTMX POST 回复，看响应里回复框没有刚提交的正文；编辑同理。换行那一半要在浏览器里抓 htmx 发出的请求体看 `%0D%0A` 还是 `%0A`。
- **状态**：丢字一半已核对代码；换行一半推测

## 03-3 低　文章关闭评论后，作者的「编辑」框照样显示；点赞、编辑超限等提示在这种文章上根本不显示

- **位置**：`comments/templates/comments/_own.html:1`（只看 `not comment.is_hidden`，不看 `can_post`）；`comments/templates/comments/section.html:18-21`（`comments_enabled` 为假时走「关闭了评论」分支，`post_problems` 整段不输出）
- **问题**：213/S1 起，被禁言或文章关闭评论后不能再编辑（`services.edit` 先查 `can_comment`），但模板仍给作者显示「编辑」表单；提交后被拒。被拒的原因写在 `post_problems` 里，可关闭评论的文章走的是另一个分支，原因不显示：用户点「保存修改」，整块刷新，编辑框收起，正文没变，没有任何说明。点赞超限（`["点赞太频繁了，稍后再试"]`）在关闭评论的文章上也同样静默。被禁言的作者在开放评论的文章上能看到原因，只是编辑框不该出现。
- **失败场景**：内容编辑关了某篇文章的评论；作者想改错字，点编辑、保存，什么都没发生。
- **怎么验证**：文章 `comments_enabled=False`，作者登录看文章页，响应里有 `comment_edit` 的表单；HTMX POST 编辑，响应里没有「这篇文章关闭了评论」以外的任何提示，正文未变。
- **状态**：已核对代码

## 03-4 低　视图在事务外读评论，service 拿这个旧对象做检查：和隐藏、删除同时发生时 213 的守卫可被绕过

- **位置**：`comments/views.py:139`（事务外 `get_object_or_404`）；`comments/services.py:217`（`toggle_like` 查 `visible`）、`:254`（`pin_problem`）、`:288`（`edit` 查 `visible`）、`:310-313`（`delete` 查 `is_deleted` / `is_hidden`）
- **问题**：写事务是 IMMEDIATE，但被检查的对象是开事务之前读的，service 不重读；`save(update_fields=...)` 只写自己那几列。于是：作者 `delete` 与内容编辑 `hide` 交叉时，`delete` 用旧的 `is_hidden=False` 放行，留下「已隐藏且正文为空」的行（正是 S7 要防的）；`edit` 与 `hide` 交叉时，被隐藏的评论被换了正文；`pin` 与作者 `delete` 交叉时，得到 `is_pinned=True, is_deleted=True`（设计：删除会取消置顶）。
- **失败场景**：窗口只有几毫秒，概率低；后果是 v7.16 写进设计的规则被破坏。
- **怎么验证**：不需要并发：测试里先读出 `old = Comment.objects.get(pk=…)`，用另一个对象 `services.hide`，再 `services.delete(comment=old, actor=作者)`，应被拒、实际成功（`delete` 只看传进来的对象）。
- **状态**：已核对代码

## 03-5 低　后台「评论」列表把作者已删除的评论显示成空行，状态写「—」，还给「隐藏」「置顶」按钮

- **位置**：`backoffice/views/comments.py`（列表不排除、也不标出 `is_deleted`）；`backoffice/templates/backoffice/review/comments.html:24-34`
- **问题**：作者删掉的评论 `body=""`，列表行正文为空，状态只分「已隐藏 / 置顶 / —」。「隐藏」能点成功（把已删除的再标隐藏，无意义）；顶层的还给「置顶」，点了报「这条评论不能置顶」。
- **失败场景**：内容编辑翻全部评论，看到一串无正文、无说明的行；点置顶报错。
- **怎么验证**：建评论，作者 `services.delete`，用内容编辑（不是超管）打开 `/admin/` 的评论列表看这一行。
- **状态**：已核对代码

## 03-6 低　「加载更多」用页码分页：读的过程中有新评论、删除或赞数变化，会重复或漏掉条目，页面里出现重复的 `id="comment-N"`

- **位置**：`comments/services.py:176-177`（`Paginator(top, 20)`）；`comments/templates/comments/_more.html`、`section.html:49`（`hx-swap="beforeend"` 追加）
- **问题**：按「最新」排，读者加载第 1 页后别人又发了 k 条，再点「加载更多」，第 2 页前 k 条就是第 1 页末尾那几条，被追加进 `#comment-list`，同一个锚点出现两次。删除、隐藏会让后面的条目被跳过；「最热」下赞数一变也一样。
- **怎么验证**：发 21 条，取第 1 页，再发 1 条，GET `/comments/<文章>/more/?page=2`，原第 1 页第 20 条再次出现。
- **状态**：已核对代码

---

## 查过没问题

- `create` / `reply` / `more` / 状态片段：只认上线且公开的文章；`reply` 的文章取自父评论，不能跨文章；回复的回复挂回同一顶层，`reply_to_user` 记被回复者
- 草稿和没发布过的文章：没上线过的文章不可能有评论（`create` 只认 live）；文章删除时评论、点赞级联删除；作者是 PROTECT，用户只匿名化（`accounts/services.py:336-338`）
- 账号停用：`ModelBackend` 对 `is_active=False` 不还原会话，停用的人不能再发、赞、改；`can_moderate` 另查 `is_active`；改昵称、头像、停用会刷新评论过的文章（`accounts/services.py:271-274`）
- `comments_enabled` 关闭：发表、回复、编辑被 `can_comment` 拒，点赞照常，和设计 4.4 表第 491 行一致（编辑框的显示问题见 03-3）
- 点赞并发：IMMEDIATE 事务加 `(comment, user)` 唯一约束；增减在同一事务里，减带 `like_count__gt=0`
- 置顶唯一：部分唯一约束加 `release_pin`，隐藏、删除都同时清置顶（并发例外见 03-4）
- 限流：发表、回复、编辑共用每分钟 3、每天 100；点赞每分钟 60；`over_limit` 216 起在事务里计数，不会并发少算；带查询参数的请求 Caddy 交给 Django（`deploy/Caddyfile:110`），所以 `?comments=2` 的「加载更多」不会拿到静态第 1 页
- 排序参数：`sort` 在 `thread()` 里收敛成 `new` / `top`，模板里输出的是收敛后的值；页码非法由 `Paginator.get_page` 兜底
- N+1：`thread()` 的查询数和条数无关：顶层一次、回复一次（`select_related` 作者和被回复者、`with_avatars`）、点赞集合一次、`paginator.count` 一次；模板里用 `comment.pk in liked`、`item.replies|length`，不再查库。没有实测查询数
- 可见性：隐藏或删除的顶层评论只在还有可见回复时显示占位；读者看不到隐藏回复；内容编辑能看到隐藏的、看不到删除的；「最热」的回复数只算可见回复
- 模板：正文、昵称自动转义，没有 `|safe`；静态版没有表单、CSRF、登录态字样；`_like.html` 静态版只是文字
- 送审：发表、编辑在 `on_commit` 里送审，`submit` 只入库不联网，异常被吞，不挡评论

## 没来得及看

- 作者删除评论后，审核队列里尚未被巡检读过的那条记录没有撤回，巡检可能照样报给复核员或给作者发信（`moderation/services.py:91` 起的 `submit`、巡检脚本）。属于审核那一块
- 「N 条评论」用的是 `thread.total`，只算顶层（含占位）不算回复。设计没定口径，没当缺陷
- 文章预览（`article_preview`）对没发布过的草稿是否画交互版发表框（提交会 404），没细查
- 交互版里在「加载更多」出来的第 2 页上点赞、回复，响应按设计换回整块第 1 页，刚加载的条目消失、位置跳回顶部。设计 13.13.3 明写响应是整块，所以没当缺陷，但体验值得复看
- 浏览器里实际走 HTMX（`journey.py`）、抓 htmx 请求体核对换行编码：没有跑
