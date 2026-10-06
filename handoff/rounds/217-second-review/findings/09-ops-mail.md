# 217 复核 09：运维、邮件、信

范围：`backup` / `restore` / `core/offsite.py`、`cleanup_old_data`（含 216 的空草稿清理）、`cleanup_static`、`optimize_db`、`core/worker.py` 和 `run_worker`、`core/health.py`、`core/mail.py`、`core/letters.py` 和 `templates/email`、发信（`core/outbox.py`、`HeldLettersMiddleware`、`core/held_views.py`、`backoffice/views/letters.py`）、群发（`core/services.py`）、退订、`deploy/crontab.example`。

复现脚本：`findings/09-repro.py`（每条测试断言的是「缺陷存在时的样子」，passed = 已复现）。测试机上跑了一次：`bash scripts/remote-check.sh run uv run pytest -q -p no:cacheprovider -s handoff/rounds/217-second-review/findings/09-repro.py`，结果 `1 failed, 4 passed in 1.19s`。09-2 到 09-5 通过，也就是已复现。09-1 只有最后一条断言没过（「半截归档读不出来」），前面的断言（待办不再提醒、状态文件还是旧的）都过了，所以掩盖失败这一点已复现，归档的样子要更正，见 09-1。

## 发现

### 09-1 备份半路失败时留下一个写到一半的归档，后台待办反而不再提醒（中）

- **位置**：`core/management/commands/backup.py:109-117`（直接写到正式文件名，失败不清理），`core/admin_todo.py:156-184`（`backup_problems` 只看最新归档的修改时间和 `last-backup.json` 里的 `offsite`）
- **问题**：`tarfile.open(archive, "w:gz")` 直接写到 `sjtu-ow-<时间>.tar.gz`。打包时出任何异常（`media` 里的文件在遍历时被删掉、磁盘满、读不了的文件），都会留下一个**不完整的归档**，文件名和正常备份一样。测试机上这份归档能正常打开（出异常时 `TarFile.__exit__` 把 gzip 正常关掉了），但里面只有数据库，media 不全；拿它恢复时，`restore` 会先把 media 清空，再拷回不全的那一份。最后这点是推测，没有实际跑恢复。同时，`write_status` 也不会执行，`last-backup.json` 还停在上一次成功的那份。待办拿最新归档的 mtime 判断「36 小时没有新备份」，这个不完整的归档每晚都是新的，所以**备份每晚都在失败，待办却一直不报**；异地上传也不会执行。设计 16.7 v6.45 加备份状态，就是为了不再「等要恢复时才发现」
- **失败场景**：03:00 打包的时候，worker 正好在删旧的字体切片（`delete_retired_font_slices`），或者有人换了头像，Wagtail 删掉旧图 → 抛 `FileNotFoundError`；或者磁盘写满。这种情况一直持续的话（读不了的文件、磁盘满），后台始终不提醒，要恢复时才发现最近的归档根本打不开
- **怎么验证**：`09-repro.py::test_09_1_…`：先放一份两天前的正常备份（待办报「48 小时前」），再让 `TarFile.add` 打到 `media/a.png` 时抛 `FileNotFoundError`。断言：留下了新的归档、`backup_problems() == []`、状态文件还是旧的，这几条都通过了。脚本里最后一条断言写的是「读不出来」，实际**能读出来**，所以没过；上面的「问题」已按这个结果更正
- **状态**：已复现（掩盖失败这部分）

### 09-2 空草稿清理会删掉只写了「简介」（以及选手联系方式、封面、时间）的赛事草稿（低）

- **位置**：`core/management/commands/cleanup_old_data.py:141-154`
- **问题**：赛事只看 `title=""` 和 `description=""`，没看 `summary`（简介）。设计 13.17 写的是「标题和正文（说明、摘要）都空着」，docstring 也写「Anything with a word in it stays」。自动保存新建赛事时，标题是必填，存不进去，别的字段照存（`core/tests/test_autosave_events.py:76` 就是只存了简介的情形），所以「只有简介没有标题」的草稿是正常操作就能出现的状态
- **失败场景**：赛事管理员新建赛事，先写了一大段简介、选手 QQ 群和报名时间，标题还没想好就走开了；7 天以后每天的清理把它整条删掉
- **怎么验证**：`09-repro.py::test_09_2_…`：以赛事管理员身份自动保存 `{"summary": …, "participant_contact": …}` 到 `tournaments:add`，把 `updated_at` 改到 8 天前，跑 `cleanup_old_data` 后草稿不见了
- **状态**：已复现（测试机 passed）

