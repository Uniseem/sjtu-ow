# 14 部署与 CI（217 复核）

范围：`Dockerfile`、`.dockerignore`、`deploy/docker-compose.yml`、两个入口脚本、`deploy/healthcheck.py`、`deploy/crontab.example`、`deploy/fetch_tailwind_cli.py`、`scripts/check.sh`、`scripts/remote-check.sh`、`scripts/pytest-shards.sh`、`.github/workflows/ci.yml`、`sjtu_ow/settings/{base,prod,env}.py`、`.env.example`、`uv.lock`、`THIRD_PARTY_NOTICES.md`；对照设计 15–17 章、README 部署各节、210 复核（C1–C11 已修，不重复）。

复现脚本：`findings/14-repro.sh`。在测试机上跑过一次：`bash scripts/remote-check.sh run bash handoff/rounds/217-second-review/findings/14-repro.sh`（快照 `e417b2e` + 工作区，测试机 kvm17243）。下面引用的「实测输出」都出自这一次（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261007-033422-279b24a.log`，退出码 0，临时镜像和数据卷已由脚本删除）。K 段（翻旧检查日志）没取到内容，不影响结论。

---

## 14-1 镜像里写死的「构建期」密钥带进了运行时，`prod.py` 的「必填」检查形同虚设

- **严重度**：中
- **位置**：`Dockerfile:3-13`（`ENV ... DJANGO_SECRET_KEY=build-time-only FIELD_ENCRYPTION_KEY=build-time-only DJANGO_ALLOWED_HOSTS=localhost ... DJANGO_SECURE_SSL_REDIRECT=false`）；`sjtu_ow/settings/prod.py:8,19,93`
- **问题**：这几条 `ENV` 只是为了让构建期的 `manage.py tailwind build` 能读生产配置，但 `ENV` 会留在最终镜像里，后面也没有清掉。`prod.py` 写的 `env("DJANGO_SECRET_KEY", required=True)`、`env("FIELD_ENCRYPTION_KEY", required=True)` 本意是「`.env` 漏写就拒绝启动」，可镜像自带了值，漏写时它拿到的是公开在仓库里的 `build-time-only`，照常启动。`DJANGO_SECURE_SSL_REDIRECT` 同理：`prod.py` 的默认是 `True`，镜像把它压成了 `False`。
- **失败场景**：运维新写 `.env` 时把 `DJANGO_SECRET_KEY` 拼错（比如写成 `DJANGO_SECRETKEY`）或漏了一行。容器正常起来、`/healthz` 绿，网站用的是谁都知道的 `SECRET_KEY`（会话签名、密码重置令牌、`signing` 全部可伪造），后台填的 SMTP 密码、对象存储密钥、AI 接口密钥都用公开的 `FIELD_ENCRYPTION_KEY` 加密。没有任何报错；只有手动跑 `check --deploy` 才会出一条 W009 警告（`FIELD_ENCRYPTION_KEY` 连警告都没有）。BuildKit 自己的构建检查也在报这一段（`SecretsUsedInArgOrEnv`）。
- **怎么验证**：`docker run --rm <镜像> env`；不带任何 `-e` 起 Django 打印 `settings.SECRET_KEY`。修法方向：把这些值只放在那一条 `RUN` 的命令前面（`RUN DJANGO_SECRET_KEY=... uv run python manage.py tailwind build`），或用 `ARG`。
- **状态**：已复现。实测输出（C、D 段）：
  ```
  == C. 镜像里留下的环境变量
     DJANGO_SECRET_KEY=build-time-only
     FIELD_ENCRYPTION_KEY=build-time-only
     DJANGO_ALLOWED_HOSTS=localhost
     ...
     DJANGO_SECURE_SSL_REDIRECT=false
  == D. .env 里一个密钥都没写时，生产配置拿到的值（prod.py 写的是 required=True）
     SECRET_KEY = 'build-time-only'
     FIELD_ENCRYPTION_KEY = 'build-time-only'
     ALLOWED_HOSTS = ['localhost']  SITE_URL = http://localhost
     SECURE_SSL_REDIRECT = False
     同样没有 .env 时 manage.py check（不加 --deploy）：
     | System check identified no issues (0 silenced).
  ```
  `docker build --check .` 的输出（B 段）标出了 `Dockerfile` 第 3–13 行这一整段 `ENV`。

## 14-2 gunicorn 用默认的 30 秒超时、同步 worker，Caddy 也不限请求体大小：慢网络上传和后台的字体下载会让 worker 被杀，访客看到维护页

- **严重度**：中
- **位置**：`deploy/entrypoint-web.sh:10-14`（没有 `--timeout`、`--graceful-timeout`，没有 `gunicorn.conf.py`）；`deploy/Caddyfile:31-35`（`reverse_proxy` 没有 `request_body max_size`，Caddy 默认流式转发请求体）；`deploy/Caddyfile:43-51`（502/503/504 一律换成维护页）；`core/fonts/forms.py:76-83`（字体上传上限 30 MB）、`core/fonts/admin_views.py:142,181,224` → `core/fonts/services.py:127-145`（「按网址添加」「从 Google Fonts 添加」在 web 的请求里同步下载，Google 那条是逐个分片顺序下载）
- **问题**：gunicorn 的 sync worker 只在两次请求之间向主进程报到，一个请求（包括读请求体的时间）超过 30 秒，主进程就把这个 worker 杀掉，Caddy 拿到 502，按 `handle_errors` 给访客返回维护页。Caddy 不缓冲请求体，gunicorn 读请求体的速度就是访客上传的速度。服务器在海外（设计 15.1 说网络延迟比处理耗时更要紧），头像、队标、图片 5 MB、字体 30 MB 的上限下，跨境链路 100 KB/s 量级时一次上传就超过 30 秒。另外 web 只有 3 个（正式站 5 个）同步 worker，几个慢上传（或任何人对任何 POST 地址慢慢发一个大的 multipart 请求体，CSRF 中间件读 `request.POST` 时就会把它整个读完）就占满全部 worker，动态页全部排队。
- **失败场景**：①成员在手机网络下上传 4 MB 头像，30 秒后页面变成「网站维护中」，头像没传上，换几次都一样。②超级管理员在后台「从 Google Fonts 添加」一个中文字体的 2–3 个字重：每个字重一百个左右分片，在一个请求里从海外服务器顺序下载，超过 30 秒 worker 被杀；`create_family` 已经提交、`except` 里的 `family.delete()` 没机会执行，留下一个没有字重的字体族和已下载的分片文件（字体下载和 08 块有交叉）。③按网址添加 30 MB 的字体，`DOWNLOAD_TIMEOUT = 30` 是单次套接字操作的超时，整体下载可以远超 30 秒。
- **怎么验证**：起生产镜像，带 CSRF Cookie 和头对 `/accounts/login/` 以 `curl --limit-rate 50k -F avatar=@3MB` 上传，看 curl 结果和 `docker logs` 里的 `WORKER TIMEOUT`（`14-repro.sh` 的 I 段）。修法方向：gunicorn 设 `--timeout`（比如 120）或换 gthread；Caddy 加 `request_body { max_size 32MB }`（再往上的拒绝在边上就挡住）；字体的网址下载、Google 下载挪到 worker 任务里做。
- **状态**：已复现（I 段，直连 gunicorn，没经过 Caddy；经 Caddy 时 502 会被换成维护页是读 Caddyfile 得出的）：
  ```
  不限速上传 3 MB：200 用时 0.249815s 已发 3000210 字节
  限速 50 KB/s 上传 3 MB（约 60 秒）：500 用时 30.723621s 已发 1572864 字节
  [2026-10-06 19:40:29 +0000] [1] [CRITICAL] WORKER TIMEOUT (pid:20)
  gunicorn 命令行：... gunicorn sjtu_ow.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile - --error-logfile -
  ```
  上传到 1.5 MB、30.7 秒时 worker 被杀。字体下载那两条路径是读代码得出的，没实测。

## 14-3 `restore --from-s3` 把解密后的整份备份留在容器的 `/tmp` 里，不删；演练模式也一样

- **严重度**：低
- **位置**：`core/management/commands/restore.py:135-145`（`downloaded = tempfile.mkdtemp(prefix="restore-")`，之后任何分支都没有 `shutil.rmtree(downloaded)`）
- **问题**：`offsite.download` 解密出的 `downloaded.tar.gz` 是明文的数据库快照加全部上传文件（全体用户的邮箱、联系方式），落在容器可写层的 `/tmp/restore-XXXX/` 下。成功、失败、演练（不加 `--yes`）都不清理。设计 15.2 要求备份出了服务器要加密，本地明文只留在 `backups` 卷里、14 天轮换；这一份不在任何轮换里。
- **失败场景**：运维按 README 先演练：`$C exec web python manage.py restore --from-s3 <KEY>`（演练不需要停 web，所以多半在 web 里跑）。演练结束，web 容器的 `/tmp` 里多了一份明文全量备份，一直留到下次重建容器；`docker commit`、容器导出、拿到这台宿主机 Docker 目录的人都能读到，磁盘也多占一份（正式站磁盘本来就紧，见 AGENTS「磁盘」）。
- **怎么验证**：把 `offsite.download` 换成写一个文件的假实现，跑 `restore --from-s3 x`（不加 `--yes`），结束后看 `tempfile.gettempdir()` 下有没有 `restore-*`。
- **状态**：已核对代码（没跑：要对象存储）。

## 14-4 生产镜像里装着 GPL 的 x265 编码器（经 Wagtail → Willow[heif] → pillow-heif 带进来），和设计 17.8 的许可证规则冲突

- **严重度**：低
- **位置**：`uv.lock` 的 `pillow-heif 1.7.0`（`uv tree --invert --package pillow-heif`：`willow v1.12.0 (extra: heif)` ← `wagtail[heif] v8.0` ← `sjtu-ow`）；设计 17.8；`THIRD_PARTY_NOTICES.md`（没提）
- **问题**：pillow-heif 本身是 BSD-3，但它的 Linux 轮子里捆了 `libx265`（GPL-2.0-or-later）和 `libde265`、`libheif`（LGPL-3.0）。设计 17.8 写「GPL、AGPL 这类……不能用」。本站根本不收 HEIC/AVIF（`WAGTAILIMAGES_EXTENSIONS` 只有 jpg/png/webp），这些库一直用不上。当前镜像只在服务器上自己构建、不对外分发，实际的许可证风险不大，但规则说的是「不能用」，而且没人记过这个例外。
- **怎么验证**：看镜像里 `site-packages/pillow_heif.libs/` 和 `pillow_heif.libheif_info()`。修法方向：用 uv 的 `override-dependencies` / 排除 `pillow-heif`，或在设计 17.8 记一条例外并说明理由。
- **状态**：已复现（G 段实测）：
  ```
  libde265-24373b0b.so.0.2.2
  libheif-5ea5cb37.so.1.23.3
  libx265-5e99f1c8.so.216
  License: BSD-3-Clause
  libheif_info: {... 'encoders': {'x265': 'x265 HEVC encoder (4.2+1-e444744)', ...}, 'decoders': {'libde265': ...}}
  ```
  （x265 是 GPL-2.0+、libde265 是 LGPL-3.0，这是上游项目的已知许可证，不是这次跑出来的；`LICENSES_bundled.txt` 的原文没打印。）

## 14-5 `SENTRY_DSN` 读了但没人用：设计和 `.env.example` 都说填了就有错误追踪，实际什么都不发生

- **严重度**：低
- **位置**：`sjtu_ow/settings/base.py:356`；`.env.example:17`；设计 16.3「`SENTRY_DSN` 可选，错误追踪服务的地址」、16.6「错误追踪（建议）」
- **问题**：全仓库只有 `base.py` 这一行出现 `SENTRY_DSN`，依赖里没有 `sentry-sdk`，没有初始化代码。照设计填了地址的运维会以为 500 会上报，实际不会。
- **怎么验证**：`grep -rn SENTRY --include='*.py' .`（只命中 `base.py:356`）；`pyproject.toml` 没有 sentry。改法：要么接上，要么从设计 16.3 和 `.env.example` 里删掉，写成「以后要接」。
- **状态**：已核对代码。

## 14-6 `.env.example` 过时：照它写的生产 `.env` 会关掉预渲染、保留可用的占位密钥

- **严重度**：低
- **位置**：`.env.example:6-7,16`；README「生产 / 测试环境启动」第 107 行「按 .env.example 写 .env」；设计 16.3（`PRERENDER_ENABLED` 生产为 `true`）
- **问题**：①`PRERENDER_ENABLED=false`：`prod.py` 默认是开，但 `.env` 里写了 `false` 就是关；照模板写的正式站全部页面都由 Django 实时渲染，Caddy 的预渲染分流全落空（设计 15.1 的性能目标靠它）。②`FIELD_ENCRYPTION_KEY=change-me-unused-until-encrypted-fields`：注释说「加密字段做出来以前用不上」，现在 SMTP 密码、对象存储密钥、AI 接口密钥都靠它；和 `DJANGO_SECRET_KEY=change-me` 一样，没改就照常启动（`check --deploy` 对 `SECRET_KEY` 只给 W009 警告，对 `FIELD_ENCRYPTION_KEY` 什么都不查）。③`base.py:352` 的注释「Placeholder until M5 / M2」同样过时。
- **怎么验证**：读 `.env.example` 和 `prod.py:19-21`；用 `.env.example` 原样起生产配置看 `settings.PRERENDER_ENABLED`。
- **状态**：已核对代码。

## 14-7 CI 的供应链：Action 只按大版本引用、没收窄令牌权限、检出时留着凭据，再执行一个不核对 sha256 的下载二进制

- **严重度**：低
- **位置**：`.github/workflows/ci.yml:15,18`（`actions/checkout@v4`、`astral-sh/setup-uv@v5`）；整个文件没有 `permissions:`；`ci.yml:36`、`scripts/check.sh:38-39`（`tailwind download_cli`）
- **问题**：216 给镜像里的 Tailwind 命令行加了 sha256 核对（C10），但 CI 和测试机的 `check.sh` 还是用 `manage.py tailwind download_cli`，从 GitHub 下载后不核对就执行。`actions/checkout` 默认把 `GITHUB_TOKEN` 写进 `.git/config`，后面的每一步（包括这个二进制、所有测试依赖）都能读到；没有 `permissions: contents: read`，令牌权限取决于仓库设置（老仓库默认可写）。Action 用可移动的大版本标签，上游标签被改写时 CI 直接跑新代码。
- **怎么验证**：读 `ci.yml`；在 CI 加一步 `git config --get-all http.https://github.com/.extraheader` 看得到令牌。修法方向：`permissions: contents: read`、`persist-credentials: false`、按提交 SHA 固定 Action、CI 和 `check.sh` 也走 `deploy/fetch_tailwind_cli.py`。
- **状态**：已核对代码（令牌是否可写取决于仓库设置，推测）。

