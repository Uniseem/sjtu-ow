# 06 · core 基础设施与运维机制（Go 复刻清单）

来源：基础设施调研代理。基线 `ec44ae4`。

## 1. Worker 与任务队列

**选型与存储**：django-tasks + django_tasks_db.DatabaseBackend，任务即 SQLite 表，队列名只有 default（settings/base.py:141-146）。SQLite 连接 transaction_mode=IMMEDIATE、timeout=5、PRAGMA journal_mode=WAL; synchronous=NORMAL（base.py:107-122）——写事务串行化是限流、字体排队等机制的前提。默认 cache 是数据库表 django_cache（base.py:124-128），worker 心跳靠它跨进程可见；另有进程内 renditions LocMemCache（600s / 2000 条，base.py:130-138）。

**任务清单**（core/tasks.py）：deliver_queued_email（:66-77）、process_font_face（:84-92）、delete_retired_font_slices（:95-100）、prerender_page / prerender_all / remove_prerendered（:103-131，均先判 prerender.is_enabled()）、send_broadcast（:134-143）。

**入队方式**：统一 transaction.on_commit——邮件在 QueuedEmailBackend.send_messages，处于原子块就 on_commit(enqueue)，否则立即入队（core/mail.py:283-299）；字体处理 queue_face 同样 on_commit（core/fonts/services.py:171-180）；被替换的字体分片延迟 1 天再删（core/fonts/services.py:267-280）。

**重试策略**：
- 邮件：失败按 MAIL_RETRY_DELAYS = (60, 300, 1800) 秒重新入队，初发 + 3 次重试（core/tasks.py:16,66-77）。
- 字体：单 worker 一次只处理一个字体；占不上就 requeue，30 秒后再排，最多 120 次（约 1 小时）。
- 去重：enqueue_once（core/tasks.py:31-63）——同 task_path + 同 args 已有 READY 等待时不再入队；earlier_counts=True 允许"已有的更早一次也算"。
- 提醒宽限：REMINDER_GRACE = 10 分钟——保存时安排的提醒不会早于保存后 10 分钟发出（core/tasks.py:19-28）。

**心跳**：worker 守护线程每 30 秒写 cache key sjtu_ow:worker_heartbeat（TTL 240s）（core/worker.py:46-95）。同一 beat 顺带跑：定时发布 publish_due_pages、AI 巡查触发 enqueue_if_due，各 job 独立 try/except + close_old_connections（core/worker.py:54-73）。

**被杀后 RUNNING 复位**：run_worker 启动时先 reset_orphaned_running_tasks()——所有 RUNNING 置回 READY 从头重跑（广播可能重发，"比永远发不出强"）（core/worker.py:24-43）。**设计前提：永远只有一个 worker**。

**巡查限时**：AI 巡查由心跳触发，cache 门闩保证每 PATROL_MINUTES=30 分钟最多一轮（cache.add 原子占位）；单轮最多占 worker 60 秒，超时以 FOLLOW_UP_PRIORITY=-10 排续轮（moderation/patrol.py:32-38,204-212）。

**Go 复刻要点**：DB 表任务队列 + on_commit 语义、单 worker 假设、启动复位、30s 心跳写共享存储、巡查门闩与限时、邮件三级重试、字体排队、enqueue_once、提醒宽限。

## 2. 邮件管线

**队列架构**：EMAIL_BACKEND = core.mail.QueuedEmailBackend（入队），EMAIL_DELIVERY_BACKEND = SiteSettingsEmailBackend（worker 实发）（base.py:212-213）。SMTP 配置全部存数据库 SiteSettings，不读环境变量；密码 Fernet 加密。

**LetterMessage 与内嵌图**：LetterMessage(EmailMultiAlternatives) 重写 message()——HTML 部件变 multipart/related，HTML 中 cid:ow-mark / cid:ow-horizon 引用的 PNG 直接附进信体（core/mail.py:27-49）。图由 Pillow 绘制（红底白 mark + 两道山脊，1200×100 超采样 4 倍再 LANCZOS 缩小，与站点 horizon 同 seed 2026/1896），manage.py render_email_art 写 static/img/email/，测试比对提交文件。

**超时与重试**：SMTP_TIMEOUT_SECONDS = 20（服务器收了连接不说话不能卡死单线程 worker）（core/mail.py:24,206）；重试 60/300/1800 秒。发送前统一补：text+HTML 双体（纯文本信套同一信纸）、主题前缀（默认 [SJTU-OW]）、SiteSettings 发件人（core/mail.py:71-125,211-230）。

