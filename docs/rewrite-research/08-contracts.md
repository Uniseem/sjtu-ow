# 08 · 前后端契约枚举（Vue API 层 / Go JSON 设计规格）

来源：契约枚举调研代理。基线 `ec44ae4`。

## 1. JS → 后端调用全集

### 1.1 全局机制（app.js）

- 无自身网络请求，但为所有 HTMX 请求统一注入 CSRF 头：htmx:configRequest 时从 document.cookie 读 csrftoken，设置 event.detail.headers["X-CSRFToken"]。
- htmx.config.allowEval = false、includeIndicatorStyles = false（CSP 兼容）。
- 迁移要点：**所有 HTMX POST 都带 X-CSRFToken 头（cookie 值），不是表单字段**。

### 1.2 自动保存协议（autosave.js ↔ core/autosave.py + AutosaveReplayMiddleware）——最核心的契约

**触发**：
- form[data-autosave]：文本类控件 input 后停 800ms；change（勾选/下拉/图片选择器/blur）后 60ms（文本 blur 立即）。
- 密码框、[data-autosave-skip] 控件不触发。
- 队列：data-autosave-queue="split" 的多个表单串行。
- 同表单一次只发一个请求；期间再改则置 again 完成后续发。
- 页面其他表单 submit 前先 flushAll()；beforeunload 有未存时询问。
- [data-autosave-button] 按钮被隐藏（无脚本时仍可普通提交）。
- form[data-autosubmit-file]（头像上传）：选好文件 → 先 flush 全页 → requestSubmit() 走普通整页 POST。
- htmx 换入新表单后重新 setUp；window.owAutosave = {flush, setUp} 供外部调用。

**请求**：
```
POST <form 的 action 或当前页 URL>          // multipart/form-data（FormData 整个表单）
credentials: same-origin
Headers:
  X-Autosave: 1
  X-Autosave-Key: <24 位随机字母数字，每表单实例生成一次>
  X-CSRFToken: <表单内 csrfmiddlewaretoken 或 cookie>
  Accept: application/json
```

**响应 JSON 字段语义**：

| 字段 | 类型 | 语义 | 前端消费方 |
|---|---|---|---|
| ok | bool | not errors | 隐含 |
| saved | string[] | 本次实际保存的表单字段名（含 prefix） | 状态行「其余已保存 N 项」 |
| errors | object<string, string[]> | 键=字段名（含 formset prefix）或 __all__；值=错误文案数组 | 字段下插 p.c-field__error + is-invalid；__all__ 进状态行 |
| location | string | 新建对象首次保存后的编辑地址 | history.replaceState + 重写 form.action |
| replace | object<CSS选择器, HTML字符串> | 就地替换页面块 | outerHTML 换块保持焦点，setUp + 派发 ow:replaced 事件（拖拽板监听重绑） |
| values | object<字段名, 值> | 服务器回填（slug 跟随标题、latest_revision 版本号、清文件框） | checkbox 设 checked、file 清空、聚焦/在途的文本框跳过 |
| saved_at | string | HH:MM | 状态行「已保存 14:32」 |
| retry | bool | 仅 AutosaveReplayMiddleware 发：这个 key 此前已在新地址创建过对象 | 前端立即向 location 重新保存一次 |

**错误语义（前端状态机）**：
- HTTP 401/403/404，或 200 但非 JSON（=登录页）：permanent，不再重试，文案「保存失败：登录状态已失效或没有权限」。
- 表单含已选文件（队标）失败：不自动重试，等下次改动。
- 其他失败：指数退避 5s × 2^n，上限 60s。状态行 data-state：idle/saving/saved/partial/failed。

**服务端规则（core/autosave.py）**：
- wants(request) = POST && X-Autosave == "1"。
- 表单整体有效 → 整体保存；否则只存「自身有效的已改字段」：valid_changes() 排除出错字段 + autosave_together 组（跨字段规则，如 (roster, registration_window)、ContactMethodForm 的 (("type","value"),)、ArticleForm 的 ("slug",)）；__all__ 错误且无组 → 全不存。
- 已有对象：save_valid_fields() 写到从库里重取的副本再 update_fields 保存，IntegrityError 返回 []。
- 新对象：new_from_valid_fields() 用首改的有效字段创建草稿行（空标题也建），返回 location。
- log_edit()：同一人 30 分钟内对同一对象的编辑合并为一条日志。

