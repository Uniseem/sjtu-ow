# 04 Wagtail 超管路径（217 复核）

范围：`/wagtail/`（`WAGTAIL_ADMIN_PREFIX`）下还能到的一切、各应用的 `wagtail_hooks.py`、`accounts/admin_users.py`（底层后台的用户、用户组页）、`core/middleware.py` 的 `WagtailAdminCSPMiddleware`、`wagtail_urls` / `wagtaildocs_urls` 里不经过 `/wagtail/` 的 Wagtail 视图、全站设置的 Wagtail 表单、页面编辑面板、文档、重定向。只记录，不修。

复现脚本：`handoff/rounds/217-second-review/findings/04-wagtail_repro_test.py`（每条测试断言的是「现在的缺陷行为」，通过 = 复现）。在测试机上跑了一次（`bash scripts/remote-check.sh run uv run pytest -q -s -p no:cacheprovider handoff/rounds/217-second-review/findings/04-wagtail_repro_test.py`），结果是 `1 failed, 8 passed in 4.42s`，退出码 0。通过的 8 条就是复现了 04-1（两个地址各两条）、04-2、04-3（两条）、04-4。没通过的那条是 04-5 里「邮箱按大小写原样存」这个子论断，实际存进去的是小写，其余部分都复现了，见 04-5。本机只看了输出的最后 120 行，前几条测试打印的内容没留下来，只有「通过」这个结论。

## 高

### 04-1 两个不走 allauth 的登录口：没验证邮箱也能登录，登录失败没有任何限流

- **严重度**：高（匿名、从公网可达，绕过设计 3.1、3.2 和 15 章的两道安全控制）
- **位置**：
  - `sjtu_ow/urls.py:12`：`include(wagtailadmin_urls)` 带进了 Wagtail 的 `login/`（`wagtail/admin/urls/__init__.py:147`）。它在 `require_admin_access` 之外，匿名可达
  - `sjtu_ow/urls.py:24`：`include(wagtail_urls)` 带进了 `_util/login/`（`wagtail/urls.py`，名字是 `wagtailcore_login`）。它就是 Django 自带的 `auth_views.LoginView`，在 `/wagtail/` 之外，`WagtailAdminCSPMiddleware` 根本不看
  - `core/middleware.py:51-58`：只把**已登录的**非超管从 `/wagtail/` 送走，匿名的请求照样进 `/wagtail/login/`
  - `deploy/Caddyfile:100`（`/wagtail/*` 一律交给 Django）、`@not_get_head`（POST 一律交给 Django）：两个地址 Caddy 都放行
- **问题**：两个视图都用 Django 的 `AuthenticationForm`，直接调 `django.contrib.auth.authenticate()`。allauth 的两道检查只在它自己的登录流程里：登录失败限流在 `allauth.account.adapter.DefaultAccountAdapter.authenticate`（`pre_authenticate` 计 `login_failed`，`settings/base.py` 的 `ACCOUNT_RATE_LIMITS["login_failed"] = "10/m/ip,5/300s/key"`），强制验证邮箱在 allauth 登录流程的验证阶段（`ACCOUNT_EMAIL_VERIFICATION = "mandatory"`）。`ModelBackend` 和 `allauth.account.auth_backends.AuthenticationBackend.authenticate` 本身两样都不做，只拒绝停用账号。`settings.WAGTAILADMIN_LOGIN_URL = "account_login"` 只改了「跳到哪登录」，`/wagtail/login/` 这个地址仍然在。站内也没有别的限流兜底：`core/ratelimit.py` 只用在业务操作上，Caddyfile 里没有限流
- **失败场景**：
  1. 有人用别人的邮箱（或者随便编一个）注册，验证码收不到。他 `GET /_util/login/` 拿 CSRF，再 `POST username=那个邮箱&password=…`，就拿到整站有效的会话：报内战、报赛事、申请和创建战队、评论都只看 `can_use()`（`accounts/permissions.py`，只查 `is_active` 和规则），全站只有投稿查 `email_is_verified`（`content/views.py:106`）。这违反设计 3.1「邮箱验证是强制的：没验证邮箱的账号不能登录」（`docs/design.md:265`）
  2. 撞库和暴力破解：对任何账号，包括超管，在 `/wagtail/login/` 或 `/_util/login/` 上无限次试密码，不会碰到 allauth 的「同一账号 5 分钟 5 次、同一 IP 每分钟 10 次」。这违反设计 3.2「登录失败次数过多时临时限制」（`docs/design.md:273`）和 15 章「暴力破解：allauth 限流」（`docs/design.md:2905`）。超管密码一旦被试出来，`/wagtail/` 整个对攻击者敞开