### 09-3 「通知全体成员 30 分钟内不再发」在定时文章上线的那一刻失效（低）

- **位置**：`core/services.py:248-261`（按 `Broadcast.created_at` 算间隔），`core/services.py:333-349`（`send_waiting` 发信时只改了 `waits_for_publish` 和人数，没记发出时间）
- **问题**：「上线时通知全体成员」的那条记录，`created_at` 是安排的时间（可能是几天前），真正发给全站的时刻是文章上线那一刻。上线、全站收到信以后，编辑马上再点「通知全体成员」，间隔检查看到的「上一次」是几天前，于是放行，全站在几十秒内收到两封。按钮旁边「某时刚通知过」显示的也是安排的时间
- **失败场景**：编辑安排文章周五 20:00 上线并通知；20:00 全站收到；编辑以为没发出去（或者手动发布时又勾了「同时通知」），20:01 再点一次 → 全站第二封。B11 想拦的正是这种情况
- **怎么验证**：`09-repro.py::test_09_3_…`：安排文章、安排通知，把时间拨到上线后 30 秒跑 `publish_due_pages()`，`announcement_problem("article", page) == ""`，再 `announce` 一次，信的数量翻倍
- **状态**：已复现（测试机 passed）

### 09-4 `/healthz` 把「到点才一秒」的延时任务算成「等了 10 分钟」（低）

- **位置**：`core/health.py:138-153`
- **问题**：积压检查的条件是 `enqueued_at <= 现在-10 分钟`，并且 `run_after` 已到。内战提醒、报名开始和截止时的页面刷新、内战自动结束这些延时任务，往往是几天前就排进队列的（`enqueued_at` 很早），到点的那一秒就满足条件。worker 只有一个线程，只要它在跑别的长任务（全量预渲染、字体切片、SMTP 不通时每封信卡 20 秒），这段时间里到点的延时任务都会让 `/healthz` 返回 503。设计 16.6 说的是「超过 10 分钟未处理」，应该从 `max(enqueued_at, run_after)` 开始算
- **失败场景**：外部监控每分钟查一次，worker 在做全量预渲染时，内战提醒刚好到点 → 报警，过一会儿又自己好了；`web` 容器的 Docker 健康检查也跟着变成 unhealthy
- **怎么验证**：`09-repro.py::test_09_4_…`：建一条 READY 任务，`enqueued_at` 两天前，`run_after` 一秒前 → `check_task_backlog()` 返回 `False`
- **状态**：已复现（测试机 passed）

### 09-5 `restore --from-s3` 把解密后的明文备份留在临时目录里（低）

- **位置**：`core/management/commands/restore.py:135-145`
- **问题**：`downloaded = tempfile.mkdtemp(prefix="restore-")` 之后再也没删过（变量 `downloaded` 只赋值，不使用）。解密出来的 `downloaded.tar.gz` 里是整库（邮箱、联系方式）和全部 media，在容器的 `/tmp` 里一直留到容器重建；只演练、不加 `--yes` 也一样会留下
- **失败场景**：在 `web` 里 `exec … restore --from-s3 KEY` 演练一次，`/tmp/restore-*/` 下就留着一份明文全量备份，直到下次升级重建容器；而设计 16.7 要求上传前加密，就是不想让明文留在不该留的地方
- **怎么验证**：`09-repro.py::test_09_5_…`：把 `tempfile.tempdir` 指到临时目录，演练一次 `restore --from-s3`，`restore-*/downloaded.tar.gz` 还在，里面有 `db.sqlite3`
- **状态**：已复现（测试机 passed；留下的 `restore-*/downloaded.tar.gz` 里有 `db.sqlite3`、`media`）

### 09-6 换了新服务器时，只靠命令行没法从异地备份恢复（低）

- **位置**：`core/management/commands/restore.py:102-127`、`core/offsite.py:97-100,266-280`；README「备份与恢复」
- **问题**：`--from-s3` 的存储桶凭据从**当前库**的 `SiteSettings` 读。服务器全丢以后，新装的库里没有这些设置（凭据在备份里），而 `restore` 既不收凭据参数，也不能解密本地的 `.enc` 文件（直接 `restore x.tar.gz.enc` 会在 `tarfile.open` 上抛一串没处理的异常）。所以要先把新站跑起来、建超管、通过 HTTPS 登录后台（生产 Cookie 只走 HTTPS），把对象存储填一遍，或者进 shell 写 `SiteSettings`，才能恢复。README 没写这一步；182 的恢复演练用的是本地文件，没走过这条路。设计 15.4 的目标是「4 小时内在新服务器上恢复」
- **失败场景**：正式站整台机器丢了，手里只有 R2 的凭据和 `BACKUP_ENCRYPTION_KEY`，照 README 执行 `restore --list-s3` → 「异地备份还缺这些设置」，然后只能现场想办法
- **怎么验证**：在一个新建的空库上设好 `BACKUP_ENCRYPTION_KEY`，执行 `manage.py restore --list-s3`；再对一个 `.enc` 文件执行 `manage.py restore x.tar.gz.enc`
- **状态**：已核对代码