**退订**：只有"可关的活动通知"带退订——信脚退订链接 + 邮件头 List-Unsubscribe / List-Unsubscribe-Post: One-Click（RFC 8058）（core/letters.py:126-133）；每人链接独立（签名 token 含 user pk，core/services.py:139-145）；群发逐人发、各自退订链接、关掉通知的人跳过（core/services.py:352-373）。

**待发信手动确认流**（设计 10.5，204 起）：登录用户的 POST 被 HeldLettersMiddleware 包进 outbox.asking(actor) 批次（core/middleware.py:162-178）；操作写出的信经 outbox.hold 整封冻结进 HeldLetter（batch UUID、letter JSON、收件人快照；同批次同信合并收件人）（core/outbox.py:76-101）；动作重定向后先跳「发信」确认页逐封勾选，decide() 用条件 UPDATE 一次性 claim（WAITING→SENT/SKIPPED）防双击重发（core/outbox.py:147-169）。非 POST 上下文（worker/命令/测试）直接发。等待期 7 天，过期不再出现；30 天后清理（cleanup_old_data.py:95-102）。

**验证码邮件**：邮箱验证码 15 分钟 / 3 次尝试，密码重置 3 分钟 / 3 次（base.py:244-250）；验证码在 Letter 里以 code 字段大号显示。开发无 SMTP 时验证码打印到 worker 终端。

**其余细节**：一人一封、按昵称称呼（people() 去重、.invalid 邮箱跳过=已注销账号）（core/letters.py:139-170）；纯文本外来邮件（Wagtail 通知）套同一信纸且只把本站 URL 变链接（防钓鱼，core/letters.py:199-221）；第二封起信头写"之前已发过 N 次"；EMAIL_ALLOWLIST 测试环境白名单过滤；SMTP 测试按钮同步直发不走队列；管理员通知收件人按角色取组+超管（emails_for_groups）；/_styleguide/emails/ 用假数据渲染全部约 37 种信。

**Go 复刻要点**：SMTP 配置存库 + Fernet、20s 超时、60/300/1800 重试、双体与统一信纸、cid 内嵌 PNG、RFC 8058 退订头 + 每人独立链接、待发信批次表（冻结快照 + 条件更新 claim + 7 天窗口 + 30 天清理）、验证码 15min/3 次。

## 3. 预渲染之外的静态资产生成

**字体切片**（core/fonts/）：
- 校验：≤30MB、可解析、OS/2 fsType 禁嵌入位拒绝、usWeightClass 归一 100-900、fsSelection/macStyle 判斜体。
- 切分：基础拉丁/标点 600 字/片；GB2312 一级字（首字节 0xB0-0xD7）200 字/片；其余 CJK 600/片；CSS unicode-range 连续段折叠（core/fonts/slicing.py）。
- 子集化：fontTools subset 输出 WOFF2，hinting=False（省 12%）、drop FFTM、notdef_outline=True；**TTFont(..., recalcTimestamp=False) 保证字节级可复现**——分片文件名含 sha256 前 8 位（core/fonts/processing.py:106-149）。
- 业务：css_name 自增分配 sjtu-font-<n>；一次只处理一个字体（PROCESSING 超 30 分钟视为死掉）；进度写库 1-99%；替换下的分片延迟 1 天删；Google Fonts 来源直接下官方切片不再切；最多启用 6 个变体。
- 产物：media/fonts/<family_id>/ 下 woff2 分片 + media/fonts/css/fonts.<hash>.css。

**默认封面**（core/covers.py）：「默认封面」集合的图池，按 (对象 pk + 类型偏移) % 池大小 固定取图（:60-71）；空池回落占位图。

**占位 SVG**（core/placeholders.py）：9 种风格 × 4 配色 = 36 张 cover，交错排列使相邻 id 不同风格；固定随机种子，同图永远同内容；pick() 同 covers 公式。另有 6 个栏目白天场景、5 张头像底图、页脚 ridge、两条 horizon 遮罩。render_placeholders 写 static/img/placeholders/ 并删除旧文件，测试重绘比对。内含 CSS keyframes 动画 + prefers-reduced-motion 降级。

**图标**（core/icons.py）：按 favicon.svg 的数值用 Pillow 8 倍超采样画红方块白折线，产出 favicon.ico（16/32/48）+ apple-touch-icon 180 + icon-192/512；测试比对。