- **怎么验证**：`04-wagtail_repro_test.py` 的 `test_unverified_account_signs_in_through_the_other_door` 和 `test_the_other_door_has_no_failed_login_limit`，两个地址各参数化一次。断言：没验证的账号在 `/accounts/login/` 登不进去，在侧门登进去了；错 60 次以后侧门的状态码全是 200，第 61 次用对的密码照样登进去。手工验证：生产配置下 `curl -c j -b j https://…/_util/login/` 取 `csrftoken`，再 POST 表单
- **状态**：已复现（`test_unverified_account_signs_in_through_the_other_door[/wagtail/login/]`、`[/_util/login/]`、`test_the_other_door_has_no_failed_login_limit` 两个参数在测试机上都通过，见开头的运行结果）。现有测试里没有一条请求过 `/wagtail/login/` 或 `/_util/login/`（`grep -rn "wagtail/login\|_util/login\|wagtailadmin_login\|wagtailcore_login"` 在 `*/tests/` 里什么都没搜到）

## 中

### 04-2 在底层后台给页面设「隐私」以后，预渲染的静态文件留着，Caddy 照样发给所有人，最长到第二天 04:15

- **严重度**：中
- **位置**：`content/signals.py:73-149`（只在发布、撤下、删除、改 slug、移动时 `request_removal`）；`core/prerender.py:376-386`、`223-250`；Wagtail 的 `wagtailadmin_pages:set_privacy`（`/wagtail/pages/<id>/privacy/`）。全仓库没有任何代码监听 `PageViewRestriction`（`grep -rn ViewRestriction` 在业务代码里为空）
- **问题**：页面隐私（要登录、要密码、限定用户组）只能在 `/wagtail/` 里设，新后台没有这个功能（`docs/admin.md` 7）。全站读文章的地方都按 `.public()` 过滤：`content/prerender_targets.py:17`、`search/services.py:90`、`comments/services.py:40`、首页、栏目、sitemap。但是设隐私不发 `page_unpublished` 之类的信号，已经生成的 `prerendered/news/<slug>/index.html` 没人删。Caddy 先找静态文件（`deploy/Caddyfile` 的 `@prerendered`），匿名访客照样拿到全文。要等夜里 `15 4 * * * prerender`（`deploy/crontab.example`）跑 `generate_all`：页面不在 `page_targets()` 里了，文件才被删掉。期间首页和栏目页的静态副本也还列着这篇（没人触发 `refresh_listings`）。给整个「资讯」栏目设隐私的话，下面每篇文章都是这样
- **失败场景**：超管发现一篇文章不该公开，在底层后台点「隐私 → 登录后可见」，界面显示成功；Django 渲染的地址确实跳到登录页了，但访客走的是 Caddy 的静态文件，最长将近 24 小时还能看到全文
- **怎么验证**：`test_wagtail_privacy_leaves_the_static_file`：先 `generate` 出静态文件，超管 POST `set_privacy`（`restriction_type=login`），把 `on_commit` 回调都执行掉。断言：匿名请求 Django 得 302、文件还在、这一页不在 `page_targets()` 里
- **状态**：已复现。测试机输出：
  ```
  [wagtail] 设「登录后可见」 -> 200；on_commit 回调 0 个
  匿名访问 Django -> 302 /_util/login/?next=/news/soon-private/
  静态文件还在=True  在全量目标里=False
  ```

## 低

### 04-3 底层后台的用户编辑页绕开 213 补的账号状态服务：注销的账号能被「启用」、提成超管、设上新密码；重新启用不清停用原因；停用不记操作记录

- **严重度**：低（只有超管能做；但这正是设计 3.7 v7.16 写明「直接提交也拦」、213 A8/A9 专门修过的不变量，修的时候只修了新后台）
- **位置**：`accounts/admin_users.py:23-46`（`SiteUserEditForm` 的字段里有 `is_active`、`is_superuser`、`email`、`groups`、`deactivation_note`；它从 Wagtail 的 `UserForm` 继承了 `password1/password2`，`WAGTAILUSERS_PASSWORD_ENABLED` 默认是 True，模板 `accounts/templates/accounts/admin/user_edit.html` 不显示这两个框，但 POST 上来照收）、`accounts/admin_users.py:62-86`（`save_instance` 不调 `accounts.services.reactivate_account` / `deactivate_account`）
- **问题**：`reactivate_account` 对 `is_deleted()` 的账号抛 `AccountError`、启用时清 `deactivation_note`（`accounts/services.py:837-844`），新后台走的是它（`backoffice/views/members.py:170-201`）。底层后台的表单直接改 `is_active`，三处都绕过去了：
  1. 注销账号（`deleted-N@deleted.invalid`、「已注销用户」）勾上「启用」就活了。能同时勾「管理员」（`is_superuser`），还能 POST 一个新密码（`password1/2`），213 A9 清掉的超管标记又回来了
  2. 普通停用的账号重新启用时，表单把原来的停用原因原样带回来，原因不清（设计 3.7「重新启用时停用原因清空（v7.16）」）
  3. 在这里停用不写 `admin_log` 的 `users.deactivate`（新后台写，带原因），操作记录里只有 Wagtail 的一条通用「编辑」
  违反硬规则 6「状态字段只能通过 service 函数改」