### 09-7 设计、README 和实现对不上的三处（低）

- **a. 夜里的全量预渲染**：设计 16.5 写「排入任务队列，由 worker 执行」，`deploy/crontab.example:23` 是在 `web` 里 `exec … prerender` 当场生成，不经过 worker。结果没错（写文件用的是 `os.replace`），但按 AGENTS 硬规则 1，要么改设计、要么改 cron；而且这样一来，夜里这一步也就不能顺带检验 worker 能不能渲染（064 的坑）。已核对代码
- **b. README 写的恢复顺序**：README「备份与恢复」写的是「关连接 → 删 WAL → 替换数据库 → 恢复 media → 清空 prerendered」，代码（`restore.py:192-222`）和设计 16.7 v6.2 都是先恢复 media、再换数据库。照 README 理解出错时的情况（「数据库已经换了吗？」）会判断错。已核对代码
- **c. 预渲染失败的每日邮件**：设计 16.6 写「每天汇总一次失败页面，邮件通知超级管理员（默认）」，代码里找不到（`grep` 不到相关的信或任务），现在只在后台待办里显示「N 个静态页面生成失败」（`core/admin_todo.py:206-213`）。这条和 08 块有重叠。已核对代码

### 09-8 `optimize_db` 的「检查点跳过」提示永远不会出现（低）

- **位置**：`core/management/commands/optimize_db.py:37-42`
- **问题**：`PRAGMA wal_checkpoint(TRUNCATE)` 被读者挡住时不会抛异常，而是返回一行，第一列 `busy=1`（SQLite 文档的语义）。`except OperationalError` 这一支走不到，挡住了也照样打印「优化后」，从来没有「跳过」的警告
- **怎么验证**：另开一个连接 `BEGIN; SELECT …` 占住读事务，再跑 `optimize_db`，看输出里有没有「跳过」，再看 `cursor.fetchone()`
- **状态**：已核对代码（没有复现）

### 09-9 正式站的 cron 按夏令时换算，10-25 以后整体晚 1 小时（低）

- **位置**：AGENTS.md「第二台」→ 定时任务（服务器时区 Europe/Berlin，「按夏令时减 6 小时写」）；README「定时任务」写的是「服务器时区一般是 UTC，减 8 小时」
- **问题**：Debian 的 cron 不支持 `CRON_TZ`，柏林 2026-10-25 起改回冬令时，按北京时间减 6 小时写死的条目会整体推迟 1 小时（备份变成北京时间 04:00，清理 05:00……）。先后顺序不变，影响不大，但和设计 16.5 的时间表不一致；README 的换算说明也不适用于正式站
- **状态**：推测（只看了文档，没登录正式站看 `/etc/cron.d/sjtu-ow`）

### 09-10 数据库缓存用的是默认的 `MAX_ENTRIES`（300），worker 心跳可能被挤掉（推测，低到中）

- **位置**：`sjtu_ow/settings/base.py:124-128`（`DatabaseCache` 没设 `OPTIONS.MAX_ENTRIES`），`core/health.py:124-135`
- **问题**：Django 的数据库缓存默认最多 300 条，超过就按 `cache_key` 顺序删掉三分之一（先删过期的，再按键名删，不看这条重不重要）。这个缓存里放着 worker 心跳、按 IP 的限流计数（`state:<ip>` 等，每分钟一批）、自动保存的去重钥匙（每张表单一把，存 24 小时）、Wagtail 的站点根路径。条目一多，`sjtu_ow:worker_heartbeat` 就可能在删除之列 → `/healthz`「心跳缺失」直到下一次心跳（最多 30 秒），表现为偶发的 503；限流计数被删，限流就会失效
- **怎么验证**：在正式站上看 `SELECT count(*) FROM django_cache`；或者在测试里写 301 个键之后，看心跳键还在不在
- **状态**：推测（没有看正式站的条目数，也没有复现）

## 查过没问题

