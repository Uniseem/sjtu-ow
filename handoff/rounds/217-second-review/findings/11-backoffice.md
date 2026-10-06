# 217 复核 11：后台（`backoffice/`、`core/autosave.py`、`AutosaveReplayMiddleware`）

只记录，不修。复现脚本：`findings/11-repro_test.py`（11-1 到 11-5）、`findings/11-repro2_test.py`（11-6、11-7）。第一份在测试机上跑完：`bash scripts/remote-check.sh run uv run pytest -q -s -p no:cacheprovider handoff/rounds/217-second-review/findings/11-repro_test.py` → `6 passed in 2.85s`（每条测试断言的都是现在的错误行为，绿 = 复现）。11-1 到 11-5 是「已复现」；第二份（11-6、11-7）没跑，是「已核对代码」。

## 问题

### 11-1 删分类时的计数，一篇文章只算一个分类（212 D2 的修法留了洞）
- **严重度**：中
- **位置**：`content/services.py:243-260`（`category_use_counts`），调用方 `backoffice/views/categories.py:31,83,106`
- **问题**：`by_page` 是「页面 → 一个分类」的字典。先填页面行上的分类，再拿最新修订和定时修订**覆盖**同一个键。结果是一篇文章的页面行、最新草稿、定时修订各写一个分类时，只有最后写进去的那个被算上，另外几个分类的计数是 0：列表里出现「删除」按钮，`category_delete` 也放行。
- **失败场景**：
  - (a) 文章已经发布在 Y 分类（页面行 = Y），编辑自动保存的草稿改成 X。这时 Y 的计数是 0，列表给出删除按钮，点了以后 `category.delete()` 撞上 `ArticlePage.category` 的 `PROTECT`，抛 `ProtectedError`，页面 500。
  - (b) 已发布文章（行 = Y）排了一次定时更新（修订 = Z），之后另一位编辑的草稿改成 X（新修订）。Z 和 X 只有一个算得上，没算上的那个能**静默删掉**（行上是 Y，没有 PROTECT 拦）。删的是 Z 的话，到点时 `publish_scheduled` 打开 Z 修订就会碰到 modelcluster 对 `PROTECT` 外键的 `raise Exception`，定时上线失败；删的是 X 的话，编辑页 500。这正是 D2 本来要防的情形。
- **怎么验证**：`11-repro_test.py::test_11_1a…`、`test_11_1b…`。现有测试 `content/tests/test_category_delete.py:120-166` 只覆盖了页面行为空、或最新修订分类为空的情形，碰不到覆盖。
- **修法提示**：每篇文章收集一个**分类集合**（行、最新修订、定时修订都算），按集合计数。
- **状态**：已复现（`test_11_1a`、`test_11_1b` 都绿：(a) 删除旧分类 500 且分类还在；(b) Z、X 只算上一个，没算上的那个删得掉，删后对应修订 `as_object()` 抛异常）

### 11-2 212 D3「别人改过就不存」被「覆盖同一条修订」绕过
- **严重度**：中
- **位置**：`content/drafts.py:29-42`（`stale_base`）、`content/drafts.py:45-67`（`overwritable` + `save_draft`）；`backoffice/views/articles.py:172,248`、`backoffice/views/pages.py:97,155,201`
- **问题**：防护只比较修订编号。可是同一个人 30 分钟内的自动保存走 Wagtail 的 `overwrite_revision`，**改的是同一条修订，编号不变**（`wagtail/models/revisions.py:430-435`）。所以乙打开编辑页以后，甲又接着存了几次，乙手里的编号仍然等于 `latest_revision_id`，乙的保存不会被拒。乙的表单整张提交、按 `changed_data` 和当前草稿比较，乙看到的旧正文和当前正文不一样，于是正文被写回旧版：**甲在乙打开之后写的内容全部丢失**。接下来甲的保存反而被拒（「另一个人在你打开以后改过这篇」）。
- **失败场景**：两位编辑同时开着「关于我们」或同一篇文章，甲一直在写，乙只改了一下标题，甲最近十几分钟写的正文就没了。网站页面、首页置顶、栏目介绍同理。
- **怎么验证**：`11-repro_test.py::test_11_2…`：甲存一次拿到 r，乙这时打开（基于 r），甲再存（r 不变），乙带着 r 改标题，结果 `ok=True`、正文变回甲的第一段。现有测试 `content/tests/test_drafts.py:242-302` 只测了「甲第一次保存产生了新修订」这一种情形。
- **修法提示**：表单带的应该是「修订编号 + 修订的 `created_at`」（覆盖时会更新这个时间），或者另设一个每次保存都加一的版本号。
- **状态**：已复现。测试机输出：
  ```
  甲第一次存： True 修订 441 -> 442
  甲接着写： True 修订号还是 442 乙打开时的号 442
  乙改标题：ok= True saved= ['title', 'body', 'author', 'slug']
  现在的草稿：标题 乙改的标题 正文 '甲第一段'
  ```