- **失败场景**：超管在 `/wagtail/users/` 里点开一个「已注销用户」，顺手勾了「启用」保存。`can_use()` 对这个空壳变成 True，成员分组的人选器会列出它
- **怎么验证**：`test_wagtail_user_edit_revives_a_deleted_account`（断言 `is_deleted` 仍为真，同时 `is_active`、`is_superuser` 都是 True、新密码能用）、`test_wagtail_reactivation_keeps_the_spent_reason`
- **状态**：1、2 已复现（两条测试在测试机上都通过）；3 只核对了代码

### 04-4 底层后台改「是否来自交大」时，「交大用户 / 校外用户」组被表单里的旧勾选盖回去，`can_use()` 按错的组判断

- **严重度**：低（只有超管能做，但是是顺手就会碰到的操作，结果和界面显示的不一致）
- **位置**：Wagtail 的 `UserForm.save`（`wagtail/users/forms.py:178-189`：先 `user.save()`，再 `self.save_m2m()`）；`accounts/signals.py:73-78`（`post_save` 里的 `sync_sjtu_groups`）、`accounts/signals.py:81-91`（`m2m_changed` 只重算投稿者）；`accounts/permissions.py:15-30`
- **问题**：顺序是这样的：`user.save()` 触发 `post_save`，`sync_sjtu_groups` 按新的 `is_sjtu` 把人挪到「交大用户」；紧接着 `save_m2m()` 用表单里提交的 `groups` 整体 `set()`，「角色」标签页上还勾着原来的「校外用户」，于是又被换回去。`m2m_changed` 只调 `sync_submitter_group`，交大、校外两个组没人再纠正。结果是 `is_sjtu=True`，人却在「校外用户」里。直到这个人下一次整体 `save()` 才恢复。超管在「角色」页直接取消勾选「校外用户」也一样（这样能绕开对这个组的功能限制）。新后台的 `UserForm.save_roles` 把系统组排除在外（`backoffice/forms.py:565-605`），没有这个问题。Wagtail 用户列表的批量「分配角色」（`accounts/wagtail_hooks.py` 有意保留）也能把人加进这两个系统组
- **失败场景**：「校外用户」组上有「报名赛事」的功能限制。超管在底层后台把一个人改成交大的，保存后页面显示「是否来自交大：是」，这个人报名赛事却被拒（「你暂时无法使用此功能」）
- **怎么验证**：`test_wagtail_is_sjtu_change_leaves_the_old_group`
- **状态**：已复现。测试机输出：`[wagtail] POST -> 302；改之后：is_sjtu=True 组=['投稿者', '校外用户'] can_use(报名赛事)=False`

### 04-5 底层后台改登录邮箱不验证、不同步 allauth 的邮箱记录：旧地址照样能登录，新地址按大小写原样存

- **严重度**：低
- **位置**：`accounts/admin_users.py:33-38`（`email` 在 `SiteUserEditForm` 的字段里，模板 `user_edit.html` 第一个框就是它）；`settings/base.py:301` 的 `WAGTAIL_EMAIL_MANAGEMENT_ENABLED = False` 只关了「账号设置」页的邮箱面板（注释写着 115 轮就是为了不跳过设计 3.4 的验证）
- **问题**：只改 `User.email`，allauth 的 `EmailAddress` 里还是旧地址，而且是已验证、主地址：
  - `email_is_verified()` 仍然是真，新地址等于没验证就算「已加入」
  - allauth 的 `filter_users_by_email` 先查 `EmailAddress`，用旧地址加原密码照样能登录
  - 旧地址还占着，别人用它注册会被 `ACCOUNT_UNIQUE_EMAIL` 拒
  - （217 更正：原来推测 Wagtail 的表单会把 `New@Example.com` 按大小写原样存下来；测试机上实际存的是 `new@example.com`，这一条不成立）
  
  超管自己编辑自己时，`editing_self` 只去掉 `is_active`、`is_superuser`，邮箱照样能改