**校徽拆层**（core/emblem.py）：解析 static/img/sjtu-emblem.svg，按 </defs> 后最长的 <path>（齿轮环）拆成 body/gear 两个独立 SVG 供首屏 CSS mask 分别上色、齿轮慢转；测试重拆比对。

**Go 复刻要点**：字体管线（fsType 校验、GB2312 分片、WOFF2 可复现输出、内容哈希命名、单字体串行、旧分片 1 天缓删）；占位图/图标/邮件图/校徽层**要么移植绘制算法，要么把已生成文件当静态资产直接搬运**——重点是"同对象固定取图"公式和"生成物与代码一致性测试"这两个约束。

## 4. 备份恢复

**backup 命令**（每天 03:00 cron）：
- 数据库快照用 SQLite 在线备份 API（sqlite3.connect(...).backup()），绝不直接拷文件（WAL 会撕裂）；实际路径以 core/dbfile.database_path() 为准。
- 归档 backups/sjtu-ow-YYYYMMDD-HHMMSS.tar.gz（db.sqlite3 + media/；static 与 prerendered 不备，可重建）。
- 本地保留 BACKUP_KEEP_DAYS=14 天。
- 异地上传（core/offsite.py）：站点设置 S3/R2；先 Fernet 加密（key = sha256(BACKUP_ENCRYPTION_KEY)）再上传 .enc；加密密钥只在环境变量（放数据库等于密钥在被它保护的备份里）。上传失败整条命令失败；成功后按前缀分页 list + 正则只删自己的 .tar.gz.enc（1000 个一批），清理失败仅警告。
- 状态文件 backups/last-backup.json（finished_at/archive/size/offsite: off|skipped|uploaded|failed/error）。

**restore 命令**：--list-s3 列对象；--from-s3 KEY 下载解密；默认 dry-run，--yes 才执行。流程：先校验 FIELD_ENCRYPTION_KEY 能解开备份里的三个加密列 → 先恢复 media（可失败重来）再换数据库 → 删旧 WAL → copy2 换库 → **empty_folder 只清空 prerendered 不删目录**（数据卷挂载点不能删）→ 删 PrerenderedPage 记录 → 代码比库新时警告。停/启服务是运维手工做。

**备份待办提醒**（core/admin_todo.py:156-184）：BACKUP_STALE=36 小时无新归档、或 offsite=failed，超管后台首页出待办。

**Go 复刻要点**：在线备份（Go 侧可用 VACUUM INTO）、tar.gz(db+media)、14 天双端保留、Fernet(sha256(env key)) 加密 + S3 上传、恢复前密钥试解密、media 先行 + WAL 删除 + 挂载卷只清空、状态 json + 36h 告警。

## 5. 健康检查与中间件

**/healthz**（core/health.py + core/views.py:40-65），4 项检查全部影响状态码（200/503）：
- database：写探测行后回滚；SQLite busy 视为健康；只读库报 error 而非 500。
- disk：数据库卷剩余 ≤ 20% 判失败。
- worker_heartbeat：心跳缺失/超 120 秒判失败。
- task_backlog：READY 且入队超 600 秒（且 run_after 已到）判失败。
- 对外只给总状态和各项 ok 布尔；detail（错误文本、百分比）只给超管。