### 11-3 在「角色」页给「投稿者」组关掉「投稿」会无限递归，500
- **严重度**：中（超管一点就 500，组成员的状态可能停在半路）
- **位置**：`backoffice/views/members.py:262-278`（`role_restriction_add`）、`backoffice/templates/backoffice/members/roles.html`（每个组包括投稿者都有「对这组关掉」）；根因在 `accounts/signals.py:82-110` 加 `accounts/services.py:197-212`
- **问题**：限制存好后，信号对投稿者组里每个人调 `sync_submitter_group`。`can_use(ARTICLE_SUBMIT)` 因为「在投稿者组里」返回 False，于是把人移出组；`m2m_changed(post_remove)` 再次同步，这时他已经不在组里，`can_use` 变成 True，又把人加回去；`post_add` 再同步……如此循环，直到 `RecursionError`。
- **失败场景**：超管想暂停全站投稿，在「成员 → 用户与权限 → 角色 → 投稿者」选「投稿」点「对这组关掉」，结果 500。限制那一行已经提交了没有，取决于事务边界。
- **怎么验证**：`11-repro_test.py::test_11_3…`（`pytest.raises(RecursionError)`）
- **修法提示**：这种限制本身会自我取消。要么表单不让对投稿者组关投稿，要么同步时不把「投稿者」组本身算进 `can_use` 的组限制。和 10（账号）那块可能重叠。
- **状态**：已复现。测试机输出：`角色页给投稿者组提供了「对这组关掉」: True`、`POST 抛出 RecursionError`

### 11-4 选图控件拿非数字的值重画表单就 500
- **严重度**：低
- **位置**：`backoffice/widgets.py:55-56`（`ImagePicker.get_context` 直接 `filter(pk=value)`），`backoffice/widgets.py:91`（`image_field` 用的是 `forms.ModelChoiceField`，不是 216 的 `IdChoiceField`）
- **问题**：字段校验本身会把 `abc` 当作无效选项报错，但不带 `X-Autosave` 整张提交时，页面要带着原值重画。控件拿 `"abc"` 去查图片，抛 `ValueError`（Field 'id' expected a number），渲染时 500。
- **失败场景**：写文章（所有验证过邮箱的成员都能进）、新建或编辑赛事、战队编辑、全站设置的 7 个图片字段，凡是 POST `cover=abc` 这类值都会 500。`core/tests/test_garbage_input.py` 的 `POSTS` 里没有 `cover`、`logo`、`hero_image` 这些键，所以测不出来。违反 AGENTS「编号一律过一道关」。
- **怎么验证**：`11-repro_test.py::test_11_4…`
- **状态**：已复现。测试机输出：`投稿者写文章 cover=abc（不带 X-Autosave）: 500`、`新建赛事 图片字段=abc: 500`、`全站设置 图片字段=abc: 500`

### 11-5 投稿者在「关联赛事」下拉里看得到草稿和已取消的赛事
- **严重度**：低（信息泄露）
- **位置**：`backoffice/forms.py:174`（`Tournament.objects.order_by("-pk")`，不分状态）
- **问题**：任何验证过邮箱的成员打开 `/admin/articles/new/`，下拉里就能读到还没发布的赛事标题。前台文章页倒是按 `is_public` 过滤了，但下拉没有过滤。
- **怎么验证**：`11-repro_test.py::test_11_5…`
- **状态**：已复现。测试机输出：`投稿者写文章页里有草稿赛事名: True`

### 11-6 操作记录按「到 9999-12-31」筛选就 500
- **严重度**：低（只有超管能进）
- **位置**：`backoffice/views/settings.py:66-69`（`_day_start(until) + timedelta(days=1)` 溢出，抛 `OverflowError`）。对照：活动数据有 `EARLIEST` / `LATEST` 兜底（`core/activity.py:71`）。
- **怎么验证**：`11-repro2_test.py::test_11_6…`（没跑）
- **状态**：已核对代码

### 11-7 清理空草稿会删掉只写了简介、联系方式的赛事草稿
- **严重度**：低
- **位置**：`core/management/commands/cleanup_old_data.py:143-145`
- **问题**：赛事只看 `title=""` 和 `description=""`，不看 `summary`、`participant_contact`、时间。文章那边是算上了 `summary` 的。注释写着 “Anything with a word in it stays”，和代码不一致。
- **失败场景**：赛事管理员先写了简介、群号，标题还没定，一周没碰，就被夜里的清理删掉。
- **怎么验证**：`11-repro2_test.py::test_11_7…`（没跑）
- **状态**：已核对代码