- **失败场景**：成员说邮箱换了，超管在底层后台直接改。之后通知发到新地址，登录却只认旧地址；旧邮箱要是已经被别人拿走，别人收不到验证码，但能用旧地址加上泄露的密码登录
- **怎么验证**：`test_wagtail_email_change_skips_verification`
- **状态**：已复现（大小写那一条除外）。测试机输出：
  ```
  [wagtail] POST -> 302；user.email='new@example.com' EmailAddress=[('old@example.com', True, True)] email_is_verified=True
  [allauth] 用旧地址登录 -> 登录了吗=2
  ```
  这条测试最后在 `assert person.email == "New@Example.com"` 上失败，原因就是上面那个大小写的错误推测

### 04-6 系统用户组在底层后台能改名、能删，代码按组名找组，改名后会悄悄另建一个没有权限的同名组

- **严重度**：低
- **位置**：`accounts/admin_users.py:118-119`（`SiteGroupViewSet` 照搬 Wagtail 的 `GroupViewSet`，新建、编辑、改名、删除都在）；`accounts/services.py:38-63`、`197-210`（`Group.objects.get_or_create(name=…)`）
- **问题**：「投稿者」被改名（比如改成「作者」）以后，`sync_submitter_group` 用 `get_or_create` 新建一个空的「投稿者」，上面没有 `access_admin` 和页面权限。之后新验证邮箱的成员进的是这个空组，打不开后台写文章；改名后的旧组留着原来的人，再也不同步。删掉「交大用户」或「校外用户」的话，挂在上面的 `FeatureGroupRestriction` 跟着级联删除，限制悄悄没了，下一次同步时再建一个空组。`docs/admin.md` 4.x 写着「角色本身不能在这里新建、删除、改权限（细粒度的在底层后台）」，但底层后台对系统组（`backoffice/forms.py:565` 的 `SYSTEM_GROUPS`）和预设角色没有任何保护
- **怎么验证**：超管在 `/wagtail/groups/<投稿者>/` 改名保存，再验证一个新账号的邮箱，看他所在的「投稿者」组有没有 `wagtailadmin.access_admin`
- **状态**：已核对代码（没写复现：组表单要带权限 formset）

### 04-7 文档库仍然开着：什么类型的文件都能传，`/media/documents/` 直链绕过 Wagtail 自己的 CSP 和集合隐私

- **严重度**：低（只有超管能上传；文档库本来就「不用」，见 `docs/admin.md` 7）
- **位置**：`sjtu_ow/settings/base.py`（`wagtail.documents` 在 `INSTALLED_APPS`，没设 `WAGTAILDOCS_EXTENSIONS`，默认 None，任何扩展名都收）；`sjtu_ow/urls.py:14`；`deploy/Caddyfile` 的 `handle /media/*`（只有 HSTS 和缓存头，没有 CSP）
- **问题**：Wagtail 自己通过 `/documents/<id>/<name>` 发文件时会加 `Content-Security-Policy: default-src 'none'`（`wagtail/documents/views/serve.py:110`），也查集合的查看限制。但文件就放在 `MEDIA_ROOT/documents/` 下，Caddy 按扩展名原样发 `/media/documents/x.html`，不带 CSP。一个 HTML 或 SVG 文档在本站同源下能执行脚本，可以读到非 HttpOnly 的 `csrftoken`，用来访超管的身份去 POST `/admin/`。设了「私有集合」的文档也能用直链拿到
- **失败场景**：超管把别人发来的「赛程.html」传进文档库，拿到链接发到群里；点开的后台用户被这个页面以自己的身份操作
- **怎么验证**：超管在 `/wagtail/documents/multiple/add/` 传一个带 `<script>` 的 `.html`，然后 `curl -I https://…/media/documents/<名字>.html`，看 `Content-Type: text/html` 和有没有 CSP
- **状态**：已核对代码

## 查过没问题