**AutosaveReplayMiddleware**：
- key 校验 X-Autosave-Key 匹配 [A-Za-z0-9]{16,64}，缓存键 sjtu_ow:autosave-made:{user.pk 或 -}:{key}，TTL 24h。
- 前置拦截：同 key 在别的 path 已创建过 → 直接回 retry:true JSON（不再进视图）。
- 后置：视图 200 JSON 且带新 location → 写缓存。作用：网络丢包后重试不会创建第二篇草稿。

**所有参与自动保存的端点**：
| URL | 视图 | 特殊返回 |
|---|---|---|
| POST /me/ | me_profile | save_valid_fields |
| POST /me/avatar/ | data-autosubmit-file，整页 POST | redirect 回 /me/ |
| POST /me/game-accounts/<pk>/、/me/contacts/<pk>/ | autosave JSON | |
| POST /teams/<pk>/manage/（form=profile） | _autosave_profile | replace["[data-team-logo]"]、values={logo_file:"", remove_logo:false} |
| POST /admin/articles/new/、/admin/articles/<pk>/ | articles._autosave | 新建 values.latest_revision、values.slug、replace["[data-article-preview]"]；并发冲突 → errors.__all__=[STALE_MESSAGE] |
| POST /admin/pages/new|<pk>/ | 同 article 模式 | |
| POST /admin/categories/new|<pk>/ | | |
| POST /admin/images/<pk>/ | | |
| POST /admin/member-groups/new|<pk>/、/admin/users/<pk>/、/admin/teams/edit/<pk>/ | | |
| POST /admin/member-groups/people/<pk>/title/ | 仅 title 字段 | |
| POST /admin/settings/site/ | SiteSettings | |
| POST /admin/tournaments/new|edit|copy/<pk>/、/admin/scrims/… | events._autosave | 新建 location=/admin/tournaments/<pk>/edit/、replace["[data-event-next]"] |
| POST /admin/settings/typography/ | formset，逐行 add_prefix(name)；保存后重新生成字体 CSS | |
| POST /admin/scrims/<pk>/split/（queue="split"，两表单共用） | split_admin._autosave | action=select → replace["[data-split-board]"]（整板）；action=save → replace["[data-split-copy]"]、[data-team-problem:xxx]、[data-team-total]、[data-total-a|b]、[data-gap] |

### 1.3 backoffice.js（后台增强）

**A. 搜人（data-person-search）**
```
GET /admin/member-groups/<pk>/people/?q=<昵称或邮箱>
Headers: Accept: application/json
→ 200 JSON {"results": [{"id": <user pk>, "label": "<昵称 + 邮箱或#id>"}]}
```
250ms 防抖；label 由 person_label(person, viewer) 决定（有 sees_emails 权限才显示邮箱）；只搜「已加入且不在组里的人」。

**B. 行内块替换（data-inline：加入/上移/下移/移出成员）**
```
POST /admin/member-groups/<pk>/people/add/        body: FormData{user: <pk>}
POST /admin/member-groups/people/<pk>/remove/
POST /admin/member-groups/people/<pk>/move/       body: FormData{direction: up|down}
Headers: Accept: application/json, X-CSRFToken
→ 200 JSON {"ok": bool, "problem": str, "replace": {"[data-memberships]": <整块 HTML>}}
```
失败/非 200 → 降级普通表单提交整页刷新。换入块内的 autosave 表单由 owAutosave.setUp 重绑。

**C. 图片选择对话框（data-image-picker / data-image-dialog）**
- 打开：fetch(chooser_url)（GET /admin/images/chooser/?q=&collection=&page=）→ HTML 片段塞进 dialog body；response.redirected 或非 ok → 「登录状态已失效」提示。
- 对话框内 GET 表单（搜索/筛选/翻页）同样 fetch 拼 query 装载；a[data-chooser-nav] 分页链接同。
- 上传并选用：
```
POST /admin/images/chooser/upload/     multipart: collection=<pk>, file=<图片>
→ 200 JSON {"id": <image pk>, "title": str, "thumb": <缩略图 URL>}
→ 4xx JSON {"error": str}
```
- 选中后把 id 写入 [data-image-picker-input]、触发 change（让 autosave 听见）、缩略图进预览。

**D. 其他（无网络）**：data-confirm、data-autosubmit、data-select-all。

### 1.4 markdown-editor.js（EasyMDE 封装）

widget 注入属性：data-markdown-editor、data-preview-url=/admin/markdown/preview/、data-upload-url=/admin/markdown/image/、data-max-size=5242880。

