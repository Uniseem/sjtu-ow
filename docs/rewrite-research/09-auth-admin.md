# 09 · 认证与后台（Go 认证模块 + Vue 后台规格）

来源：认证/后台/测试调研代理。基线 `ec44ae4`。

## 一、认证体系（Go 版逐流复刻规格）

### 1.1 技术底座
- django-allauth 65.x，邮箱即用户名：USERNAME_FIELD="email"、REQUIRED_FIELDS=["nickname"]（accounts/models.py:110-111），email unique。
- 双认证后端：ModelBackend + allauth（base.py:150-153）。
- 密码哈希：**Argon2 优先、PBKDF2 兜底**（base.py:169-172），Django 默认参数 argon2id, t=2, m=102400 KiB(100MB), p=8。存 PHC 串（$argon2id$v=19$m=102400,t=2,p=8$…）。**Go 端用 golang.org/x/crypto/argon2.IDKey 可直接验证，无需重置密码。**（测试里换 MD5 是为了速度，与生产无关。）
- 密码校验器：相似度/最小 8 位/常见弱密码/纯数字（base.py:155-167）。

### 1.2 注册（设计 3.1）
- 表单字段：邮箱+密码1+密码2（allauth ACCOUNT_SIGNUP_FIELDS）+ 额外表单 SignupExtraForm（昵称 2–16 字去首尾空格、是否交大单选、两个必须分开勾的协议，accounts/forms.py:25-65）。
- 流程：提交 → 建「邮箱未验证」账号 → 发 6 位数字验证码 → 输码验证 → **自动登录** → 落到个人中心「基本资料」并提示补游戏 ID/联系方式（adapter.py:42-51）。
- 验证码参数：15 分钟有效、最多试 3 次、支持重发；重发限流 confirm_email: 1/10s/key。
- 邮箱验证强制（mandatory）；ACCOUNT_UNIQUE_EMAIL=True、大小写不敏感。
- 注册后置：记 agreed_terms_at / agreed_cross_border_at 时间戳（adapter.py:92-107）；signal 自动进「交大用户/校外用户」组、按条件进「投稿者」组。
- 限流（按访客 IP）：signup 20/m/ip。**关键坑：adapter 重写 get_client_ip 取 X-Real-IP**（Caddy 传入），否则反代后一人锁全站（adapter.py:53-57）。
- 邮件文案统一走信纸框架 render_mail（adapter.py:66-90），验证码/重置码剩余分钟数注入模板。

### 1.3 登录 / 退出
- 邮箱+密码；防枚举 ACCOUNT_PREVENT_ENUMERATION=True——错误提示统一「邮箱或密码不正确」。
- 限流：login 30/m/ip；login_failed 10/m/ip + 5/300s/key。
- 未验证邮箱不能登录（设计 3.1）；停用账号拒绝。
- 会话：SESSION_COOKIE_AGE=14 天、HttpOnly、SameSite=Lax；生产加 Secure、SSL 重定向、HSTS 1 年 preload。**CSRF Cookie 特意不设 HttpOnly**（HTMX 静态脚本要读）。
- 附加提示 Cookie ow_logged_in=1（不含身份、非 HttpOnly、随会话删除）供预渲染静态页判断登录态。
- 退出：GET 确认页 + POST 真正登出，回 /。

### 1.4 改密码 / 重置密码
- 改密码：必须输旧密码；限流 change_password 5/m/user、reauthenticate 10/m/user。
- 重置：邮箱 → 6 位验证码（3 分钟有效、最多试 3 次）→ 设新密码；限流 reset_password 20/m/ip + 5/m/key、reset_password_from_key 20/m/ip。防枚举：无论邮箱是否存在提示一致。
- Wagtail 自带的改密/重置已关（WAGTAIL_PASSWORD_MANAGEMENT_ENABLED=False）。

### 1.5 改邮箱（v7.19）
- ACCOUNT_CHANGE_EMAIL=True + 新邮箱验证码验证后才替换。
- **改前必须重输密码**（ACCOUNT_REAUTHENTICATION_REQUIRED=True，5 分钟窗口）。
- Wagtail 后台「账号」页改邮箱已关（WAGTAIL_EMAIL_MANAGEMENT_ENABLED=False）——否则验证过邮箱的投稿者能绕过验证。