## 14-8 `.dockerignore` 的 `__pycache__`、`*.pyc` 只排除根目录那一层，各应用目录下的缓存都进了镜像

- **严重度**：低
- **位置**：`.dockerignore:4-5`
- **问题**：`.dockerignore` 的写法按上下文根目录匹配，`__pycache__` 只排除 `./__pycache__`，要排除所有层得写 `**/__pycache__`、`**/*.pyc`。测试机的检出目录跑过 pytest，48 个 `__pycache__` 目录被 `COPY . .` 带进镜像。Python 按源文件的修改时间和大小判断 `.pyc` 是否过期，一般不会跑错代码，主要是镜像里多了别的机器、别的版本编译出的文件，构建缓存也因此更容易失效（任何一个 `.pyc` 变了，`COPY . .` 那一层就重建）。
- **怎么验证**：`find /app -name __pycache__ -not -path '/app/.venv/*' | wc -l`。
- **状态**：已复现（F 段）：`/app 下（不含 .venv）的 __pycache__ 目录数：48`，例如 `/app/sjtu_ow/settings/__pycache__`、`/app/tournaments/migrations/__pycache__`。

## 14-9 分片测试的 worktree 一直沿用旧的 `data/test.sqlite3`：同名迁移改过之后，分片对着旧表结构跑