**中间件**（core/middleware.py，注册顺序见 base.py:59-77）：
- RequestIDMiddleware：每请求服务端生成 12 位随机 X-Request-ID，不信任客户端提供的。
- WagtailAdminCSPMiddleware：/wagtail/* 非超管重定向到 /admin/；/admin/ 与 /wagtail/ 套后台 CSP（unsafe-inline/eval）。
- LoggedInHintCookieMiddleware：ow_logged_in（会话期）+ ow_flash（一次性）两个非 HttpOnly 提示 cookie。
- PrerenderMissMiddleware：匿名 GET 命中可预渲染路径但文件缺失时排队生成。
- HeldLettersMiddleware：见第 2 节。
- AutosaveReplayMiddleware：按 X-Autosave-Key（16-64 位字母数字）缓存"该 key 已创建的对象地址"24 小时，网络重试不会建第二个新对象，返回 retry:true + location（:181-247）。

**限流**（core/ratelimit.py）：over_limit(key, limit, window=60)——整分钟窗口（int(time//60) 为桶号），cache key sjtu_ow:rl:{key}:{bucket}，TTL = 2×窗口；db cache 无原子 incr，靠 IMMEDIATE 事务内 add+incr 保并发正确。访客 IP 取 Caddy 注入的 X-Real-IP（:11-19）。

**自动保存**（core/autosave.py）：wants() = POST + X-Autosave: 1（:32-33）。规则：表单整体合法 → 全存；否则只存各自合法的变更字段、出错字段保存储值；跨字段规则（表单声明 autosave_together 组）任一成员出错整组跳过；表单级错误无注册组时本次全不存（:71-105）；落库时从库里取新副本写干净字段，IntegrityError 回滚（:108-152）；新对象首存 new_from_valid_fields 允许必填为空建草稿（:155-165）。日志 30 分钟合并（LOG_MERGE，:29,168-189）。应答 JSON 含 saved/errors/location/replace/values/saved_at（:57-68）。

## 6. 设置与环境变量

**环境变量全表**（base.py / prod.py / .env.example）：

| 变量 | 默认 | 出处 |
|---|---|---|
| DJANGO_SECRET_KEY | dev 值；prod 必填 | base.py:9 / prod.py:8 |
| DJANGO_ALLOWED_HOSTS | localhost,127.0.0.1,testserver；prod 必填 | base.py:15 |
| SITE_URL | http://localhost:8000；prod 必填 | base.py:17 |
| DJANGO_CSRF_TRUSTED_ORIGINS | 同上 | base.py:206 |
| FIELD_ENCRYPTION_KEY | dev 值；prod 必填 | base.py:353 |
| DATABASE_PATH | <repo>/data/db.sqlite3 | base.py:105 |
| STATIC_ROOT / MEDIA_ROOT | staticfiles/ / media/ | base.py:183,187 |
| DEFAULT_FROM_EMAIL | noreply@localhost | base.py:214 |
| EMAIL_ALLOWLIST | 空 | base.py:357 |
| PRERENDER_ENABLED | False（prod 默认 True） | base.py:339 |
| PRERENDER_ROOT | prerendered/ | base.py:340 |
| BACKUP_ROOT | backups/ | base.py:343 |
| BACKUP_ENCRYPTION_KEY | 空（不设则不上传异地） | base.py:347 |
| BACKUP_KEEP_DAYS | 14 | base.py:348 |
| STATIC_KEEP_DAYS | 30 | base.py:350 |
| SENTRY_DSN | 空（预留未用，217 建议删或真接） | base.py:356 |
| TEST_ENVIRONMENT | False（1=横幅+robots 全禁） | base.py:360 |
| GUNICORN_WORKERS | 3 | entrypoint-web.sh |
| DJANGO_SECURE_SSL_REDIRECT | prod True | prod.py:93 |
| DISK_MIN_FREE_RATIO | 0.20（代码默认） | base.py:362 |

代码内常量：HEALTH_PROBE_BUSY_TIMEOUT_MS=200、上传图 ≤5MB、缩略图强制 WebP q80（base.py:324-329）、allauth 限流表（base.py:261-271）、CSP 策略（base.py:275-290，与 Caddyfile 逐字一致有测试）。

**存数据库的全站设置**（SiteSettings 单例）：SMTP 组、站点信息组（简介/分享图/首屏图/成立日期/QQ 群）、5 栏目横幅、社区参数组（战队上限 10/队长上限 3/游戏 ID 上限 5/内战提醒 2h/赛事提醒 24h）、AI 审核组（模型默认 deepseek-v4.1-flash、每日 2000、超时 30s、最多输出 600）、异地备份组、排版组。**申请自动关闭不在设置里而是常量**：STALE_APPLICATION_DAYS=14 天、REMIND_CAPTAIN_DAYS=7 天（teams/services.py:361-364，每晚 cleanup 触发）。

## 7. 部署

**Dockerfile**：python:3.13-slim + libjpeg/zlib/webp；uv 装依赖；Tailwind CLI（112MB）独立层用 deploy/fetch_tailwind_cli.py 预下载（版本 2.9.0，sha256 白名单校验、5 次退避重试）；构建期 tailwind build；**非 root：app uid 10001，五个数据卷目录在镜像内建好并 chown**（Dockerfile:45-48）。

**docker-compose**：三服务 web（gunicorn 8000，healthcheck deploy/healthcheck.py 30s/5s/3 次/60s 宽限，探测带 Host + X-Forwarded-Proto）、worker（run_worker，static 卷只读挂载）、proxy（caddy:2.10-alpine）。卷：data/media/static/prerendered/backups/caddy。日志 json-file 10MB×5。

**entrypoint**：web = mkdir 卷目录 → createcachetable → collectstatic --noinput（不带 --clear，保留旧哈希文件）→ gunicorn；worker = mkdir → run_worker。

**Caddyfile**：encode zstd gzip（2.10 的 precompressed 对无 range 请求回 206，故不用）；502/503/504 落 maintenance.html（no-store）；路由优先级：/static/* 带 12 位 hash → immutable 1 年，否则 300s must-revalidate；/media/fonts/ 只有 fonts.css.[hash].css 和分片 woff2 可访问，其余（上传的原始字体）一律 404；/media/images/* immutable 1 年，其他 media 86400s；admin/wagtail/accounts/me/_fragments/healthz、非 GET/HEAD、带 query 一律直转 Django；否则尝试 /srv/prerendered/{path}/index.html（命中则 max-age=0 must-revalidate + page_security 头组）；header_up X-Real-IP {client_ip}。

**crontab.example**（宿主机，CRON_TZ=Asia/Shanghai；正式站在 Berlin 时区机器上按夏令时减 6 小时写——**217-09-9：2026-10-25 夏令时结束会整体晚一小时，待修**）：
- 0 3 * * * backup
- 0 4 * * * cleanup_old_data（删完成任务 30 天、已处理审核记录 180 天、做完的信 30 天、过期会话、空草稿 7 天、关闭 14 天没人处理的申请并通知、7 天提醒队长）
- 15 4 * * * prerender 全量重建
- 20 4 * * * cleanup_static（按 staticfiles.json 清旧文件，读不到清单什么都不删）
- 30 4 * * 0 optimize_db（PRAGMA optimize + wal_checkpoint(TRUNCATE)）

**README 生产/测试启动要点**：测试环境 = 同机另一套 compose 项目 -p sjtu-ow-test + TEST_ENVIRONMENT=1 + EMAIL_ALLOWLIST；先 migrate 再 up；createsuperuser 邮箱直接算已验证；三把密钥 openssl 随机生成并另行备份；升级到 216 需先把旧数据卷 chown 给 app 用户；升级保留旧静态文件一个月。

## 8. 其他横切机制

- **converters**（core/converters.py）：URL 转换器 <id:…> 限 [0-9]{1,18}（防 64 位溢出 500）；as_id() 给表单/查询串同规则解析，非法返回 None。
- **crypto**（core/crypto.py）：Fernet(sha256(FIELD_ENCRYPTION_KEY)) 加解密；looks_like_fernet（gAAAAA 前缀）区分密文与遗留明文。
- **agenda**（core/agenda.py）：首页「我的安排」最多 4 条；内战开始后仍留 6 小时（SCRIM_GRACE）；数据源 = 内战报名 + 报名队伍成员 + 散人报名；有时间的按时间排、无时间的排后。
- **calendar_feed**（core/calendar_feed.py）：ICS 地址 = Signer(salt="sjtu-ow.calendar").sign_object([pk, calendar_version])；「换一个订阅地址」= calendar_version+1，旧地址立刻失效；RFC 5545：75 字节折行不切字符、转义、DTSTAMP UTC、内战 3 小时/赛事 4 小时时长。无需登录。
- **activity**（core/activity.py）：活动数据——本学年/上学年/近 30 天/自定义（限 2000-2100 年）；只统计已发布+已结束；CSV 导出带 BOM。
- **admin_todo** 待办类型全集：自己的待发信；报名待审核、等待编队人数、开赛超 3 天未标结束；报名截止未分队的内战；超管专属——预渲染失败页数、worker 心跳停了、无队长战队、AI 审核卡住、备份问题（>36 小时/上传失败）、最近 7 天重试后仍失败的邮件数。
- **admin_log**：19 种自定义 action 写 Wagtail log；record() 失败只警告不影响业务操作。

**总体结论**：这套基础设施的核心假设是「单 SQLite 库 + 单 worker + Caddy 前置 + cron 宿主机」，Go 重构最需要逐条对齐的是：on_commit 入队语义、RUNNING 复位、30s 心跳/120s 判死/600s 积压三组阈值、邮件 20s 超时 + 60/300/1800 重试 + RFC8058 退订、待发信批次快照与一次性 claim、SQLite 在线备份 + Fernet 双密钥体系与恢复顺序、IMMEDIATE 事务下的整分钟限流、以及一批"生成物可复现且有测试锁定"的静态资产管线。