### 1.6 注销 / 导出
- 导出 GET /me/export/：每用户每小时 5 次；JSON 下载、no-store；内容清单由 EXPORTED/NOT_EXPORTED 字典逐列声明并被测试盯住（accounts/services.py:427-474）。
- 注销 GET/POST /me/delete/：必须输当前密码；每用户每小时 5 次（防盗号会话暴力试密码）；队长必须先转让/解散；执行为**匿名化而非删除**（撤报名→退临时队→删游戏 ID/联系方式/邮箱记录→deleted-N@deleted.invalid→停用→清超管标记→set_unusable_password→清组→删送审记录）。

### 1.7 特殊机制与已知漏洞
- createsuperuser：新建超管邮箱直接 trust_email 标已验证+主邮箱（新站没 SMTP 也能登录配 SMTP）。
- verify_email <邮箱> 管理命令：发信坏了时手工标验证。
- **217-04-1（高，未修，已复现）**：/wagtail/login/（sjtu_ow/urls.py:12）和 /_util/login/（wagtail_urls 引入）是不走 allauth 的两个侧门——未验证邮箱的账号能登录，且**无任何失败限流**可无限撞库（含超管）。core/middleware.py:51-58 的门只拦「已登录的非超管」，匿名请求照样进。复现脚本 handoff/rounds/217-second-review/findings/04-wagtail_repro_test.py。**Go 重构必须引以为鉴：只保留一个登录入口。**
- 同轮相关：04-3（/wagtail/ 用户编辑页绕过账号服务）、04-4（改 is_sjtu 后用户组被改回）、04-5（那里改邮箱不用验证）——Go 版均无此问题空间。

### 1.8 功能门禁（非认证但与账号耦合）
- can_use(user, feature)：单用户规则 > 组限制 > 默认允许；拒绝原因永不展示（accounts/permissions.py:15-32）。
- 唯一在前台查 email_is_verified 的功能是投稿（content/views.py:106）——其余功能只看 is_active。

## 二、后台