- **210 已修的几条**：C1 SMTP 超时（`build_smtp_backend` 传了 `timeout=20`，测试邮件同样走它）；C2 worker 启动时把残留的 RUNNING 任务复位成 READY，在心跳线程启动之前；C3、C11 生产环境 `django.request` 的 ERROR 输出到标准输出，500 页另记一行带请求编号，编号由服务器生成；C7 `ENCRYPTED_COLUMNS` 和全部三个 `EncryptedTextField` 对得上；C9 `/healthz` 对外只给 `ok`，读用户出错时退回不给细节
- **备份**：用 SQLite 在线备份 API（`mode=ro`），不是直接复制文件；`database_path()` 取的是连接实际用的库；本地和异地的保留都只删本站命名的文件（`_is_ours` 要求直接放在前缀下）；异地上传失败会让整条命令失败并写进状态；没有密钥就不上传；加密后的临时文件在 `finally` 里删掉
- **恢复**：解包用 `filter="data"`；先恢复 media（用 `empty_folder`，不删挂载点），再关连接、删 WAL 和 shm、换数据库，再清空 `prerendered` 和 `PrerenderedPage`；密钥校验在动任何东西之前；最后提示「备份比代码旧」
- **发信**：`decide` 用带条件的 `update` 逐行认领，点两次不会发两次；`waiting()` 按做事的人和 7 天过滤，别人的批次 404；预览页按 actor 查；`_safe` 检查回跳地址的主机和协议。**删除账号时的信**：`delete_account` 删 `HeldLetter` 在事务里，退出临时队伍的信在 `on_commit` 里才写，此时删除已经做完，信写在删除之后；用户登出后 `settle` 走 `anyone=True` 直接发，和设计 10.5 一致。15 个会写信的动作，视图都以重定向结束（逐个看过战队、头像、赛事和内战取消），会转到「发信」页
- **信的转义**：`letter.html` 全部自动转义；`readable_url` 返回的不是安全字符串；`wrap_text` 先 `escape` 再把链接替换进去，只有以 `SITE_URL + "/"` 开头的地址变成链接（216 D6），`&quot;` 留在属性值里，跳不出 href；allauth 的纯文本模板关了转义，但只出纯文本
- **主题前缀和白名单**：前缀用 `startswith` 判断，重复加也不会加两次；`EMAIL_ALLOWLIST` 对 to/cc/bcc 都过滤，名单外的一律不发；队列在 `on_commit` 之后才入队；重试 1、5、30 分钟，待办只统计最后一次也失败的
- **群发**：`transaction_mode=IMMEDIATE`，两次并发点击排队执行，第二次能看到第一次的记录，30 分钟的间隔不会被并发绕过；收信人是在用、主邮箱已验证、开着通知的成员（同一个 EmailAddress 行）；退订用签名的令牌，GET 只是问、POST 才退订（邮件扫描器预取链接不会误退），`csrf_exempt` 是为了 RFC 8058 的一键退订，注销的账号（`is_active=False`）链接失效
- **worker**：心跳、定时发布、AI 巡查各自 try，每个任务后 `close_old_connections`；`publish_due_pages` 的判断条件和 Wagtail 的 `publish_scheduled` 一致；SIGTERM 时等当前任务做完，被 SIGKILL 的由启动时的复位兜底
- **cleanup_static**：读不到清单就什么都不删；CSS、JS 每次 `collectstatic` 都会重写，修改时间约等于它们过时的时间。（图片、字体这类不需要改写引用的文件，修改时间是第一次生成的时间，过时后的第二天就可能被删；只影响拿着旧缓存页的访客，影响很小，不单列）
- **文章空草稿**：只删从没发布过、最新修订里标题、摘要、正文都空、7 天没动的；`latest_revision_created_at` 为空的不会被选中

## 没来得及看

- 09-1 里拿不完整的归档去恢复的后果（会不会清空 media）没有实际跑过
- `send_broadcast` 半路抛异常（比如入队时数据库锁超过 5 秒）：剩下的人收不到，任务记成 FAILED，不重试，待办也不提示（只统计邮件任务）。只读了代码，没判断触发概率
- `deliver_queued_email` 的任务参数里存着验证码和信的正文，保留 30 天；注销账号后这些还在（隐私上的取舍，没和设计 15.3 逐条对）
- `core/fonts` 下载、AI 巡查请求的超时上限（`moderation_timeout` 管理员能填多大）对单线程 worker 的影响
- 正式站上的 `/etc/cron.d/sjtu-ow`、`docker buildx du`、`django_cache` 条目数（没有登录正式站）