- **严重度**：低
- **位置**：`scripts/pytest-shards.sh:35-42`（`git clean -fdq` 不带 `-x`，被忽略的 `data/test.sqlite3` 留着）；`pyproject.toml` 的 `addopts = "--reuse-db"`；`scripts/remote-check.sh:94` 主检出目录同理
- **问题**：`--reuse-db` 下 pytest-django 只对已有的库补跑「没应用过」的迁移。一轮里还没推送的迁移改了内容（名字不变），或者测试机先检了一个新快照、再检一个更旧的快照，分片库里的表结构就和代码对不上。根目录 `conftest.py` 的 `_migration_tests_leave_the_schema_at_latest` 只管测试自己倒回迁移的情况，管不到这个。
- **失败场景**：一轮里写了 `00NN` 迁移，`remote-check.sh` 跑一次；再改这个迁移（加一个字段），再跑：分片库里还是第一版，测试报「没有这一列」之类的假红（反过来删了约束时也可能假绿），CI 是新库、结果不同（AGENTS「本地全绿不等于 CI 全绿」那一类）。
- **怎么验证**：在测试机上对同一个迁移文件改两版，各跑一次 `remote-check.sh`，第二次看分片日志。
- **状态**：已核对代码（没复现）。

## 14-10 设计说每日全量预渲染「排入任务队列，由 worker 执行」，crontab 实际在 web 容器里同步跑