### 11-8 列表页按权限隐藏按钮，有一处漏了
- **严重度**：低
- **位置**：`backoffice/templates/backoffice/content/categories.html` 末尾，空状态里的「新建分类」没套 `{% if can_add %}`。页头那个按钮是套了的。
- **失败场景**：只有分类 change 权限、没有 add 权限的人，在空列表上点了得到 403。
- **状态**：已核对代码

### 11-9 `docs/admin.md` 4.2 对文章表单字段的描述和代码不一致
- **严重度**：低（设计和实现两说，违反硬规则 1）
- **位置**：`docs/admin.md:92` 和 `backoffice/forms.py:183-189`
- **问题**：文档写「内容编辑和超管多『开放评论』」「普通成员（`plain_writer`）只能选开放投稿的分类」。代码是按 `is_submitter_only` 判断的，所以赛事管理员、内战管理员、认证作者（`plain_writer` 或非编辑）也有「开放评论」，也能选不开放投稿的分类。代码和原来的 `content/forms.py:34-40`、设计 15 章 L2849「投稿者只能选」是一致的，**错的是 admin.md 的措辞**。
- **状态**：已核对代码

## 查过没问题

- **门**：`nav.placed` 先判登录、再 `can_enter`（含 `is_active`）、再标签自己的 `allowed`；`announce` 按种类套 `placed`，种类不认识就落到首页的门，`announce_view` 里再判 `entry.can_send`。全部 POST 视图都是 `require_POST` 或 `method == "POST"` 分支，后台没有 `csrf_exempt`，模板里 42 个 POST 表单都带 `csrf_token`。删除和状态改动都没有走 GET。
- **跨角色越权**：赛事和内战的视图分别挂在 `runs_tournaments` / `runs_scrims` 的标签下，内战管理员进不了赛事的编辑、复制、删除、编队、审核，反之亦然。文章的编辑、预览、撤下、删除逐篇用 `OwnArticlesPermissionTester`。分类的新建和删除另外判 add / delete 权限，成员分组同样。用户、战队、角色、全站设置、字体、静态页、操作记录、集合都只给超管。按编号操作的视图（规则、限制、分组成员、评论）没有按对象分的权限，设计上也没有。
- **`AutosaveReplayMiddleware`**：
  - 键是 `用户pk:随机键`，换个账号读不到别人的记录。键只在响应带了 `location` 且和请求地址不同时才写入。
  - 它排在 CSRF 的 `process_view` 前面就短路返回，但返回的只是本人自己的地址；跨站请求带不了自定义头，也读不到响应，所以没有风险。
  - 新建的对象被删掉以后再重放，会转到 404 的地址，脚本按「永久失败」停止重试（提示文案写的是登录失效，不准确，但这种情形太刁钻，不单列）。
  - 文章重放后表单的 `latest_revision` 是空的，`stale_base` 对空值放行，不会误报「别人改过」。
- **自动保存的三条规则**：赛事和内战新建、复制只把 `valid_changes` 套到新的 `fresh` 上；分组规则覆盖人数范围和报名窗口两条库约束；编辑时部分保存捕获 `IntegrityError`。成员分组、分类的大小写或条件唯一约束会落到表单错误上。
- **密钥**：三处密钥都不回显，空着就保留；存过之后服务端回 `values` 把框清空（F4）；`input` 事件跳过密码框，只在离开框时存。
- **启用和停用**：自己的账号不能停；已注销的账号不给「重新启用」按钮，服务层也会拒（213 A8）。停用以后 `ModelBackend` 不再认这个会话。
- **其它**：成员分组搜人只有超管按邮箱搜（A2）；后台模板里没有 `|safe`、`mark_safe`；`safe_next` 只接受本站地址；`letters_confirm` 按做事的人过滤。

## 没来得及看

- 11-6、11-7 的复现脚本没跑（协调方要求收尾）。
- `static/js/backoffice.js`（人选器、选图对话框）的逐行检查，交给 12 块。
- `KeepSeconds` 让带秒的 `starts_at` 每次自动保存都出现在 `saved` 里、每次都触发 `after_change`（重新生成页面、送审）。只是推测有放大效应，没核对去重逻辑。
- 已解散的战队还能在后台改名、打开招募；内战发布后能改「规格」：两处设计都没写，没有判成缺陷。
- `tournaments/review_admin.py`、`teams_admin.py`、`split_admin.py` 的内部逻辑（归 05、06 块）。