**预览**：
```
POST /admin/markdown/preview/    body: urlencoded  text=<markdown，服务端截 200 000 字>
→ 200 text/html：与公开页同一渲染器产出的 HTML 片段，innerHTML 进 .md-preview
```
200ms 防抖，sequence 号防乱序。

**贴图/拖图上传**：
```
POST /admin/markdown/image/      multipart: image=<file>
→ 200 JSON {"url": "/media/images/…max-1600x1600 rendition…"}   （插入 ![](url)）
→ 403 {"error":"你没有上传图片的权限。"} / 400 {"error": "…"}
```
入「投稿图片」集合，走 Wagtail 图片表单校验。

### 1.5 state.js → /_fragments/state/

**前端**：无 ow_logged_in=1 且无 ow_flash=1 cookie → 不发请求；body data-state-filled="1" → 不发；否则收集全页 [data-slot] 值，htmx.ajax GET /_fragments/state/?slots=…（swap:"none"，靠响应内 hx-swap-oob="true" 片段自定位替换）；预渲染页等 prerenderingchange；8s 超时兜底撤骨架。

**服务端**（core/views.py:state_fragment）：
- 限流 120 次/IP/分钟，超限 429 + Retry-After: 60（空体）。
- slots 参数：逗号分隔原始名，最多 12 个（MAX_SLOTS），名字:参数按第一个冒号切；空缺省 ("account","messages")。
- 响应：HTML 拼接，每个已注册插槽渲染其模板（oob=True → 根元素 hx-swap-oob="true"，id 形如 slot-account、slot-team-join）。
- 头：Cache-Control: private, no-store、Vary: Cookie；顺带 get_token(request) 确保预渲染页拿到 csrftoken cookie。
- 会话失效清理：未登录但仍带 ow_logged_in → 删该 cookie；请求了 messages 插槽且带 ow_flash → 删。

### 1.6 评论全部 hx 端点

统一形态：响应 = 整个 comments/section.html 重渲染（hx-target="#slot-article-comments" hx-swap="outerHTML"）；登录失效时 200 + HX-Redirect: /accounts/login/ 头。

| 端点 | 方法 | 请求体 |
|---|---|---|
| /comments/<page_pk>/new/ | POST | body，hx-include="#comment-sort" 附带 sort |
| /comments/<page_pk>/more/?page=N&sort= | GET | hx-target="#comment-list" hx-swap="beforeend"，响应 _more.html（含 oob 更新的 #comments-more） |
| /comments/<pk>/reply/ | POST | body |
| /comments/<pk>/like/ | POST | — |
| /comments/<pk>/edit/ | POST | body |
| /comments/<pk>/delete/ | POST | —（hx-confirm） |
| /comments/<pk>/pin/、/unpin/ | POST | — |
| /comments/<pk>/hide/、/unhide/ | POST | —（hide 带 confirm） |

限流：评论 3/分钟 + 100/天（按用户）；点赞 60/分钟；超限以「问题列表」形式重渲染 section（保留草稿 draft_body）。非 HTMX 请求（no-JS）：redirect 回文章 #comments + messages。section 模板上下文：page, thread(items/total/has_next/next_number/liked), interactive, can_post, post_problems[], can_moderate, sort(new|top), draft_body, oob。

### 1.7 个人中心行内编辑 hx 模式（Django 模板 partialdef）

| 端点 | 方法 | hx 行为 | 响应 |
|---|---|---|---|
| GET /me/contacts/（取消） | GET | hx-target="#contact-list" outerHTML | 整列表（partialdef contact_list，含 _htmx_oob.html） |
| GET /me/contacts/?new=1 | GET | hx-target="#create-contact" innerHTML | 新建表单 |
| GET /me/contacts/<pk>/ | GET | hx-target="#contact-<pk>" outerHTML | 该行变编辑表单 |
| POST /me/contacts/（新建） | POST hx-post | 失败 → #create-contact innerHTML；成功 → #contact-list outerHTML | 含 oob：_incomplete + slots/messages |
| POST /me/contacts/<pk>/（编辑行，data-autosave） | POST | 优先走 autosave JSON；普通提交成功 → 该行 outerHTML | |
| POST /me/contacts/<pk>/delete/ | POST | #contact-list outerHTML + hx-confirm | 整列表 + oob toasts |
| game_accounts 全套同构 | | #game-account-list / #game-account-<pk> / #create-game-account | |