- **严重度**：低
- **位置**：设计 16.5 表格「每天 04:15」；`deploy/crontab.example:23`（`exec -T web python manage.py prerender`）；`core/management/commands/prerender.py:61`（直接 `prerender.generate_all()`）
- **问题**：实现和设计两边各说各的（AGENTS 硬规则 1）。在 web 里同步跑意味着全量生成和 gunicorn 抢 web 容器的内存和 CPU，而 worker 那条「渲染前检查静态清单」的逻辑不参与；结果上没坏，但设计写的不是这样。
- **状态**：已核对代码。改哪边需要定。

## 14-11 `fetch_tailwind_cli.py` 的重试不覆盖下载到一半断开

- **严重度**：低
- **位置**：`deploy/fetch_tailwind_cli.py:80-89`
- **问题**：只在 `URLError`、`TimeoutError`、`ConnectionError` 时重试。112 MB 读到一半连接被对方关掉时，`response.read()` 抛的是 `http.client.IncompleteRead`（`HTTPException` 的子类，不在上面三类里），直接带着堆栈让构建失败——144 加重试正是为了不让一次 GitHub 抖动打断构建。sha256 核对能挡住「读短了但没报错」，挡不住这个异常。
- **怎么验证**：给 `fetch(opener=...)` 传一个 `read()` 抛 `http.client.IncompleteRead(b"")` 的假响应，看是否重试（现在的 `test_a_flaky_download_is_retried` 只测 `URLError`）。
- **状态**：已核对代码。