### 2.1 结构与门禁（docs/admin.md 第 1–3 章）
- 自写后台在 /admin/；Wagtail 管理界面挪到 /wagtail/ 只给超管应急（编辑细粒度组权限、看修订历史、重定向）；非超管已登录访问 /wagtail/* 一律 302 回 /admin/（core/middleware.py:43-63，同时给两个前缀套后台 CSP）。
- 八大类声明在 backoffice/nav.py:50-127：首页 / 内容（文章、分类、网站页面、图片）/ 活动（赛事、内战）/ 成员（用户与权限、战队、成员分组）/ 审核（报名、内容、头像、评论）/ 数据（活动数据）/ 设置（全站设置、字体库、排版设置、静态页面、操作记录）/ 手册；「用户与权限」另有第二排小标签（用户/角色）；单页大类无标签条。
- placed(section, tab, subtab, allowed=...) 门禁三步（nav.py:225-256）：未登录→登录页；无 access_admin→403；**不满足所在标签的 allowed 函数→403（视图不被调用）**。比标签更严的页面用 allowed= 单独声明：图片集合三个页只给超管（views/images.py:260,292,318）。announce 按 kind 动态放置。
- access.py 各门槛：can_enter = is_superuser 或 wagtailadmin.access_admin（每个验证过邮箱的成员经「投稿者」组都有）；各标签 = 内容编辑组权限 / Wagtail 图片集合策略 / tournaments、scrims 的 can_manage / 评论 can_moderate / reviews_content / views_activity / 超管。
- 自动保存约定：表单挂 data-autosave（文本停 0.8s、勾选 60ms 就发，X-Autosave: 1，失败 5s 起指数退避到 60s）；data-autosave-button 隐藏原生保存按钮（无脚本时仍可提交）；data-autosubmit-file 选文件即传；data-autosave-queue 排队防互相覆盖；新建首存带 X-Autosave-Key。服务端规则见 08。

### 2.2 backoffice/views/ 逐页清单（页 → 权限）
| 文件 | 页面 | 权限 |
|---|---|---|
| home.py:23 | 后台首页（问候、待办、我的文章、超管上线清单） | can_enter |
| letters.py:28,41 | 「发信」等待/确认 | can_enter |
| articles.py:90,267,296,312,320,331 | 文章列表/新建/编辑/预览/撤下/删除 | 门=can_enter；视图内按 Wagtail permissions_for_user（can_publish/can_unpublish/can_delete/他人草稿不可见） |
| categories.py:29,47,101 | 分类列表/新建编辑/删除 | edits_categories；新建/删除另需 add/delete |
| pages.py:61,89,138,145,193 | 网站页面列表/编辑/预览/首页置顶(≤3)/栏目简介 | edits_site_pages；置顶走 HomePage 草稿+发布 |
| images.py:71,114,149,194,212,236,260-318 | 图片库/上传/编辑/删除/选图对话框/对话框内上传/集合三页 | uses_images（集合策略）；实例级 change/delete 视图内判；集合三页 allowed=is_superuser |
| events.py:192,274-329 | 赛事列表/新建/编辑/复制/删除（只有从未发布的草稿可删） | runs_tournaments |
| events.py:357,418-460 | 内战列表/新建/编辑/复制/删除 | runs_scrims |
| members.py:68-232 | 用户列表/编辑/单人规则 | is_superuser；停启用走 deactivate/reactivate 服务，不能停自己 |
| members.py:232-281 | 「角色」：角色列表、组功能限制 | is_superuser |
| members.py:302,329 | 战队列表/编辑（指定队长、解散入口） | is_superuser |
| members.py:374-570 | 成员分组全套 + 搜人/加人/移人/排序/改职务 | edits_member_groups；新建/删除另需权限 |
| settings.py:24 | 全站设置（SiteSettings 表单、发测试信、试备份） | is_superuser |
| settings.py:55 | 操作记录（页面+模型日志统一） | is_superuser |
| comments.py:26,54 | 评论列表/单条操作 | moderates_comments；恢复/取消置顶需内容编辑 |
| tournaments/review_admin | 报名审核列表/批量通过/导出 CSV/详情/操作 | runs_tournaments |
| moderation/admin_views + avatar_admin | AI 巡查列表/试发/详情/处理/要求作者修改；头像审核 | reviews_content |
| core/activity | 活动数据 | views_activity |
| core/admin_manual | 后台手册 | reads_manual |
| core/fonts + prerender_admin | 字体库 8 页 / 排版 / 预渲染三页 | is_superuser |
| content/markdown_views | Markdown 预览 / 编辑器贴图 | content/articles 标签 |

### 2.3 Wagtail 还提供什么（Go/Vue 版需找等价物）
1. **页面树与路由**：HomePage（父=Page，子=ArticleIndexPage/StandardPage）、ArticleIndexPage（父=HomePage，子=ArticlePage）、ArticlePage（父=栏目页，无子页）、StandardPage。路由靠 wagtail_urls 兜底按 slug 树解析。**Go 版等价物：自建 pages 表 + 前缀路由匹配 + 每类型字段表**。修订/草稿/定时发布用 save_revision、PublishPageRevisionAction/UnpublishPageAction。
2. **图片库**：集合树（投稿者只能传「投稿」集合）、集合权限策略做门禁；renditions：fill-WxH-c50 / max-WxH 规格；上传即转 WebP（q80）、上限 5MB、jpg/png/webp；缩略图缓存 LocMem 600s/2000 条防每图一查询；**未用焦点裁剪，全部固定居中 c50**——Go 版实现可简化。特殊集合：「默认封面」「默认头像」池按集合名找。
3. **富文本 vs Markdown**：**正文自 192 轮起是纯 Markdown**（CommonMark+表格+删除线、单换行即换行、禁 HTML、标题降级、独占一行的本站图片变 figure、B 站链接变播放器）；字数/阅读分钟/纯文本保存时算好存字段。后台编辑器是自写工具栏+预览接口。Vue 版可用 markdown-it 直接复刻同一渲染规则（Go 版则用 goldmark 对拍）。
4. **Wagtail 管理界面残留**（只给超管）：登录页指向 allauth；单语言单时区；禁更新检查、禁 Gravatar；用户批量操作删掉「删除/设置启用状态」（accounts/wagtail_hooks.py）；站点配色。
5. **locale/zh_Hans**：补 Wagtail 缺的百来条翻译并把「帐号」统一成「账号」；.mo 由标准库编译，测试保证 po/mo 同步。Go 版无需此物。
6. **其他照用件**：SiteSettings、操作记录模型 + register_log_actions、bilibili embed finder、数据库搜索后端、重定向应用。wagtail.contrib.forms 已装但无表单页；文档库装着但基本不用且有 217-04-7 直链风险——**Go 版可整体去掉**。

### 2.4 docs/admin.md 目录
# 后台（v7.0 起自己写的后台）；## 1. 原则（6 条）；## 2. 架构（2.1 Wagtail 那边留下什么：留着照用与去掉的完整清单）；## 3. 布局（b-top/b-head/b-tabs/b-split 线框）；## 4. 大类和页面（4.1–4.6 逐大类）；## 5. 组件（b-*）；## 6. 测试；## 7. 不做。
