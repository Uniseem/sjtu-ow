# 收尾批次：剩余工作一次做完

读者是接手的 GPT（本批前后端都由它做）。本文写于 2026-10-12（291 轮），依据当时的 [STATUS](../handoff/STATUS.md) 各表、290 的报告与验收边界，以及 [frontend-migration.md](frontend-migration.md) 第 4、6、7、9、11 节。

本文是这一批的执行规格。批次进行中，进度仍只写 STATUS；批次提交后本文不再更新，后续以 STATUS 和轮次目录为准。本文和 STATUS 冲突时以 STATUS 为准，顺手在本文加一句更正。

**299轮更正（2026-10-14）**：用户进一步取消非必要剩余验收，当前范围改按 [development本批范围](development.md#本批剩余验收范围299-用户决定)，只保留一次最后改动的操作检查，完整矩阵、双引擎全旅程、第二次真实旧库演练等追加项取消。本轮用户明确「不用执行，只要改文档和状态然后 push 即可」，不运行验证。下文保留291原规格，不再以其全量完成条件领取本批任务；省略项不标通过，实际状态见 STATUS，部署授权、磁盘与数据安全条件仍保留。

---

## 0. 用户决定与授权边界

2026-10-12 用户拍板，原话见 `handoff/rounds/291-gpt-handoff-plan/request.md`。

| 事项 | 决定 | 对本批的含义 |
|---|---|---|
| 分工 | 这一阶段 GPT 前后端都做 | 本批可改 `web/`、`server/`、`e2e/`、新栈 `deploy/` 文件、前后端验收脚本、`check.sh` 与 CI 两段、`frontend-migration.md` 与 12 号文档、STATUS 各段。OWNERSHIP 长期表不改；Claude 本批不在共享检出写东西 |
| 做法 | 一次把剩下的全部做完，**代码全部写完再测试** | 编码阶段（第 3 节）不跑编译、测试、对拍、浏览器；全部写完后，第 4 节在测试机集中跑。和 290 同一做法 |
| 正式站 cron | 授权改成冬令时不受影响的写法 | 第 2 节。**10-25 前必须完成**，和代码批次无关，开工先做 |
| 真实旧库演练 | 拷正式站备份到测试机，用完删除 | 第 4.10 节；正式站只读 |
| 干部试用站（检查点 B） | 不做 | 不部署 IP 试用站，不安排干部试用；割接条件见第 5 节 |
| 磁盘、异地备份 R2 | 未授权 | 不重测、不清理、不配置；收尾时一起问用户 |
| 部署、割接 | 未授权 | 第 6 节只准备材料、向用户提问 |

不变的规矩（AGENTS 常驻约束）：
- 旧站冻结、只读。
- `web/packages/api/src/gen/` 和 `docs/api-reference.md` 只由 `sjtuow apigen` 生成，不手改。
- 页面已经读的字段只能兼容添加；一个人做两边也一样，确实要改名就先让页面换过去，再删旧字段。
- 新依赖先问用户。Playwright 已在第 10 节第 3 件批准：用之前核对许可证（Apache-2.0），锁文件由测试机生成，补 `THIRD_PARTY_NOTICES.md`。
- 不提交 `data/`、`backups/`、`media/`、`.env`、真实身份或密钥。
- 提交身份沿用仓库本地的 Uniseem 配置；`Co-authored-by` 写实际运行的模型，不署 Claude。
- 并行子代理或多个检出，要用户另行授权。

---

## 1. 开工

1. `git status`：干净就 `git pull --rebase`；不干净就停下问用户。
2. 读这些：
   - STATUS 头部和各表；本文
   - OWNERSHIP
   - frontend-migration 第 4 节（不变量）、第 6、7、9 节
   - [development.md](development.md)、[REVIEW-GUIDE](../handoff/REVIEW-GUIDE.md)
   - `handoff/rounds/290-f6-f9-full-frontend/` 的 request、report、review
3. 轮次分两个：
   - cron 单独一个小轮 `NNN-ops-cron-winter`，先做先提交，不用等代码批次。
   - 其余全部是一个轮次 `NNN-final-batch`，一个提交。
   - 号码在开工时拉取后取最大号加一。
4. 批次的 request.md 引用本文和 291 request 里的用户原话，写明基线 SHA。
5. 不设行数门槛（290 时用户已免除）。report 里写实际改动的文件数和行数，供参考。

---

## 2. 正式站 cron 冬令时写法（开工先做，10-20 前完成）

背景：
- 正式站（169.58.217.180，时区 Europe/Berlin）现在跑的是旧 Django。
- `/etc/cron.d/sjtu-ow` 是按柏林夏令时换算写死的；2026-10-25 柏林切冬令时后，每条任务都会整体晚一小时。
- 新写法让每条每小时触发，由 `deploy/at-shanghai.sh` 判断北京时间到没到。
- 操作原文见 [legacy-guide](legacy-guide.md)「把正式站的 cron 换成新写法」；机器参数见 [operations](operations.md)「第二台」。

授权范围：只改 `/etc/cron.d/sjtu-ow`。不升级、不构建、不重启、不清磁盘、不动数据卷、不碰其他项目。

1. **只读探查并记录：**
   - `date`、`timedatectl`
   - `cat /etc/cron.d/sjtu-ow`
   - `ls -l /srv/sjtu-ow/deploy/at-shanghai.sh`
   - `git -C /srv/sjtu-ow log -1 --oneline`
   - 用 Compose `ps` 确认跑的是旧站的 `web`、`worker`

   脚本不存在，或者不是 218 起的版本，就停下问用户，不要自行往服务器放代码。
2. **备份：** `cp -p /etc/cron.d/sjtu-ow /root/sjtu-ow-backups/cron.d-sjtu-ow.bak-$(date +%Y%m%d%H%M)`。备份不要放在 `/etc/cron.d/` 里。
3. **写新文件：**
   - 五条照 `deploy/crontab.example`：03:00 `backup`、04:00 `cleanup_old_data`、04:15 `prerender`、04:20 `cleanup_static`、周日 04:30 `optimize_db`。`/etc/cron.d` 格式要在每条五个时间字段后加一列 `root`。
   - `DC=` 那行**用现有条目里实际在用的 Compose 命令**。正式站要带 `-p sjtu-ow`、两个 `-f`（`docker-compose.yml` 和 `docker-compose.vps.yml`）和 `--env-file`，路径都写绝对路径。example 里只有一个 `-f`，不要照抄。
   - `AT=sh /srv/sjtu-ow/deploy/at-shanghai.sh`。
   - 现有文件里如果有 example 没有的条目，保留并改成同样的写法，在报告里列出。
   - 权限 644，属主 root，文件末尾要有换行。
4. **验证：**
   - `sh /srv/sjtu-ow/deploy/at-shanghai.sh <当前北京小时> -- echo 到点了` 会输出；换一个小时就不输出。
   - 用 `AT_SHANGHAI_EPOCH` 各取 10-25 前、后一个北京 03:00 的秒数，确认两次都判定为到点。
   - 过一个整点后看 cron 日志（`journalctl -u cron` 或 `/var/log/syslog`）：五条都触发了，没有报错。
   - 第二天北京 03:00 之后，`$C exec -T web ls -lt /app/backups | head -3` 能看到当天的新备份；04:15 之后，预渲染时间已更新。
5. **回退：** 把备份文件 `cp` 回去。
6. **记录：**
   - 小轮的 report 写改前、改后的内容（不含密钥）和验证输出。
   - STATUS 运维表「正式站 cron」一行改成「✓ 轮次号」，`blocked_on` 去掉这一项。

---

## 3. 编码阶段：全部写完，不跑测试

本节每一项都只写，不编译、不跑。每项写的同时，把它对应的测试、对拍行、旅程步骤、变异点一起写好，留到第 4 节统一跑。

这个阶段允许的只读动作：读代码、读文档、读旧站模板、在测试机上查看已有日志。

### 3.1 读码复核 290 并修

为什么先做：290 一次新增或重写了 24831 行，其中 Go 非测试文件 120 个、+13436 行。它只做过同批子代理的有限复核。

做法：按 REVIEW-GUIDE 的口径逐个风险点读码。怀疑的地方当场写一条能让它变红的测试（Go 单测或真实 HTTP 步骤）；确认是 bug 就修。按风险从高到低：

| 优先 | 范围 | 文件（`server/internal/` 下，另注明的除外） | 看什么 |
|---|---|---|---|
| 1 | 后台权限与私有数据 | `backoffice/` 下的 roles、users、registrations、management、home、navigation | 每个接口都过能力门；三类非超管干部不能越权；联系方式、报名名单、`member_contact` 只给该看的人；403 不泄漏东西是否存在 |
| 2 | 业务密钥 | `settings/editor.go`、`settings/backup.go`、`platform/crypto/files.go`、`ops/offsite.go`、`platform/storage/s3.go` | 只加密存，只回「已设置」；不进日志、审计、错误正文和生成类型；S3 签名和流式加密在截断、边界处的行为 |
| 3 | 私有预览 | `notify/notice_preview.go`、`mailpreview/module.go`、`content/admin_preview.go`、`content/preview_reader.go` | 归属、过期、跨作者、CSP、缓存头 |
| 4 | 保存协议 | `accounts/personal_patch.go`、`accounts/profile_patch.go` | 版本号；409 带回 current；明确的 null/false；漏传的字段不动；同一幂等键重放 |
| 5 | 内容 | `content/` 下的 admin_articles、admin_site_drafts、admin_pages、revision_decode、admin_validation | 修订恢复、关闭的分类、定时发布、普通页草稿隔离、投稿者受限字段 |
| 6 | 活动与报名 | `tournaments/` 下的 registration_form、personal、admin_edit；`scrims/` 下的 signup_form、personal；`backoffice/registrations.go` | 报名规则照 05 号文档；并发版本；CSV 导出防公式注入（以 `=`、`+`、`-`、`@` 开头的单元格）；冻结名单 |
| 7 | 上传与字体 | `platform/media/admin_edit.go`、`fonts/` 全部（含 `offline_package.py`） | 文件类型、大小、路径穿越、分块归属；外网调用只出现在授权动作里 |
| 8 | 注销与旧信导入 | `accounts/service.go`、`notify/import.go` | 匿名化完整、会话全部撤销、导入不吞错误 |
| 9 | 前端 | `web/apps/admin`、`web/apps/site` | 前端的门只管体验，真门在 Go；`v-html` 只在白名单；没有假成功；离页保护 |

产出：
- 本批 review.md 写「对 290 的独立复核」，问题分「必须修」「建议修」。必须修的本批修掉；建议修的写进 STATUS 或 13 号文档。
- 结论另外追加到 `handoff/rounds/290-f6-f9-full-frontend/review.md` 末尾，标题为「NNN 轮独立复核结论」（handoff/README 的规定）。

### 3.2 验收工具

**a. 对拍矩阵**
- 现状：`e2e/parity/parity.py` 的 `PAGES` 是手写的 47 行「名字 × 身份 × 地址」，身份只有 visitor、member、captain、officer 四种。七种身份只在账号专项里有（`account_scenarios.py` 的 `ROLES`）。
- 要写：改成按「地址 × 适用身份」声明、自动展开。七种身份（访客、成员、队长、赛事管理员、内战管理员、内容编辑、超管）复用 `account_scenarios` 的种子；前台每个地址按第 6 节列出该比的身份。

**b. 后台行**
- 现状：清单里没有后台行。工具已经把 `web/apps/admin/dist` 拷进了 assets。
- 要写：第 7 节的全部后台地址，旧站 `/admin/…`（backoffice）和新后台 SPA 按同一地址比。
  - 等 SPA 渲染完成（`#main` 稳定、没有加载中状态）再取内容。
  - 身份覆盖四种：未登录跳登录；没有该标签能力的干部给 403；有能力的非超管干部；超管。
  - 设计允许的差异（换成 CodeMirror 编辑器、原图不公开等，见 `design-next.md` 第 7 节）写进白名单，每条注明出处。

**c. 其他行**
- 现状：没有这些行。
- 要写：
  - `/unsubscribe/<token>/`：有效、无效、过期三种，token 由种子生成
  - `/letters/<batch>/<id>/`：302 到私有预览
  - `/_styleguide/emails/` 两条
  - `/sitemap.xml`、`/robots.txt`、`/favicon.ico`、`/apple-touch-icon.png`：比状态码、类型和正文

**d. 错误页**
- 现状：旧站在开发设置下，404 是 Django 调试页，所以清单里没有错误页（见 `PAGES` 的注释）。
- 要写：
  - 旧站一侧用 `templates/errors/*.html` 渲染出的静态页作参照，或者用旧站 `render_error_pages` 生成的 `deploy/error_pages/`。
  - 新站的 403、404、429、500 真实触发。
  - 503 走 Caddy 维护页。

**e. 账号错误态**
- 现状：`e2e/parity/account_errors.py` 有 11 个场景：登录错误、注册三种、重新认证、改密三种、验证码错误、重置码错误、重置短密码。
- 要补：
  - 邮箱验证码过期；三次输错作废后再输
  - 重发冷却（显示 Retry-After）
  - 重置码过期
  - 登录、注册、找回、验证码重发各自的 429
  - 注册时邮箱已存在（照旧站的防枚举表现）
  - 换邮箱时新邮箱已被占用
- 限流场景两边都用真实请求把桶打满，不改业务限流参数。

**f. 旅程**
- 现状：`scripts/journey.mjs` 最后一次改在 260，三种模式跟不上现在的页面。
- 要写：三种模式迁到新栈真 Go 加本机捕获 SMTP。启动方式复用 `web/apps/site/real-accounts-journey.mjs` 和 290 `personal-journey.mjs` 的写法。
  - newbie：注册 → 读信里的验证码 → 验证 → 加游戏 ID 和联系方式 → 报内战 → 申请战队（经过发信页）→ 首页「我的安排」。
  - pages：每个地址 × 七种身份都打开一遍。
  - admin：
    - 再报 10 个人。
    - 分队页勾满 10 人、生成，用卡片按钮移到缓冲区再移回，保存。
    - 编队页把 3 个散人编进新队、起名、保存。
    - 写一篇文章，在对话框里选封面，发布。
- 出现控制台错误、未捕获异常、CSP 违规、激活不一致或 500，都退出 1。

**g. WebKit**
- 现状：只有用 CDP 驱动的 Chromium。
- 要写：加 Playwright（已批准），只用于 WebKit。pages 模式全部地址，加 newbie、admin 两条旅程，在 WebKit 上各跑一遍。

**h. 响应头**
- 现状：已有 `e2e/caddy/smoke.sh`。
- 要补：
  - CSP 三套（前台、后台、邮件和正文预览）、HSTS、`nosniff`、`Referrer-Policy`、`frame-ancestors`
  - 静态资源的缓存头
  - 非接口的写请求回 405
  - 请求体上限：上传 10 MB，其余 1 MB
  - `POST /unsubscribe/*` 进 Go
  - 502–504 出维护页

**i. 演练脚本**
- 现状：`deploy/rehearse.sh` 在给的路径不存在时会静默改用空库；也没有 `import-media` 这一步。
- 要写：
  - 给了路径却不存在，就报错退出。
  - 加 `import-media` 一步，媒体目录作为参数传入。
  - 能从旧站的备份包里解出数据库和媒体。
  - 保留 900 秒计时；输出里不打印真实数据。

**j. 一键跑完**
- 现状：没有。
- 要写：在批次目录写一个脚本，按第 4 节的顺序串起来。每一步的日志写单独的文件并记录退出码；某一步失败也继续往下跑，但最终退出非 0。

**k. 负向探针**
- 现状：账号专项已经有。
- 要写：矩阵、后台行、错误页、响应头各加一个探针，故意弄坏之后必须报「不同」或「失败」。

### 3.3 前台补齐（照旧模板）

**样张**
- 现状：`web/apps/site/src/pages/Styleguide.vue` 只放了 CAvatar、CEmpty、CField、CIcon、CRank、CRegStatus、CRoleIcon、CSeats、CStatus。
- 要写：
  - 补上 266、267 的其余组件：CPager、CPlay、CProfileGaps、CPagehead、PostCard、TeamTile、CTournamentCard、CScrimRow、CTeamLogo、CStartsAt、AuthLayout（含旁栏、面包屑、错误提示）、MeLayout。
  - 用和旧 `/_styleguide/` 同一份数据。
  - 加真实图片和默认图的样例。

**真实图片与默认图池**
- 现状：267 留下的待办「真实图片与默认图片池的页面投影」。
- 要写：文章卡、文章头图、战队标志、头像、赛事封面逐个核对。
  - 有图就走 `imageUrl`（A7）。
  - 没图就按 design-details 2.2–2.4、13.2.5 用默认封面池或默认头像池。
  - Go 投影里缺 `default_*_image_id` 的补上（只加字段）。

**错误页**
- 现状：代码在 `web/apps/site/src/error-page.ts`。STATUS 表里写「半（一行字）」，但 263 记的是 A12 ✓。
- 要写：逐字对照 `templates/errors/` 下的 403、404、429、500 和 `error.css`，不带脚本。表和代码对不上的地方，先核实再修。

**退订**
- 现状：
  - 页面是 `pages/Unsubscribe.vue`，75 行。
  - Go 已有 `GET` 和 `POST /api/announcements/unsubscribe/{token}`，以及一键退订 `POST /unsubscribe/{token}/`（`server/internal/notify/api.go:77-83`）。
  - Caddy 已经转发（`Caddyfile.new` 的 `@unsubscribe_post`）。
- 要写：照旧站 `core/views.py` 的 `announcements_unsubscribe` 和模板 `core/unsubscribe.html` 补齐页面。
  - 三种状态：有效、已退订、无效（404）。
  - 按钮提交和成功文案。
  - 一键 POST 没有页面。

**账号过期和限流态**
- 现状：287 起页面透传真实 API 错误；验证码重发按 Retry-After 冷却。其他限流场景还没有专门的页面表现。
- 要写：补齐 3.2 e 新场景在页面上的表现，文案以旧站为准。

**待核对的跳转**
- 现状：`/accounts/password/set/`、`/login/code/confirm/` 在表里写着「安全页 F5 待」，而安全页 290 已经做了。
- 要写：核对跳转目标和旧站一致，更新表。

**元信息（A11）**
- 现状：已有 `usePageMeta`。
- 要写：
  - `/me/`、`/accounts/`、`/letters/`、`/admin/` 加 `noindex`。
  - canonical、分享卡片（`fill-1200x630`）。
  - 图标和 `theme-color` 照旧站 `base.html`。

**个人记录跨页**
- 现状：`/me/teams/`、`/me/registrations/` 的跨页写动作没有完整验过。
- 要写：取消报名、退役等写动作做完整，回到列表后状态正确。

**投稿落点**
- 现状：成员打开 `/submit/` 会 302 到后台写文章页。
- 要写：投稿者（不是干部）能进写文章页，表单字段按身份减少。和后台内容组一起验。

### 3.4 后台补齐（frontend-migration 第 7 节、admin.md 第 4 节）

页面组件都在 `web/apps/admin/src/pages/` 下（content、activities、management、letters、mailpreview）。逐页对照旧 backoffice 模板和 admin.md 第 4 节的逐页说明，补齐缺的行为。

每页共同要求（第 7 节开头）：
- 没登录跳登录；没有该标签的能力给 403。
- 改值的表单自动保存（A9）。
- 危险操作走 `useConfirm()`。
- 动作产生的信走发信页（I6）。

各组重点：

**内容**
- 图片：多张上传、编辑、集合增删改。
- 选图对话框：48 张一页，可筛选。
- 分类：只有没文章的分类才能删。
- 文章：
  - 表单字段按身份增减；CodeMirror 编辑器；预览
  - 关联赛事；网址和定时发布
  - 自动存草稿；发布、撤下、删除；修订历史
- 网站页面：置顶、栏目简介、普通页、预览。

**活动**
- 赛事和内战列表：筛选、待审核件数、「更多」菜单按状态变化。
- 新建、编辑、复制、删除；动作（发布时可顺带通知）；取消。
- `/admin/announce/<种类>/<id>/`（支持 `?to=participants`）。

**编排与审核**
- 报名：列表筛选、批量通过、导出 CSV；详情页通过、驳回、撤销。
- 编队板：散人池、多队、满队拒收、低于下限标记、键盘移动、两阶段保存、`base_version`。
- 分队板：勾选上场、生成、拖拽 A/B 队和缓冲区、每动一次就存、复制文案、过期标记、`board_version`；分队文字页。

**成员**
- 用户：停用要写原因、角色勾选、个人功能规则。
- 角色：每组人数、能做什么、功能限制。
- 战队：编辑、指定队长、解散。
- 成员分组：搜人（250 毫秒防抖）、排序、头衔、移出。

**巡查与数据**
- 内容巡查：处置、发信要作者修改；AI 巡查按 D5 只读。
- 头像：三种状态。
- 评论：隐藏和恢复、置顶和取消。
- 活动数据：按周期查看、导出 CSV。
- 操作记录：可筛选，50 条一页。

**设置与手册**
- 全站设置：分组、选图、密钥不回显、测试邮件、试异地备份。
- 字体库和排版（D4）。
- 邮件样张。
- 后台首页：问候、快捷按钮、待办卡、我的文章、上线清单。
- 手册按角色显示对应部分。

**旧地址**
- `/admin/settings/prerender/` 现在只是 SPA 里的客户端跳转（`web/apps/admin/src/router.ts:14`）。第 10 节第 5 件要求 301 到上一级，要在 Caddy（或 Go）做真正的 301。

### 3.5 割接材料

**`docs/cutover.md`**
- 把第 5 节的教训改进正文：
  - 割接前先给旧镜像打 `legacy` 标签。
  - 新栈换一个项目名（比如 `sjtu-ow-next`），不和旧站共用镜像名。
  - 所有命令都带 `--env-file`。
- 第 4 节的回滚命令改成能照着做的。
- 删掉试用站相关的内容。
- 加磁盘余量预检：新镜像构建需要空间，正式站上次测量只剩 19%。

**定时任务**
- 新栈的定时任务在 worker 里按 `Asia/Shanghai` 计算（12 号文档「定时器」），不再需要宿主机 cron。
- 割接时要停用宿主机的 `/etc/cron.d/sjtu-ow`，否则它会对新栈容器跑 `manage.py`；回滚时换回来。
- 这两步写进割接和回滚步骤。

**Compose**
- `deploy/docker-compose.new.yml` 等文件和上面定的项目名、镜像名保持一致。

**正式站专用文件**
- 正式站有两个不进仓库的文件：`docker-compose.vps.yml`、`Caddyfile.vps`（反代信任 `100.96.0.0/12`）。
- 新栈要有对应的做法，写进 cutover。

---

## 4. 测试阶段：写完后集中跑

规矩：
- 全部在测试机上、用助手的后台任务跑，输出写文件（development.md）。
- 测试机同一时间只跑一组；对拍一次大约 6 分钟。
- 按下表顺序跑，可以用 3.2 j 的脚本一次串起来。

| 步 | 内容 | 入口 | 通过标准 |
|---|---|---|---|
| 4.1 | 整组 | `bash scripts/remote-check.sh` | 退出 0：Go 五项、apigen 一致、严格类型、Web 测试、构建与预算 |
| 4.2 | 变异 | 仿 `handoff/rounds/290-f6-f9-full-frontend/mutate.py` | 3.1 的新测试、3.2 的新守卫，逐个改坏都变红（断言失败，不是编译失败），恢复后变绿 |
| 4.3 | 浏览器底座 | `web/apps/site/browser-check.mjs`、`web/apps/admin/browser-check.mjs`、`web/apps/site/comments-browser-check.mjs` | 全过，CSP 零违规 |
| 4.4 | 真实接口 | `real-accounts-journey.mjs`、`real-comments-journey.mjs`，290 的 `api-journey.py`、`personal-journey.mjs`、`run_real_personal.py`，以及 3.1 新增的 | 全过。290 日志后半那段旧驱动的错误断言（期待编辑不可用）要改掉 |
| 4.5 | Caddy 与响应头 | `e2e/caddy/smoke.sh`（3.2 h 扩充后） | 输出 `CADDY-SMOKE-OK` |
| 4.6 | 对拍全矩阵 | `e2e/parity/run.sh --wide --strict`（前台、后台、其他行）；`--accounts --wide --strict`；账号错误态 | 每行通过，或者差异逐条列出等用户认可；阈值 0.5% 不改 |
| 4.7 | 三条旅程 | `scripts/journey.mjs newbie`、`admin`、`pages` | 各自退出 0 |
| 4.8 | WebKit | 用 Playwright WebKit 跑 pages 和两条旅程 | 退出 0 |
| 4.9 | 体积 | `budget.mjs`（前台、后台） | 不超预算 |
| 4.10 | 真实旧库演练两次 | 见下 | 两次都导入零报错、对账一致；第二次总耗时不超过 900 秒 |
| 4.11 | 修复循环 | — | 任何修复后重跑受影响的项；最后在最终源码上重跑 4.1 和受影响的专项 |

### 4.10 真实旧库演练

用户授权的是：拷正式站备份到测试机，用完删除。

1. **正式站只读。** 列出现有备份（`$C exec -T web ls -lt /app/backups`），取最新一份每日备份，记下大小和 sha256。不新建备份，不在正式站上写临时文件。
2. **直接流到测试机，本机不落盘。** 例如：

   ```bash
   ssh root@169.58.217.180 'cd /srv/sjtu-ow && docker compose -p sjtu-ow -f deploy/docker-compose.yml -f deploy/docker-compose.vps.yml --env-file .env exec -T web cat /app/backups/<文件>' \
     | ssh sjtu-ow-test 'umask 077; mkdir -p /srv/sjtu-ow-rehearsal && cat > /srv/sjtu-ow-rehearsal/<文件>'
   ```

   Compose 命令以 operations「第二台」写的为准，命令整段放在单引号里在正式站上展开。

   到测试机后再算一次 sha256，和第 1 步对上。
3. **跑演练。** 在 `/srv/sjtu-ow-rehearsal/`（权限 700）里解包，用 3.2 i 改过的 `deploy/rehearse.sh <旧库> <媒体目录>` 跑完：快照 → migrate → import → import-media → reconcile → parity，记下各步耗时。
4. **对账。** 逐表计数对上：用户、战队、文章、评论、赛事、内战、报名、图片和集合、普通页（`content_standardpage`，见 BE-0）、站点设置、字体。任何导入错误都要报出来，不能吞掉。
5. **打开页面看。** 用 `sjtuow session` 给几个真实身份发会话（不用密码），在测试机本地打开主要的前台和后台页面，查 500、坏图、空块。
6. **两次的区别。**
   - 第一次发现的导入问题，回到编码阶段修，并补一条用种子数据就能复现的测试。
   - 第二次重新拷一份**最新**备份，整条重跑并计时。
7. **每次结束都删除。** 要删的有：
   - `/srv/sjtu-ow-rehearsal/`
   - `rehearse.sh` 的临时目录
   - 用真实库跑出的对拍输出（如果用过 `/tmp/sjtu-ow-parity`）

   删完用 `ls` 证明已删，报告里写删除时间。
8. **证据纪律。** 报告和轮次目录只写计数、哈希前缀、耗时、错误类型；不放真实昵称、邮箱、联系方式和截图。

### 失败怎么处理

- 首次失败的日志保留；修好后再跑的单独记录。
- 不放宽阈值，不改业务限流。
- 不把用桩数据跑的浏览器结果当成 Go 持久化的证据（290 的边界）。

---

## 5. 做完的标准

下面全部满足，这一批才算完成：

1. STATUS 前台页面表和后台表，每一行的「页面、部件、接口、对拍、旅程」都是 ✓ 并带日志名；或者差异已经单列一张表，等用户认可。
2. 底座表 A1–A14、B1–B8 每一项都有证据；B8（磁盘）标「等用户」。
3. 新人第一晚、干部那一晚、pages 三条旅程，在 Chromium 和 WebKit 上都通过。
4. 响应头、体积通过。
5. 290 的独立复核结论已经追加，必须修的已经修掉。
6. 两次真实旧库演练通过，第二次不超过 900 秒，真实数据已删除。
7. cron 新写法已在正式站生效（第 2 节）。
8. `cutover.md` 能照着做。
9. 最终提交上整组全绿；推 main 后，该 SHA 的 CI 成功。

有不满足的，照实写「部分完成」，没做完的项留在 STATUS 的当前表里。

---

## 6. 收尾与交给用户

1. 写好三份记录和 STATUS：
   - report：真实命令、日志编号、退出码，失败的也留着。
   - review：自查，加上 3.1 的独立复核。
   - STATUS：各表、头部、运维表；最近轮次只留 3 条。
2. 一个中文提交：标题 `NNN: …`，正文详细，`Co-authored-by` 写实际模型。`git pull --rebase` 后推 main，按精确 SHA 等 CI。
3. 向用户提交割接申请，一次问清：
   - 割接时间
   - 正式站磁盘重测和清理（新镜像需要空间）
   - 异地备份 R2
   - 割接后的外部验收：多种邮箱收信、校园网和三大运营商访问、4 小时内恢复演练、外部监控、成员公告

   **没拿到授权，不部署、不割接。**
4. 获得授权后照 `cutover.md` 执行，另起一轮。

---

## 7. 本批不做

- 不改旧站；不改像素阈值和业务限流参数。
- 除第 2 节的 cron 外，不部署任何服务器；不碰正式站的数据、磁盘和其他项目。
- 不手改生成物；不改 OWNERSHIP 的长期表和 AGENTS。
- 不移植 AI 巡查（按 D5 放到割接后）；不做设计变化（要先问用户）。
- 不调用 Google、外部 S3 等真实外部服务，一律用本机假服务。

---

## 附：STATUS 待办与本文的对照

| STATUS 里的待办 | 本文位置 |
|---|---|
| 账号错误、过期、限流态 | 3.2 e、3.3、4.6 |
| F2 样张、真实图片 | 3.3 |
| F4 全身份、真实图片、内容旅程、投稿落点 | 3.2 a、3.3、3.4、4.6、4.7 |
| 退订、单封预览截图、个人记录跨页旅程 | 3.2 c、3.3、4.6、4.7 |
| 战队申请、管理的完整浏览器旅程 | 3.2 f、4.7 |
| 错误页、sitemap 等、邮件样张行 | 3.2 c、3.2 d、3.3、4.6 |
| 后台逐页四组合与旅程 | 3.2 b、3.2 f、3.4、4.6、4.7 |
| F10 全站矩阵、WebKit、响应头、体积 | 3.2 a、3.2 g、3.2 h、4.5–4.9 |
| 真实旧库与迁移演练 | 3.2 i、4.10 |
| 290 只做了有限复核 | 3.1 |
| 正式站 cron | 第 2 节 |
| 磁盘、R2、割接时间、外部验收 | 第 6 节（问用户） |
| 试用站 | 不做（frontend-migration 第 10 节第 6 件） |