---

## 查过没问题

- **非 root 运行（216 C10）**：E 段实测 `uid=10001(app)`、`HOME=/home/app`；`/app`、`/app/static`、`/app/locale`、`/app/deploy` 不可写，`/tmp`、`/home/app` 可写。运行时会写的地方只有数据卷（`MEDIA_ROOT`、`STATIC_ROOT`、`PRERENDER_ROOT`、`BACKUP_ROOT`、数据库目录）和 `/tmp`（`backup` 的 `TemporaryDirectory`、Django 上传临时文件、`restore` 见 14-3）。`render_*`、`compile_translations` 这些写 `/app/static`、`/app/locale` 的命令只在开发时用；入口脚本不用 `uv run`，不碰 uv 缓存；`PYTHONDONTWRITEBYTECODE=1`，不会尝试写 `.pyc`。
- **`.dockerignore` 排除 `backups`、`.env.*`**（216）：镜像顶层的 `backups`、`data`、`media`、`prerendered`、`staticfiles` 是 `Dockerfile` 自己建的空挂载点。
- **`check.sh` 的镜像编号比较**：A 段实测 `docker build -q` 只输出一行 `sha256:…`，BuildKit 的构建检查警告不进这个输出，`docker_old != $(cat "$docker_log")` 的比较成立。
- **基础镜像**：H 段实测 Python 3.13.16、OpenSSL 3.0.22（2026-08-25），镜像里没有来自 security 源、可升级的 Debian 包（0 个）。
- **Compose**：三个服务都有 `json-file` 5×10 MB 轮转（设计 15.5）、`restart: unless-stopped`；worker 的 `static` 只读，`backups` 只挂在 web（`backup` 和后台待办都在 web 里读写，worker 不碰）；web 只 `expose` 8000，不对外开端口。
- **停止信号**：web 的 PID 1 是 `exec` 出来的 gunicorn，worker 的 PID 1 是 `python manage.py run_worker`，django-tasks-db 自己装了 SIGTERM 处理（`db_worker.py:83-87`），`docker stop` 能正常退出；10 秒宽限内没跑完的任务由 216 的启动复位兜底。
- **健康检查**：`deploy/healthcheck.py` 带域名和 `X-Forwarded-Proto: https`，503 被 `HTTPError`（`URLError` 子类）接住返回 1；worker 停了时 web 被标成 unhealthy 只是标签，`depends_on` 都没设 `service_healthy`，不影响启动。
- **代理信任**：`SECURE_PROXY_SSL_HEADER` 信任 `X-Forwarded-Proto`；仓库的 Caddyfile 没配 `trusted_proxies`，Caddy 会用真实协议覆盖访客自带的这个头，`X-Real-IP` 也被 `header_up` 覆盖；gunicorn 不对外，不存在绕过 Caddy 直连的路径。
- **生产安全设置**：Secure/HttpOnly/SameSite Cookie、HSTS（和 Caddy 一字不差有测试）、nosniff、`X_FRAME_OPTIONS=DENY`、CSP、`ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` 为空时拒绝启动（前提是镜像没带默认值，见 14-1）。
- **CI 和 `check.sh` 一致**：`core/tests/test_check_script.py` 按行比对命令和环境变量；`docker build` 在 CI 里走的是带 sha256 的 `fetch_tailwind_cli.py`。
- **`remote-check.sh`**：快照用临时索引 `git add -A`，不碰本机暂存区；命令用 `printf %q` 转义；退出时删本机的临时引用；锁用 `flock`。
- **许可证**：`static/vendor/` 四个文件的版本（htmx 2.0.10、Alpine 3.17.1、Sortable 1.15.6、EasyMDE 2.21.0 / CodeMirror 5.65.15）和 `THIRD_PARTY_NOTICES.md` 一致；`uv.lock` 里直接、间接依赖除 14-4 以外都是 MIT/BSD/Apache/ISC/PSF/MPL-2.0（certifi），没有 GPL/AGPL 包。
- **依赖的已知漏洞**：J 段实测 `uvx pip-audit -r <uv export --no-dev> --no-deps` 输出 `No known vulnerabilities found`（PyPI 漏洞库，2026-10-07）。只查了 Python 依赖，没查 Caddy 镜像和 Debian 包以外的东西。
- **crontab**：`DC=` 一行带 `-p` 和 `--env-file`；`exec` 进去的命令以 `app` 运行，备份文件归 `app`。

## 没来得及看

- `scripts/journey.py`、`scripts/screens.py` 没细看（只在测试机上用，不进镜像的运行路径）。
- 正式站上的本机专用文件（`docker-compose.vps.yml`、`Caddyfile.vps`、`.env`）按要求没碰，也没看。