关键模式：**每个 HTMX 片段响应都捎带 me/_htmx_oob.html（#profile-incomplete + #slot-messages 两个 oob 块）**。

### 1.8 其余 JS（无后端请求，但属行为契约）

theme.js（localStorage ow-theme、storage 事件同步、View Transition）；loading.js/arrival.js（sessionStorage ow-loading，200ms 后才记，20s 过期）；contextmenu.js（自绘右键菜单，「在站内搜索」跳 /search/?q=）；scrim-split.js/tournament-teams.js（SortableJS 拖拽只改隐藏 input 再触发 autosave；容量规则客户端先拒；监听 ow:replaced 重绑）；typography-preview.js（纯 CSS 变量预览）。

## 2. Cookie 契约

| Cookie | 设置者 | 属性 | 读取方 | 为什么 |
|---|---|---|---|---|
| sessionid | Django SessionMiddleware | HttpOnly=True; SameSite=Lax; Max-Age=14天；prod 加 Secure | 仅服务端 | 身份 |
| csrftoken | CsrfViewMiddleware | **HttpOnly=False（故意）**; SameSite=Lax; prod Secure | app.js（HTMX 头）、autosave.js（兜底）、backoffice.js（表单隐藏域优先） | 预渲染页无表单无 token，必须能从 cookie 读出放进 X-CSRFToken 头 |
| ow_logged_in | LoggedInHintCookieMiddleware | 值恒 "1"；max_age=SESSION_COOKIE_AGE；httponly=False；samesite/secure 随会话 | 只有 state.js | 登录提示位：预渲染页脚本据此决定是否请求 /_fragments/state/。不含身份数据故可非 HttpOnly |
| ow_flash | 同上（_flash_cookie） | 值 "1"；会话级；非 HttpOnly | state.js | 「有一条 flash 消息在等」提示位：匿名预渲染页 + 有消息 → 也要拉 fragments（显示 toast）。messages used 后删 |
| localStorage ow-theme | theme.js | light/dark/无 | theme.js | 主题；跨 tab storage 事件同步 |
| sessionStorage ow-loading | loading.js/arrival.js | {at, from}，20s 有效 | arrival.js | 加载条跨页续播 |

**预渲染安全联动**：预渲染生成器拒绝任何「带 Set-Cookie 的响应」落盘——提示 cookie 是浏览器端 JS 判断登录态的唯一线索。Vue/Go 版需要等价机制（如非 HttpOnly 登录提示位 + 一个 personalize 端点）。

## 3. slots 注册表全表

| 插槽名 | 注册处 | 渲染模板 | 出现页面 | 匿名/登录内容 |
|---|---|---|---|---|
| account | core/apps.py | slots/account.html → components/account_area.html，id=slot-account | 所有页面（顶栏） | 匿名=登录/注册链接；登录=昵称+账号菜单 |
| messages | core/apps.py | slots/messages.html，id=slot-messages | 所有页面（toast 容器） | 匿名=空；有 flash 时为 toast 列表 |
| footer-account | core/apps.py | slots/footer_account.html | 所有页面页脚 | 匿名=登录/注册；登录=个人中心/退出 |
| my-agenda | core/apps.py（core/agenda.py） | slots/agenda.html | 仅首页 | 匿名=空壳；登录=「我的安排」最多 4 条 |
| article-comments:<page_pk> | comments/apps.py | comments/section.html | 文章页 | 匿名=只读评论区；登录=可交互，版主可管理 |
| team-join:<team_pk> | teams/apps.py | teams/slots/join.html | 战队详情页 | 匿名=登录提示；登录=申请表单/已是成员/队长入口/不可申请原因 |
| scrim-actions:<scrim_pk> | scrims/apps.py | scrims/slots/actions.html | 内战详情页 | 匿名=请先登录；登录=报名表单/我的分队位置/群链接 |
| tournament-actions:<tournament_pk> | tournaments/apps.py | tournaments/slots/actions.html | 赛事详情页 | 匿名=登录提示；登录=报名入口/我的状态/选手联系方式/散人池提示 |

上下文构造与实时页共用（actions_context / section_context），保证静态与动态一致。scrims/views.py 另有独立的 GET /_fragments/scrims/<pk>/actions/（private, no-store）做同一件事。

## 4. 模板清单（共 232 个文件）