- **`WagtailAdminCSPMiddleware` 挡非超管**：在 `AuthenticationMiddleware` 之后，按 `request.path` 前缀判断，GET、POST、HTMX 一视同仁，都 302 到 `/admin/`。大小写不同的前缀（`/WAGTAIL/`）解析不到 Wagtail 的路由，会落到页面兜底的 404。`/wagtail/api/main/pages/`、选择器、预览、批量操作、报告、`editing-sessions` 都在 `/wagtail/` 下，非超管全被挡。匿名访问受保护的 `/wagtail/` 地址由 Wagtail 的 `require_admin_access` 跳到 `account_login`。只有 `login/`、`password_reset/`、`jsi18n/`、`sprite/` 在门外：后两个无害，`password_reset/` 因为 `WAGTAIL_PASSWORD_MANAGEMENT_ENABLED = False`（`password_reset_enabled()` 跟着是 False）不可用；`login/` 见 04-1
- **公开 API**：没装 `wagtail.api`，没有公开的页面 API；`wagtail.images` 的 serve 视图没挂路由；`django.contrib.admin` 装了但没挂 URL
- **`/documents/`、`/_util/authenticate_with_password/` 收超大编号**：都是 AutoField 主键查询，Django 6 对超出范围的整数查询直接返回空结果，得 404，不会 `OverflowError`
- **没有残留的 viewset**：全仓库不再有 `register_snippet`、`SnippetViewSet`、`ModelViewSet`、`register_admin_urls`、`admin.site.register`。赛事、内战、战队、评论、功能规则在 `/wagtail/` 下都没有编辑页，状态字段改不到。只剩 `SiteSettings`（`register_setting`）
- **全站设置的 Wagtail 表单**：`core/apps.py` 把 `SiteSettings.base_form_class` 设成 `SiteSettingsAdminForm`。三把密钥用 `PasswordInput(render_value=False)`，初始值清空，留空表示保留；`moderation_extra_body` 走同一个 `clean_extra_body`；`qq_group_url` 的 `https_only` 是模型校验器，两边都生效；首页和横幅的重新生成在 `core/signals.py` 的 `post_save` 里，不看是从哪个入口改的
- **用户删除、新建、批量删除、批量停用**：`UserCreateView` 和 `UserDeleteView` 都 `PermissionDenied`，列表上不出现入口。`accounts/wagtail_hooks.py` 替换了注册表实例的 `_scan_for_bulk_actions`，每次查询后去掉 `delete` 和 `set_active_state`，bulk 地址拿到 None 得 404（`accounts/tests/test_user_bulk_actions.py` 覆盖了）
- **底层后台停用账号的连带后果**：`UserEditView.save_instance` 调了 `after_deactivation`（取消待审申请、暂停招募），会提示队长身份。成员页和首页的重新生成、投稿者组的同步由 `accounts/signals.py`、`members/signals.py` 的信号负责，两个入口都会触发
- **账号设置页**：名字、邮箱、头像面板关了，`WAGTAIL_PASSWORD_MANAGEMENT_ENABLED = False`，不检查更新，不用 Gravatar
- **页面编辑**：`ArticlePage` 的 `base_form_class = ArticlePageForm`，超管在这里看到全部字段（有意）。`ArticlePage.save` 每次保存都重算 `body_plain`、字数和阅读分钟数，Wagtail 发布修订时也会调用。发布、撤下、删除、改 slug、移动都有 `content/signals.py` 接着做预渲染和列表刷新；`HomePage` 的置顶最多 3 篇，模型层也校验
- **页面树过滤**：`content/wagtail_hooks.py` 的过滤对超管不生效，底层后台现在只有超管能进，等于不起作用，但也没有坏处
- **重定向**：`RedirectMiddleware` 只处理 Django 返回 404 的请求；有静态文件的地址 Caddy 直接发，重定向不会被触发，也不会出错。只有超管能建重定向
- **日志动作注册**：`core`、`moderation`、`tournaments` 的 `register_log_actions` 只登记名称，没有副作用
- **没装的东西**：搜索推广（`wagtail.contrib.search_promotions`）没装；`wagtail.contrib.forms` 装了，但没有表单页模型

## 没来得及看

- 04-1、04-3 测试机打印的完整输出：本机只取了最后 120 行；结论是通过，具体打印的内容要重跑才能看到
- `/wagtail/workflows/`：超管重新启用审批工作流以后，新后台的发布路径（直接 `PublishRevisionAction`）和工作流会怎么交叉
- `/wagtail/sites/`、`/wagtail/collections/`：改站点主机名、给「默认封面」「默认头像」集合改名，会让 `core/covers.py` 按名字找集合的逻辑失效（新后台的集合页也能改名，不是 `/wagtail/` 独有，留给 02）
- Wagtail 编辑器里的页面评论和通知信（`templates/wagtailadmin/notifications/`）走不走 `core.mail` 的主题前缀
- 页面密码保护的 `_util/authenticate_with_password/` 有没有限流（要先有超管设了密码隐私才有意义）