### 根 templates/（118）
| 文件/目录 | 区域 | 角色 |
|---|---|---|
| base.html | 全站 | 页面骨架 |
| account/*.html（27） | 账号 | allauth 覆写：登录/注册/验证码/改邮箱/改密码/重置/重认证 + _form、_back_to_security、_why、layout、4 个 base |
| account/email/*（19） | 账号邮件 | allauth 六类信的 subject/txt/html 三件套 + base_message.txt |
| account/messages/*.txt（11） | 账号 | allauth flash 消息文案 |
| account/snippets/*（2） | 账号 | already_logged_in、warn_no_email |
| allauth/layouts/*（3） | 账号 | 三种布局覆写 |
| components/*（22） | 全站组件 | 见 07 |
| email/*（6） | 邮件 | layout/letter/plain + parts/{button,code,facts} |
| errors/*（6） | 错误页 | 500 页显示 request_id；429 显示 retry_after |
| me/*（12） | 个人中心 | base、_nav、_htmx_oob、_incomplete、_letters、profile、contacts、game_accounts、security、registrations、teams、delete |
| slots/*（4） | 插槽 | account/messages/footer_account/agenda |
| core/home.html | 兜底 | 无 Wagtail 站点时的首页 |
| wagtailadmin/* + wagtailusers/*（4） | Wagtail 覆写 | 后台外观中文化/通知信框架 |

### 各应用 templates/（114）
| 应用 | 数量 | 内容 |
|---|---|---|
| core | 17 | 兜底首页、退订页、styleguide ×2、letters ×2、admin ×6、prerender、fonts ×5 |
| backoffice | 38 | base；content ×12、events ×3、members ×7、review ×1、settings ×2、letters ×2、parts ×6、widgets/image_picker、home、confirm_delete |
| content | 8 | home_page、article_index_page、article_page、standard_page、_toc、submit、sitemap.xml、widgets/markdown_editor |
| teams | 11 | index/detail/create/apply/manage、_alumnus/_logo/_member_contact、slots/join、admin ×2 |
| scrims | 13 | index/detail/me、slots ×2、admin/{split,confirm} + 分队板局部 ×6 |
| tournaments | 13 | index/detail/register/individual_signup/registration_detail、_starts_at、slots/actions、admin ×4 + 局部 ×2 |
| moderation | 3 | index/detail/avatars |
| comments | 7 | section + _{composer,item,reply,own,like,more} |
| members | 2 | index/detail |
| search | 1 | results |
| accounts | 1 | admin/user_edit |

## 5. 头与缓存契约

### SECURE_CSP（base.py:275-290，逐条）
```
default-src 'self'
script-src 'self' 'inline-speculation-rules'
style-src 'self'
img-src 'self' data:
font-src 'self'
connect-src 'self'
frame-src 'self' https://player.bilibili.com
frame-ancestors 'none'
base-uri 'self'
form-action 'self'
```

### ADMIN_CSP（/admin/ 与 /wagtail/）
```
default-src 'self'
script-src 'self' 'unsafe-inline' 'unsafe-eval'
style-src 'self' 'unsafe-inline'
img-src 'self' data: blob:
font-src 'self' data:
connect-src 'self'
frame-ancestors 'self'
```

### EMAIL_CSP（邮件预览帧）
```
default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:;
frame-ancestors 'self'; base-uri 'none'; form-action 'none'
```

### 中间件加的头
RequestIDMiddleware：X-Request-ID（12 位随机，服务端生成）；其余见 06。

### Caddy 路由与缓存
| 路径 | 处理 | Cache-Control |
|---|---|---|
| /static/** 带 12 位 hash | 直发 | immutable 1 年 + HSTS |
| /static/* 其余 | 直发 | 300s must-revalidate |
| /media/fonts/（哈希切片） | 直发 | immutable 1 年 |
| /media/fonts/* 其他 | 404 | — |
| /media/images/* | 直发 | immutable 1 年 |
| /media/* 其他 | 直发 | 86400s |
| admin/wagtail/accounts/me/_fragments/healthz、非 GET/HEAD、带 query | 透传 Django（header_up X-Real-IP） | Django 决定 |
| @prerendered 命中 | 直发静态 | max-age=0 must-revalidate + page_security 全套 |
| 502/503/504 | maintenance.html | no-store |

压缩 encode zstd gzip。Django 侧 prod：SECURE_SSL_REDIRECT、SESSION/CSRF_COOKIE_SECURE、HSTS 三件套、X_FRAME_OPTIONS=DENY、REFERRER_POLICY=same-origin、NOSNIFF。/_fragments/state/ → private, no-store + Vary: Cookie；/calendar/<token>.ics → private, max-age=900 + noindex。

### 预渲染安全红线（core/prerender.py::render_html）
匿名 Client（x-prerender: 1）渲染后四道检查，任何一条触发 PrerenderError 拒绝写盘：① 状态码 200（404/410 → 删文件）；② Content-Type 含 text/html；③ response.cookies 必须为空；④ HTML 不得含 csrfmiddlewaretoken / csrf_token / sessionid 三个标记之一。

## 6. 邮件模板契约

- layout.html：内联样式 + 表格布局；color-scheme light；隐藏 preheader；红头（cid:ow-mark）+ 地平线（cid:ow-horizon）+ 白卡（greeting → body → closing/signature/date）+ 页脚（reason + no_reply + 站点链接）。块标注 data-letter-head/horizon/card/foot（测试锚点）。
- letter.html（extends layout）：notice（第二封起提示块）、lead、facts 键值表、code 大号验证码、items 列表、paragraphs、action 按钮（红色胶囊 + 可读 URL 灰框兜底）、note、reason+unsubscribe。
- plain.html：纯文本信（Wagtail 原生通知）套同一信纸。
- 渲染通道 core/letters.py::render(letter, name) → txt+html 双版本；浏览器预览把 cid: 换成 /static/。

**34 封信 key 清单**（core/email_samples.py）：

| key | 信 | 收件人 |
|---|---|---|
| verify | 注册/改邮箱验证码 | 本人 |
| reset | 找回密码验证码 | 本人 |
| unknown | 没有注册的邮箱（防枚举） | 填写的邮箱 |
| exists | 已注册过的邮箱 | 填写的邮箱 |
| smtp | SMTP 测试邮件 | 操作的管理员 |
| apply | 收到入队申请 | 队长 |
| apply-ok / apply-no | 申请通过 / 未通过 | 申请人 |
| applications-waiting | 申请等你处理（汇总） | 队长 |
| removed | 被移出战队 | 被移除的人 |
| member-left | 队员退出（附受影响报名） | 队长 |
| captain | 成为队长 | 新队长 |
| disbanded | 战队解散 | 全体成员 |
| submitted | 报名已提交 | 队长 |
| entered | 你已被报名参加 | 名单队员 |
| approved / rejected | 报名通过 / 驳回 | 队长 |
| cancelled | 赛事取消 | 队长、临时队成员 |
| formed | 已编入临时队伍 | 被编入的成员 |
| returned | 移出临时队/队伍解散 | 受影响成员 |
| left | 临时队成员退出 | 赛事管理员 |
| tournament-reminder | 赛事开始提醒 | 参赛队员 |
| unplaced-reminder | 散人未编提醒 | 散人池成员 |
| tournament-update / -again | 赛事有更新 / 第二封起 | 全部报名者 |
| reminder | 内战开始提醒 | 全部报名者 |
| scrim-update / scrim-cancelled | 内战有更新 / 取消 | 全部报名者 |
| new-tournament / new-article / new-scrim | 活动通知（群发，附退订） | 开活动通知的成员 |
| patrol | AI 巡查发现汇总 | 设置邮箱或全体超管 |
| ask-author | 要求修改内容 | 作者 |
| avatar-taken-down | 头像被撤下 | 上传的人 |

## 对 Vue/Go 重构最要紧的接口速查

1. **JSON 端点（Go 直接照抄）**：/_fragments/state/（HTML+oob）、autosave 家族（统一 {ok,saved,errors,location,replace,values,saved_at[,retry]}）、搜人 {results:[{id,label}]}、成员组 add/remove/move/title、选图上传 {id,title,thumb}、markdown {preview,image}、/healthz。
2. **HTML 片段端点（Vue 需决定 JSON 化）**：评论 10 个端点（整 section）、me 联系方式/游戏账号 10 个 hx 端点、选图器 GET。
3. **普通表单 POST + redirect + flash**：报名、战队动作、头像、退订（RFC 8058 免 CSRF）、/letters/*。
4. **必须保留的语义**：autosave 的 key 重放防重、指数退避、__all__ 错误通道、replace 选择器协议；状态片段的 cookie 门控与 Vary: Cookie；限流键（state:IP 120/m、评论 3/m+100/d、点赞 60/m、日历 30/m）。
